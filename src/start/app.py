import json
import logging
import os
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

from status import update_status

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sfn = boto3.client("stepfunctions")


def handler(event, _context):
    failures = []
    for record in event.get("Records", []):
        try:
            _start(record)
        except Exception:
            logger.exception("failed to start workflow messageId=%s", record.get("messageId"))
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def _start(record):
    body = json.loads(record["body"])
    for notice in body.get("Records", []):
        bucket = notice["s3"]["bucket"]["name"]
        key = unquote_plus(notice["s3"]["object"]["key"])
        parts = key.split("/")
        if len(parts) < 3 or parts[0] != "uploads" or key.endswith("/"):
            raise ValueError(f"unexpected object key: {key}")
        image_id = parts[1]
        payload = {"imageId": image_id, "bucket": bucket, "key": key}
        try:
            sfn.start_execution(
                stateMachineArn=os.environ["STATE_MACHINE_ARN"],
                name=image_id,
                input=json.dumps(payload),
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code != "ExecutionAlreadyExists":
                raise
        update_status(image_id, "PROCESSING", objectKey=key)
        logger.info("started workflow imageId=%s", image_id)
