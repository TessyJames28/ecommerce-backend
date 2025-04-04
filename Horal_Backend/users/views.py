from django.shortcuts import render
from rest_framework.generics import CreateAPIView
from users.models import CustomUser
from users.serializers import CustomUserSerializer
from rest_framework.response import Response
from rest_framework import status


class RegisterUserView(CreateAPIView):
    """API endpoint to register users"""
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    def create(self, request, *args, **kwargs):
        """Override the create method to handle user registration"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        response_data = {
            "status": "success",
            "status_code": status.HTTP_201_CREATED,
            "message": "User registered successfully",
            "data": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "is_verified": user.is_verified,
                "is_staff": user.is_staff,
                "is_seller": user.is_seller,
                "is_active": user.is_active
            }
        }

        return Response(response_data, status=status.HTTP_201_CREATED)
