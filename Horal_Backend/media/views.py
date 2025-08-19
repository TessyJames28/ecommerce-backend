import os
import uuid
import logging
from django.conf import settings
from rest_framework import generics, permissions, serializers
from django_filters.rest_framework import DjangoFilterBackend
from .models import UploadedAsset
from .serializers import UploadedAssetSerializer
from .utils.s3 import upload_file, delete_file

logger = logging.getLogger(__name__)

def detect_media_type(content_type: str) -> str:
    if not content_type:
        return "file"
    ct = content_type.lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    if ct in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        return "document"
    return "file"


# -------------------- Upload --------------------
class MediaUploadView(generics.CreateAPIView):
    serializer_class = UploadedAssetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        file_obj = self.request.FILES.get("file")
        if not file_obj:
            raise serializers.ValidationError({"file": "No file provided."})

        max_size = getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 200 * 1024 * 1024)
        if file_obj.size > max_size:
            raise serializers.ValidationError(
                {"file": f"File too large. Max allowed is {max_size} bytes."}
            )

        uploader = self.request.user
        seller = self.request.user if getattr(self.request.user, "is_seller", False) else None
        is_private = str(self.request.data.get("is_private", "false")).lower() in ("1", "true", "yes")

        ext = os.path.splitext(file_obj.name)[1] or ""
        content_type = file_obj.content_type or ""
        media_type = detect_media_type(content_type)
        owner_prefix = f"seller_{seller.id}" if seller else f"user_{uploader.id}"
        file_key = f"{owner_prefix}/{media_type}/{uuid.uuid4().hex}{ext}"

        # Upload to S3
        try:
            upload_file(file_obj, file_key, content_type, is_private)
        except Exception:
            raise serializers.ValidationError({"detail": "Upload failed."})

        # Build public URL
        file_url = None
        if not is_private:
            custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
            if custom_domain:
                file_url = f"https://{custom_domain}/{file_key}"
            else:
                region = getattr(settings, "AWS_S3_REGION_NAME", "")
                if region:
                    file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.{region}.digitaloceanspaces.com/{file_key}"
                else:
                    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "").rstrip("/")
                    file_url = f"{endpoint}/{settings.AWS_STORAGE_BUCKET_NAME}/{file_key}"

        # Save DB record
        try:
            serializer.save(
                uploader=uploader,
                seller=seller,
                media_type=media_type,
                original_filename=file_obj.name,
                content_type=content_type,
                size=file_obj.size,
                key=file_key,
                url=file_url,
                is_private=is_private,
            )
        except Exception:
            logger.exception("DB save failed, attempting to delete uploaded object")
            try:
                delete_file(file_key)
            except Exception:
                pass
            raise serializers.ValidationError({"detail": "Failed to save media record."})


# -------------------- Delete --------------------
class MediaDeleteView(generics.DestroyAPIView):
    queryset = UploadedAsset.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def perform_destroy(self, instance):
        if not instance.can_delete(self.request.user):
            raise PermissionError("Not permitted to delete this asset.")
        try:
            delete_file(instance.key)
        except Exception:
            raise Exception("Failed to delete object from storage")
        instance.delete()


# -------------------- List --------------------
class MediaListView(generics.ListAPIView):
    serializer_class = UploadedAssetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['media_type', 'is_private']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return UploadedAsset.objects.all()
        return UploadedAsset.objects.filter(uploader=user)


# -------------------- Vendor Media List --------------------
class VendorMediaListView(generics.ListAPIView):
    serializer_class = UploadedAssetSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['media_type']

    def get_queryset(self):
        vendor_id = self.kwargs["vendor_id"]
        return UploadedAsset.objects.filter(seller_id=vendor_id, is_private=False)
