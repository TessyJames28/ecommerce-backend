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
            new_access_token = credentials.token
            print("Token refreshed successfully.")
            return new_access_token
    except Exception as e:
        print(f"Error refreshing Google token: {e}")
        return None