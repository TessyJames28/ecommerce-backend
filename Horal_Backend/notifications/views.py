from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework import status
from .models import Notification
from products.utils import BaseResponseMixin
from .serializers import NotificationSerializer
from users.authentication import CookieTokenAuthentication
from .tasks import send_notification_email
from django.utils.timezone import now
from rest_framework.permissions import IsAuthenticated
from support.serializers import SupportSerializer

# Create your views here.
class NotificationListView(GenericAPIView, BaseResponseMixin):
    """
    Class to get notification (in-app)
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, *args, **kwargs):
        """method to get notifications"""
        try:
            notifications = Notification.objects.filter(
                user=request.user
            )
        except Notification.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "No notification found for this user"
            )
        
        serializer = self.get_serializer(notifications, many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "Notifications retrieved successfully",
            serializer.data
        )
    

    # def post(self, request, *args, **kwargs):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     notification = serializer.save()

    #     # Trigger async email via celery
    #     send_notification_email.delay(notification.id)

    #     return self.get_response(
    #         status.HTTP_201_CREATED,
    #         "Notification created successfully",
    #         serializer.data
    #     )
    

class NotificationDetailView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve and view a single notification"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get_object(self, pk, user):
        return Notification.objects.filter(
            id=pk, user=user
        ).first()
    
    def get(self, request, pk, *args, **kwargs):
        """Method to retrieve a single notiication"""
        notification = self.get_object(pk, request.user)

        if not notification:
            self.get_response(
                status.HTTP_404_NOT_FOUND,
                "No notification found"
            )

        serializer = self.get_serializer(notification)
        return self.get_response(
            status.HTTP_200_OK,
            "Notification retrieved successfully",
            serializer.data
        )
    

    def patch(self, request, pk, *args, **kwargs):
        """
        Method to patch notification
        Specifically for users to mark as read
        """
        notification = self.get_object(pk, request.user)

        if not notification:
            self.get_response(
                status.HTTP_404_NOT_FOUND,
                "No notification found"
            )

        notification.mark_as_read()

        return self.get_response(
            status.HTTP_200_OK,
            "notification marked as read"
        )
    

    # def delete(self, request, pk, * args, **kwargs):
    #     """Method to delete a single notification"""
    #     notification = self.get_object(pk, request.user)

    #     if not notification:
    #         self.get_response(
    #             status.HTTP_404_NOT_FOUND,
    #             "No notification found"
    #         )
        
    #     notification.delete()
    #     return self.get_response(
    #         status.HTTP_204_NO_CONTENT,
    #         "Notification deleted successfully"
    #     )
    

class MarkAsReadView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve and view a single notification"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]

    def get_object(self, pk, user):
        return Notification.objects.filter(
            id=pk, user=user
        ).first()
    

    def patch(self, request, pk, *args, **kwargs):
        """
        Method to patch notification
        Specifically for users to mark as read
        """
        notification = self.get_object(pk, request.user)

        if not notification:
            self.get_response(
                status.HTTP_404_NOT_FOUND,
                "No notification found"
            )

        notification.mark_as_read()

        return self.get_response(
            status.HTTP_200_OK,
            "notification marked as read"
        )



class SupportCreateView(GenericAPIView, BaseResponseMixin):
    """Class to handle the creation of support ticket"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportSerializer


    def post(self, request):
        """API to create support ticket by customers"""
        serializer = self.get_serializer(
            data=request.data,
            context={"customer": request.user}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_201_CREATED,
            "Support ticket created successfully",
            serializer.data
        )
