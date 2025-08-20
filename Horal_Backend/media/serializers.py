from rest_framework import serializers
from .models import UploadedAsset

class UploadedAssetSerializer(serializers.ModelSerializer):
    uploader = serializers.ReadOnlyField(source="uploader.id")
    seller = serializers.ReadOnlyField(source="seller.id")
    
    # Fields generated in the view, not expected from the request
    media_type = serializers.CharField(read_only=True)
    original_filename = serializers.CharField(read_only=True)
    content_type = serializers.CharField(read_only=True)
    size = serializers.IntegerField(read_only=True)
    key = serializers.CharField(read_only=True)
    url = serializers.URLField(read_only=True)

    class Meta:
        model = UploadedAsset
        fields = [
            "id",
            "uploader",
            "seller",
            "media_type",
            "original_filename",
            "content_type",
            "size",
            "key",
            "url",
            "is_private",
            "created_at",
        ]
        read_only_fields = ["id", "uploader", "seller", "created_at"]
