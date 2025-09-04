import boto3
import logging
from django.conf import settings
from botocore.exceptions import NoCredentialsError, ClientError

logger = logging.getLogger(__name__)

def get_s3_client():
    return boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
    )

def upload_file(file_obj, key, content_type=None, is_private=False):
    s3 = get_s3_client()
    extra_args = {"ContentType": content_type} if content_type else {}
    if not is_private:
        extra_args["ACL"] = "public-read"
    try:
        s3.upload_fileobj(file_obj, settings.AWS_STORAGE_BUCKET_NAME, key, ExtraArgs=extra_args)
    except NoCredentialsError:
        logger.exception("Invalid storage credentials")
        raise
    except ClientError:
        logger.exception("S3 client error during upload")
        raise
    except Exception:
        logger.exception("Unexpected error during upload")
        raise
    return key

def delete_file(key):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
    except Exception:
        logger.exception("Failed to delete object from storage")
        raise
