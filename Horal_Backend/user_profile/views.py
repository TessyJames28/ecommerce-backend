from django.shortcuts import get_object_or_404
from rest_framework import status
from .serializers import ProfileSerializer
from rest_framework.generics import GenericAPIView
from .models import Profile
from rest_framework.permissions import AllowAny, IsAuthenticated
from products.views import BaseResponseMixin
from products.utility import IsAdminOrSuperuser

# Create your views here.


class GetUserProfileView(GenericAPIView, BaseResponseMixin):
    """Get user profile details"""
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_profile(self):
        return get_object_or_404(Profile, user=self.request.user)

    def get(self, request):
        """Retrieve user profile details"""
        profile = self.get_profile()
        serializer = self.get_serializer(profile)

        return self.get_response(
            status.HTTP_200_OK,
            "User profile retrieve successfully",
            serializer.data
        )


    def patch(self, request):
        """
        Update user profile fields partially
        response for incorrect current password:
        {
            "current_password": [
                "Current password is incorrect."
            ]
        }
        """
        profile = self.get_profile()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "User profile updated successfully",
            serializer.data
        )
    

class AllUserProfileView(GenericAPIView, BaseResponseMixin):
    """Retrieve all user profile admin"""
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        """Retrieve all user profile"""
        serializer = self.get_serializer(self.get_queryset(), many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "All user profiles retrieve successfully",
            serializer.data
        )
    