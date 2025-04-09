from django.shortcuts import render
from rest_framework.generics import GenericAPIView
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from users.models import CustomUser
from users.serializers import CustomUserSerializer, LoginSerializer, LogoutSerializer
from rest_framework.response import Response
from rest_framework import status


class RegisterUserView(GenericAPIView):
    """API endpoint to register users"""
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

    def post(self, request, *args, **kwargs):
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


class UserLoginView(GenericAPIView):
    """API endpoint for user login"""
    queryset = CustomUser.objects.all()
    serializer_class = LoginSerializer


    def post(self, request, *args, **kwargs):
        """Override the post method to handle user login"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']


        response_data = {
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Login successful",
            "data": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "is_verified": user.is_verified,
                "is_staff": user.is_staff,
                "is_seller": user.is_seller,
                "is_active": user.is_active,
                "token": serializer.validated_data['token']
            }
        }
        return Response(response_data, status=status.HTTP_200_OK)
    


class UserLogoutView(GenericAPIView):
    """API endpoint for user logout"""
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer
    authentication_classes = [TokenAuthentication]

    def post(self, request, *args, **kwargs):
        """Override the post method to handle user logout"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                "status": "success",
                "status_code": status.HTTP_200_OK,
                "message": "Logout successful"
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)