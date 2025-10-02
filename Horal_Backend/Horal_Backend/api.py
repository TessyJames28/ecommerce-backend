from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import exception_handler
from sellers_dashboard.reauth_utils import ReauthRequired


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, ReauthRequired):
        return Response(
            {"detail": "reauth_required"},
            status=status.HTTP_403_FORBIDDEN
        )

    return response