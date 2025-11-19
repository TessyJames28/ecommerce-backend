from media.utils.s3 import get_s3_client
from django.conf import settings
from PIL import Image
from io import BytesIO
import boto3
from urllib.parse import urlparse
from django.db import transaction
from .models import (
    VehicleImage, FashionImage, ElectronicsImage,
    FoodImage, HealthAndBeautyImage, AccessoryImage,
    ChildrenImage, GadgetImage
)


IMAGE_MODELS = [
    VehicleImage, FashionImage, ElectronicsImage,
    FoodImage, HealthAndBeautyImage, AccessoryImage,
    ChildrenImage, GadgetImage
]

def extract_file_key(url: str) -> str:
    """Extract the S3 object key from a given S3 URL."""
    parsed = urlparse(url)

    key = parsed.path.lstrip('/')
    return key


def s3_file_exists(file_key:str, bucket: str) -> bool:
    """Function to check if a file exists in S3 bucket"""
    s3 = get_s3_client()
    try:
        s3.head_object(Bucket=bucket, Key=file_key)
        return True
    except s3.exceptions.ClientError:
        return False
    

def delete_s3_file(file_key: str, bucket: str):
    """Function to delete a file from s3 bucket"""
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=bucket, Key=file_key)
    except Exception:
        pass


def is_broken_record(img) -> bool:
    """Function to determine if an image record is broken"""
    if not img.url:
        return True
    
    parsed = urlparse(img.url)
    if not parsed.path or "." not in parsed.path:
        return True
    
    return False


def is_corrupted_image(file_key, bucket):
    """Function to check if an image in S3 is corrupted"""
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=bucket, Key=file_key)
        body = response['Body'].read()
        image = Image.open(BytesIO(body))
        image.verify()  # Verify that it is, in fact an image
        return False
    except Exception:
        return True
    

def scan_image_model(model_class, bucket_name: str):
    """Function to scan a single image model"""
    products_to_unpublish = set()

    for img in model_class.objects.all():
        product = img.product
        file_key = extract_file_key(img.url)

        # Check record integrity
        record_is_broken = is_broken_record(img)

        # check if image exists in S3
        exists_in_s3 = s3_file_exists(file_key, bucket_name)

        # Case 1: DB broken but file exists => delete both
        if record_is_broken and exists_in_s3:
            delete_s3_file(file_key, bucket_name)

            if product.images.count() <= 1:
                products_to_unpublish.add(product.id)
            else:
                img.delete()
            continue

        # Case 2: DB broken and file missing => delete DB entry
        if record_is_broken and not exists_in_s3:
            if product.images.count() <= 1:
                products_to_unpublish.add(product.id)
            else:
                img.delete()
            continue

        # Case 3A: DB ok but missing on S3 → broken
        if not record_is_broken and not exists_in_s3:
            if product.images.count() <= 1:
                products_to_unpublish.add(product.id)
            else:
                img.delete()
            continue

        
        # Case 3B: DB okay, S3 exists, but file is corrupted
        if not record_is_broken and exists_in_s3:
            # Check if file is corrupted
            if is_corrupted_image(file_key, bucket_name):
                if product.images.count() <= 1:
                    products_to_unpublish.add(product.id)
                else:
                    delete_s3_file(file_key, bucket_name)
                    img.delete()
            continue

    #  Unpublish products with 1 broken image remaining
    if products_to_unpublish:
        model_class._meta.get_field("product").remote_field.model.objects.filter(
            id__in=products_to_unpublish
        ).update(is_published=False)


def scan_all_product_images():
    """Function to scan all product images across different models"""
    bucket = settings.AWS_STORAGE_BUCKET_NAME

    with transaction.atomic():
        for model in IMAGE_MODELS:
            scan_image_model(model, bucket)

