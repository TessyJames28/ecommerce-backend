import re
from rest_framework import serializers
from .models import CustomUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class CustomUserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(
        min_length=11,
        max_length=14,
        validators=[
            RegexValidator(
                regex=r'^\d{11,14}$',
                message=_("Phone number must contain only digits and be between 11 and 14 digits."),
            )
        ]
    )
    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "email", "phone_number", "password", "is_verified", "is_staff", "is_seller", "is_active"]
        read_only_fields = ["id", "is_verified", "is_seller", "is_active"]
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True},
            'phone_number': {'required': True},
            'password': {'write_only': True, 'required': True},
        }

    def validate_password(self, password):
        """Enforce strong password requirement"""
        if not password or len(password) < 8:
            raise ValidationError(_("Password must be at least 8 characters long."))
        if not re.search(r'[A-Z]', password):
            raise ValidationError(_("Password must contain at least one uppercase letter."))
        if not re.search(r'[a-z]', password):
            raise ValidationError(_("Password must contain at least one lowercase letter."))
        if not re.search(r'[0-9]', password):
            raise ValidationError(_("Password must contain at least one digit."))
        if not re.search(r'[@$!#%*?&^(),.?\":{}|<>]', password):
            raise ValidationError(_("Password must contain at least one special character."))
        if re.search(r'\s', password):
            raise ValidationError(_("Password must not contain spaces."))
        
        return password
    

    def create(self, validated_data):
        """Hash the password before saving"""
        password = validated_data.pop("password")
        user = super().create(validated_data)
        user.set_password(password) # Hash the password here
        user.save()
        return user