import os
from datetime import datetime, timezone

import boto3

_table = None


def _table_resource():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


def update_status(image_id: str, status: str, **attributes) -> None:
    names = {"#status": "status", "#updatedAt": "updatedAt"}
    values = {
        ":status": status,
        ":updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    assignments = ["#status = :status", "#updatedAt = :updatedAt"]
    for key, value in attributes.items():
        if value is None:
            continue
        names[f"#{key}"] = key
        values[f":{key}"] = value
        assignments.append(f"#{key} = :{key}")
    _table_resource().update_item(
        Key={"imageId": image_id},
        UpdateExpression="SET " + ", ".join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
