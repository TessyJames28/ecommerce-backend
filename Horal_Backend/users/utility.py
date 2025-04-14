from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.oauth2.credentials import Credentials
from django.conf import settings

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
        if credentials and credentials.expired and credentials.refresh_token:
            # Refresh the token if it is expired
            credentials.refresh(google_requests.Request())
            new_token_id = credentials.token
            print("Token refreshed successfully.")
            return new_token_id
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
        new_token_id = refresh_google_token(refresh_token, client_id)
        if new_token_id:
            try:
                # Verify the new token ID
                if new_token_id:
                    id_info = id_token.verify_oauth2_token(
                        new_token_id,
                        google_requests.Request(),
                        client_id
                    )
                    print("New token verified successfully.")
                # Update the token ID in the id_info dictionary
                    id_info['refresh_token'] = refresh_token
                    
                    return id_info
            except Exception as refresh_token:
                print(f"Error refreshing token: {refresh_token}")
                raise ValueError("Invalid token or refresh token")
        else:
            raise ValueError("Failed to refresh expired token")
        


def get_google_auth_url():
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    redirect_uri = "http://localhost:8000/v1/api/user/google-login/"
    scope = "openid email profile"

    auth_url = (
        f"{base_url}?client_id={settings.GOOGLE_OAUTH['WEB_CLIENT_ID']}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope.replace(' ', '%20')}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return auth_url


print("Google auth URL:", get_google_auth_url())