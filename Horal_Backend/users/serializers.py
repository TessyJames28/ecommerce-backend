import re
from rest_framework import serializers
from .models import CustomUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from notifications.utility import verify_otp

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "email", "phone_number", "password", "is_staff", "is_superuser", "is_seller", "is_active", "last_login"]
        read_only_fields = ["id", "is_active", "last_login"] # WIll add is_seller, is_staff, and is_superuser later
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True},
            'phone_number': {'required': True},
            'password': {'write_only': True, 'required': True},
        }

    
    def validate_phone_number(self, value):
        """Validate the phone number format"""
        if isinstance(value, int):
            value = str(value)
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
    access = serializers.SerializerMethodField(read_only=True)
    refresh = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'access', 'refresh']

    def get_token(self, user):
        """Generate a token for the user"""
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
    
    def get_access_token(self, obj):
        """Get the access token for the user"""
        return self.get_token(obj)['access']
    
    def get_refresh_token(self, obj):
        """Get the refresh token for the user"""
        return self.get_token(obj)['refresh']

    def validate(self, attrs):
        """Validate the login credentials"""
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user = CustomUser.objects.get(email=email)
            if not user.check_password(password):
                raise serializers.ValidationError(_("Invalid password."))
            
            user.is_active = True
            user.last_login = now()
            user.save(update_fields=['is_active', 'last_login'])

        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(_("User with this email does not exist."))

        attrs['user'] = user
        return attrs
    

class LogoutSerializer(serializers.Serializer):
    """Serializer for user logout"""
    refresh = serializers.CharField(required=True)
    id = serializers.UUIDField(required=True)


    def validate(self, attrs):
        """Validate the logout request"""
        if not attrs:
            raise serializers.ValidationError(_("Refresh token is required."))
        
        # Access request.user from the context
        user = self.context.get('request').user
        if user.id != attrs['id']:
            raise serializers.ValidationError(_("User ID does not match."))
        
        self.token = attrs['refresh']
        return attrs
    
    def save(self, **kwargs):
        """Handle the logout process"""
        user_id = self.validated_data.get('id')
        try:
            user = CustomUser.objects.get(id=user_id)
            user.is_active = False
            user.save(update_fields=['is_active'])

            # Delete the token associated with the user
            RefreshToken(self.token).blacklist()
            return user
        except TokenError:
            raise serializers.ValidationError(_("Token is invalid or expired."))
        

class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validate the email format"""
        if not CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("User with this email does not exist."))
        return value
    

class OTPVerificationSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, max_length=4, min_length=4)


    def validate(self, attrs):
        """Validate the password reset confirmation"""
        email = attrs.get('email')
        otp = attrs.get('otp')

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(_("User with this email does not exist."))

        if not verify_otp(user.id, otp):
            raise serializers.ValidationError(_("Invalid or expired OTP."))
        
        attrs['user_id'] = user.id
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    user_id = serializers.UUIDField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        """Validate the password reset confirmation"""
        user_id = attrs.get('user_id')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError(_("Passwords do not match."))
        
        try:
            user = CustomUser.objects.get(id=user_id)
            attrs['user'] = user
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(_("User with this ID does not exist."))
        
        return attrs
    

    def save(self):
        """ Handle the password reset process"""
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']

        user.set_password(new_password)
        user.save(update_fields=['password'])
        return user