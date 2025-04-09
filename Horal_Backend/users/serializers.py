import re
from rest_framework import serializers
from .models import CustomUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.models import Token


class CustomUserSerializer(serializers.ModelSerializer):
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

    
    def validate_phone_number(self, value):
        if not value.isdigit():
            raise ValidationError(_("Phone number must contain only digits."))
        if len(value) != 11:
            raise ValidationError(_("Phone number must be exactly 11 digits."))
        return value

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


class LoginSerializer(serializers.ModelSerializer):
    """Serializer for user login"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    token = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'token']

    def get_token(self, obj):
        """Generate a token for the user"""
        token, created = Token.objects.get_or_create(user=obj)
        return token.key if created else token.key

    def validate(self, attrs):
        """Validate the login credentials"""
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user = CustomUser.objects.get(email=email)
            user.is_active = True
            user.save(update_fields=['is_active'])
            if not user.check_password(password):
                raise serializers.ValidationError(_("Invalid password."))
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(_("User with this email does not exist."))

        attrs['user'] = user
        attrs['token'] = self.get_token(user)
        return attrs
    

class LogoutSerializer(serializers.Serializer):
    """Serializer for user logout"""
    id = serializers.UUIDField(required=True)

    def validate(self, attrs):
        """Validate the logout request"""
        if not attrs:
            raise serializers.ValidationError(_("ID is required."))
        return attrs
    
    def save(self, **kwargs):
        """Handle the logout process"""
        user_id = self.validated_data.get('id')
        try:
            user = CustomUser.objects.get(id=user_id)
            user.is_active = False
            user.save(update_fields=['is_active'])

            # Delete the token associated with the user
            if hasattr(user, 'auth_token'):
                user.auth_token.delete()
            return user
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(_("User with this ID does not exist."))
