import re
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.oauth2.credentials import Credentials
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import requests
from rest_framework_simplejwt.tokens import RefreshToken

def refresh_google_token(refresh_token, client_id):
    """Refresh the Google access token using the refresh token."""
    print("Refreshing Google token...")
    # Pass the refresh token to get a new access token
    try:
        credentials = Credentials(
            None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=settings.GOOGLE_OAUTH['CLIENT_SECRET'],
            token_uri='https://oauth2.googleapis.com/token'
        )
        print("Credentials created successfully.")
        
        # Refresh the to get a new access token
        credentials.refresh(google_requests.Request())
        print("Token refreshed successfully.")

        # Use the access token to get user info from Google's userinfo endpoint
        access_token = credentials.token
        user_info_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}

        user_info_response = requests.get(user_info_url, headers=headers)
        if user_info_response.status_code == 200:
            # Return the user info directly
            user_info = user_info_response.json()
            print("User info retrieved successfully.")
            print(user_info)
            return user_info
        else:
            print(f"Error retrieving user info: {user_info_response.text}")
            return None
        # return new_token_id
    except Exception as e:
        print(f"Error refreshing Google token: {e}")
        return None
    

def verify_google_token(token_id, refresh_token, client_id):
    """Verify the Google token ID and refresh token."""
    print("Verifying Google token...")
    try:
        # Verify the token using Google's API
        id_info = id_token.verify_oauth2_token(
            token_id,
            google_requests.Request(),
            client_id
        )
        print("Token verified successfully.")
        return id_info
    except ValueError as e:
        print(f"Token expired or invalid, attempting a refresh ...")
        if not refresh_token:
            raise ValueError("Token expired and no refresh token provided")
        
        # Attempt to refresh the token if it's expired
        user_info = refresh_google_token(refresh_token, client_id)
        if user_info:
            print("Successfully retrived user info with refresh token")

            # Add the refresh flag to indicate we used the refresh flow
            user_info['refreshed_token'] = True
            print(f"In verified_google_token: {user_info}")
            return user_info
        else:
            raise ValueError("Failed to refresh expired token")


def validate_strong_password(password):
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


def generate_token_for_user(user):
    """Generate a token for the user"""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }


def exchange_code_for_token(code):
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': settings.GOOGLE_OAUTH['WEB_CLIENT_ID'],
        'client_secret': settings.GOOGLE_OAUTH['CLIENT_SECRET'],
        'redirect_uri': settings.GOOGLE_OAUTH['REDIRECT_URI'],
        'grant_type': 'authorization_code'
    }

    response = requests.post(token_url, data=data)
    return response.json()