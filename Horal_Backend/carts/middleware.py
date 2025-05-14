from django.conf import settings
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.sessions.middleware import SessionMiddleware


class CartMiddleware:
    """Middleware to handle cart session management"""

    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        # If user logs in and has a session cart, it will merge be merged on views
        # This ensures the session exists

        if not request.session.session_key:
            request.session.create()

        response = self.get_response(request)
        return response
    

class SessionFixMiddleware:
    """
    Middleware to ensure django session work consistent for anonymous users.
    This fixes issues with session key generation for cart management
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Always create a session for anonymous users if they don't have one
        if not hasattr(request, 'session') and not request.session.session_key:
            request.session.save()
            request.session.modified = True

        response = self.get_response(request)
        return response