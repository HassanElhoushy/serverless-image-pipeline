import logging
import os

import boto3

from process import InvalidImage, apply_watermark, inspect_image, resize_image
from status import update_status

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
THUMBNAIL_EDGE = 300
DISPLAY_EDGE = 1280


def validate_handler(event, _context):
    image_id = event["imageId"]
    bucket = event["bucket"]
    key = event["key"]
    data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    try:
        info = inspect_image(data)
    except InvalidImage as exc:
        logger.info("rejected imageId=%s reason=%s", image_id, exc)
        update_status(image_id, "REJECTED", errorMessage=str(exc))
        return {
            "imageId": image_id,
            "bucket": bucket,
            "key": key,
            "valid": False,
            "reason": str(exc),
        }
    update_status(
        image_id,
        "VALIDATED",
        width=info["width"],
        height=info["height"],
        format=info["format"],
    )
    return {
        "imageId": image_id,
        "bucket": bucket,
        "key": key,
        "valid": True,
        "width": info["width"],
        "height": info["height"],
        "format": info["format"],
    }


def resize_handler(event, _context):
    image_id = event["imageId"]
    source_bucket = os.environ["SOURCE_BUCKET"]
    data = s3.get_object(Bucket=event["bucket"], Key=event["key"])["Body"].read()
    thumbnail_key = f"staging/{image_id}/thumbnail.png"
    display_key = f"staging/{image_id}/display.png"
    _put_png(source_bucket, thumbnail_key, resize_image(data, THUMBNAIL_EDGE))
    _put_png(source_bucket, display_key, resize_image(data, DISPLAY_EDGE))
    logger.info("resized imageId=%s", image_id)
    return {
        **event,
        "stagingBucket": source_bucket,
        "thumbnailKey": thumbnail_key,
        "displayKey": display_key,
    }


def watermark_handler(event, _context):
    image_id = event["imageId"]
    dest_bucket = os.environ["DEST_BUCKET"]
    text = os.environ.get("WATERMARK_TEXT", "PREVIEW")
    thumbnail_out = f"images/{image_id}/thumbnail.png"
    display_out = f"images/{image_id}/display.png"
    _watermark_object(event["stagingBucket"], event["thumbnailKey"], dest_bucket, thumbnail_out, text)
    _watermark_object(event["stagingBucket"], event["displayKey"], dest_bucket, display_out, text)
    logger.info("watermarked imageId=%s", image_id)
    return {
        **event,
        "thumbnailKey": thumbnail_out,
        "displayKey": display_out,
        "outputBucket": dest_bucket,
    }


def store_handler(event, _context):
    image_id = event["imageId"]
    domain = os.environ["CLOUDFRONT_DOMAIN"]
    thumbnail_url = f"https://{domain}/{event['thumbnailKey']}"
    display_url = f"https://{domain}/{event['displayKey']}"
    staging_bucket = event.get("stagingBucket")
    if staging_bucket:
        s3.delete_objects(
            Bucket=staging_bucket,
            Delete={
                "Objects": [
                    {"Key": f"staging/{image_id}/thumbnail.png"},
                    {"Key": f"staging/{image_id}/display.png"},
                ],
                "Quiet": True,
            },
        )
    update_status(
        image_id,
        "COMPLETE",
        thumbnailUrl=thumbnail_url,
        displayUrl=display_url,
        width=event.get("width"),
        height=event.get("height"),
        format=event.get("format"),
    )
    logger.info("stored imageId=%s", image_id)
    return {
        "imageId": image_id,
        "status": "COMPLETE",
        "thumbnailUrl": thumbnail_url,
        "displayUrl": display_url,
    }


def fail_handler(event, _context):
    image_id = event.get("imageId")
    error = event.get("error") or {}
    cause = error.get("Cause") if isinstance(error, dict) else str(error)
    reason = str(cause or "processing failed")[:1000]
    if image_id:
        update_status(image_id, "FAILED", errorMessage=reason)
    logger.info("failed imageId=%s", image_id)
    return {"imageId": image_id, "status": "FAILED", "reason": reason}


def _watermark_object(source_bucket, source_key, dest_bucket, dest_key, text):
    data = s3.get_object(Bucket=source_bucket, Key=source_key)["Body"].read()
    _put_png(dest_bucket, dest_key, apply_watermark(data, text))


def _put_png(bucket, key, data):
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/png")
