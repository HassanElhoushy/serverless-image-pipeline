import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3

from names import resolve_content_type, safe_file_name

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
URL_TTL_SECONDS = 300


def handler(event, _context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")
    if method == "POST" and path == "/uploads":
        return create_upload(event)
    if method == "GET" and path.startswith("/images/"):
        return get_image(event)
    return _response(404, {"message": "not found"})


def create_upload(event):
    try:
        body = _body(event)
        file_name = safe_file_name(body.get("fileName", ""))
        content_type = resolve_content_type(file_name, body.get("contentType", ""))
    except (ValueError, json.JSONDecodeError) as exc:
        return _response(400, {"message": str(exc)})

    image_id = str(uuid.uuid4())
    key = f"uploads/{image_id}/{file_name}"
    table().put_item(
        Item={
            "imageId": image_id,
            "status": "AWAITING_UPLOAD",
            "fileName": file_name,
            "contentType": content_type,
            "objectKey": key,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": os.environ["SOURCE_BUCKET"],
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=URL_TTL_SECONDS,
    )
    logger.info("issued upload imageId=%s", image_id)
    return _response(
        201,
        {
            "imageId": image_id,
            "uploadUrl": upload_url,
            "objectKey": key,
            "contentType": content_type,
            "expiresIn": URL_TTL_SECONDS,
        },
    )


def get_image(event):
    image_id = (event.get("pathParameters") or {}).get("imageId")
    if not image_id:
        return _response(400, {"message": "imageId is required"})
    item = table().get_item(Key={"imageId": image_id}).get("Item")
    if not item:
        return _response(404, {"message": "image not found"})
    return _response(200, item)


def table():
    return dynamodb.Table(os.environ["TABLE_NAME"])


def _body(event) -> dict:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if isinstance(raw, dict):
        return raw
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
