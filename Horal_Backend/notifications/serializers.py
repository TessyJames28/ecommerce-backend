from rest_framework import serializers
from .models import Notification
from django.contrib.contenttypes.models import ContentType
from .utils import ALLOWED_NOTIFICATION_MODELS


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for the notification model"""

    class Meta:
        model = Notification
        fields = [
            "id", "type", "channel", "subject", "message", "is_read",
            "status", "created_at", "read_at", "object_id", "content_type"
        ]

    def create(self, validated_data):
        """Override serializer create method"""

        # Extract content_type as string if provided
        content_type_str = validated_data.pop("content_type", None)
        object_id = validated_data.pop("object_id")

        if content_type_str and object_id:
            if self.content_type.model_class() not in ALLOWED_NOTIFICATION_MODELS.values():
                raise serializers.ValidationError("Invalid model for notification.")

            try:
                ct = ContentType.objects.get(model=content_type_str.lower())
                validated_data["content_type"] = ct
            except ContentType.DoesNotExist:
                raise serializers.ValidationError(
                    {"content_type": f"Invalid content type '{content_type_str}'"}
                )
        else:
            validated_data["content_type"] = None
            validated_data["object_id"] = None

        notification = Notification.objects.create(**validated_data)
        return notification
