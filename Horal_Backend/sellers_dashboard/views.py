from django.shortcuts import get_object_or_404
from django.conf import settings
from .reauth_utils import (
    generate_otp, store_otp, record_send, sendable,
    verify_otp, issue_reauth_token
)
from notifications.emails import send_reauth_email
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from products.utils import BaseResponseMixin
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from products.models import ProductVariant
from .models import ProductRatingSummary
from .serializers import (
    SellerProductRatingsSerializer,
    SellerProductOrdersSerializer,
    SellerProfileSerializer,
    SellerOrderItemSerializer
)
from users.authentication import CookieTokenAuthentication, ReauthRequiredPermission
from .utils import (
    get_return_order,
    get_rolling_topselling_products,
    get_sales_and_order_overview,
    get_sales_by_category,
    get_sellers_topselling_products,
    get_total_order,
    get_total_revenue,
    parse_date_safe,
    get_order_in_dispute
)
from user_profile.models import Profile
from shops.models import Shop
from sellers.models import SellerKYC
from django.db.models import Q
from orders.models import OrderItem
from django.utils import timezone
import calendar, json


# Create your views here.
class SellerProductRatingView(GenericAPIView, BaseResponseMixin):
    """
    Class to handle the aggregation logic for sellers
    products ratings
    """
    serializer_class = SellerProductRatingsSerializer
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, *args, **kwargs):
        """
        Get all products and the ratings for a specific seller
        Get all ProductIndex entries that point to linked
        products under the seller shops
        """
        sort = request.query_params.get("sort", "recent")
        search = request.query_params.get("search", "").strip()

        # Get seller's shops
        shops = Shop.objects.filter(owner__user_id=request.user)

        # Instead of product__in (inefficient for large datasets)
        ratings = ProductRatingSummary.objects.filter(
            shop__in=shops
        ).select_related("product", "shop")

        ratings = list(ratings)  # Get the related ProductIndex objects as a python list

        # Apply serach only within sellers rated products
        if search:

            # Filter in Python based on linked_product fields
            ratings = [
                rating for rating in ratings
                if hasattr(rating.product, 'linked_product') and rating.product.linked_product and (
                    search.lower() in getattr(rating.product.linked_product, 'title', '').lower()
                    or search.lower() in getattr(rating.product.linked_product, 'description', '').lower()
                )
            ]

        # Apply sorting
        if sort == "oldest":
            ratings.sort(key=lambda r: r.product.created_at or timezone.datetime.min)
        else:
            ratings.sort(key=lambda r: r.product.created_at or timezone.datetime.min, reverse=True)


        # serializer response
        serializer = self.get_serializer({
            "shop": shops.first(),
            "reviews": ratings
        })

        return self.get_response(
            status.HTTP_200_OK,
            "Sellers products ratings retrieved successfully",
            serializer.data
        )


class SellerOrderListView(GenericAPIView, BaseResponseMixin):
    """
    Class that handles the retrieval of all a sellers order
    """
    serializer_class = SellerProductOrdersSerializer
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, *args, **kwargs):
        """
        Get all orders beloging to a seller
        """
        user = request.user
        print(f"User: {user}")
        search = request.query_params.get("search")
        filter_status = request.query_params.get("status")
        year = request.query_params.get("year")
        month_input = request.query_params.get("month")
        
        # Convert month value like "january" into numeric value
        month = None
        if month_input:
            try:
                month = list(calendar.month_name).index(month_input.capitalize())
            except ValueError:
                return self.get_response(
                    status.HTTP_400_BAD_REQUEST,
                    "Invalid month name"
                )
            
        # get seller's shop
        try:
            shop = Shop.objects.get(owner__user=user)
        except Shop.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Shop not found"
            )
        
        # Filter order where the product belongs to the seller's shop
        order_items = OrderItem.objects.select_related("variant", "order", "order__user").filter(
            variant__shop=shop
        )


        # Apply search option
        if search:
            # First: get variant IDs where product title matches
            matching_variant_ids = []

            for variant in ProductVariant.objects.select_related("shop"):
                product = variant.product  # GFK object
                if hasattr(product, "title") and search.lower() in product.title.lower():
                    matching_variant_ids.append(variant.id)

            # Then use the IDs to filter the main query
            order_items = order_items.filter(
                Q(order__id__icontains=search) |
                Q(variant__id__in=matching_variant_ids) |
                Q(order__user__full_name__icontains=search)
            )

        # Apply filtering
        if filter_status:
            order_items = order_items.filter(order__status__icontains=filter_status)

        if year:
            order_items = order_items.filter(order__created_at__year=year)

        if month:
            order_items = order_items.filter(order__created_at__month=month)

        serializer = self.get_serializer({
            "shop": shop,
            "orders": order_items
        })

        return self.get_response(
            status.HTTP_200_OK,
            "Sellers order retrieved successfully",
            serializer.data
        )
    

class SellerOrderDetailView(GenericAPIView, BaseResponseMixin):
    """
    Class that handles the retrieval of a single order item details
    from sellers order
    """
    serializer_class = SellerOrderItemSerializer
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]

    def get(self, request, order_item_id):
        """
        Retrieve a single order item
        """
        if not order_item_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Provide the order item id to view the details"
            )
        
        try:
            order_item = OrderItem.objects.get(id=order_item_id)
        except OrderItem.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Order item with this id not found"
            )
        
        serializer = self.get_serializer(order_item)

        return self.get_response(
            status.HTTP_200_OK,
            "Order item details retrieved successfully",
            serializer.data
        )

        
    

class SellerProfileView(GenericAPIView):
    """
    View to retrieve the complete seller profile
    """
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SellerProfileSerializer

    def get_profile(self):
        return get_object_or_404(Profile, user=self.request.user)

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = self.get_profile()

        if not user.is_seller:
            return Response({
                "status": "error",
                "message": "Only sellers can access this endpoint."
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(profile)
        return Response({
            "status": "success",
            "message": "Seller profile retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

    def patch(self, request, *args, **kwargs):
        profile = self.get_profile()
        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=True  # Allow partial updates
        )
        
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "status": "success",
            "message": "Seller profile updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    

class SellerDashboardAnalyticsAPIView(APIView, BaseResponseMixin):
    """
    Class that that displays all data for seller's dashboard
    analytics
    """
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]


    def get(self, request, *args, **kwargs):
        """
        Get method to retrieve sellers dashboard analytics
        """
        user = request.user
        # Get SelleyKYC instance to pass to shop
        try:
            user = SellerKYC.objects.get(user=user)
        except SellerKYC.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Seller KYC not found"
            )

        # Get shop associate with this seller
        try:
            shop = Shop.objects.get(owner=user)
        except Shop.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Seller shop not found"
            )
        
        # Get query params
        period = request.query_params.get("period", "monthly").lower()
        sort = request.query_params.get("sort", None)
        if sort:
            sort.lower()
        
        allowed_periods = ['daily', 'weekly', 'monthly', 'yearly']
        if period not in allowed_periods:
            period = 'monthly'

        # Get core metrics: Revenue and Order Stats
        total_revenue = get_total_revenue(shop.id)
        total_orders = get_total_order(shop.id)
        return_orders = get_return_order(shop.id)
        orders_in_dispute = get_order_in_dispute(shop.id)

        # Sales summary by category (grouped by daily, weekly, etc)
        sales_by_category = get_sales_by_category(shop.id)

        # Order and sales overview chart data
        sales_and_order_overview = get_sales_and_order_overview(shop.id)

        return Response({
            "status": "success",
            "status_code": status.HTTP_200_OK,
            "message": "Seller dashboard analytics retrieve successfully",
            "data": {
                "total_revenue": float(total_revenue),
                "total_orders": total_orders,
                "return_orders": return_orders,
                "orders_in_dispute": orders_in_dispute,
                "sales_by_category": sales_by_category,
                "sales_and_order_overview": sales_and_order_overview
            }
        }, status=status.HTTP_200_OK)
    

class TopSellingProductsAPIView(APIView, BaseResponseMixin):
    """
    Class that that retrieves all sellers top selling products
    Can be filtered by recent and oldest
    """
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]


    def get(self, request, *args, **kwargs):
        """
        Get method to retrieve sellers dashboard analytics
        """
        user = request.user
        # Get SelleyKYC instance to pass to shop
        try:
            user = SellerKYC.objects.get(user=user)
        except SellerKYC.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Seller KYC not found"
            )

        # Get shop associate with this seller
        try:
            shop = Shop.objects.get(owner=user)
        except Shop.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Seller shop not found"
            )
        
        # Get query param
        sort = request.query_params.get("sort", None)
        if sort:
            sort.lower()

        # Rolling top selling products (last 30 days)
        top_selling_products = get_rolling_topselling_products(shop.id) or []

        if sort == "oldest":
            top_selling_products = sorted(
                top_selling_products, 
                key=lambda x: parse_date_safe(x['latest_order_date'])
            )
        elif sort == "recent":
            top_selling_products = sorted(
                top_selling_products, 
                key=lambda x: parse_date_safe(x['latest_order_date']), reverse=True
            )
            

        return self.get_response(
            status.HTTP_200_OK,
            "Seller top selling products retrieved successfully",
            top_selling_products
        )


class ReauthOTPStartView(APIView, BaseResponseMixin):
    """Starts the otp flow by generating and sending OTP to seller email"""
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]


    def post(self, request, *args, **kwargs):
        """Post method to start reauth flow for sellers"""
        user = request.user
        print("DEBUG start OTP for user:", user.id)

        if not user.is_authenticated or not getattr(user, "is_seller", False):
            return self.get_response(
                status.HTTP_401_UNAUTHORIZED,
                "auth_required"
            )
        
        if not sendable(user.id):
            return self.get_response(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "otp send rate limited"
            )
        
        otp = generate_otp()
        store_otp(user.id, otp)
        record_send(user.id)

        try:
            send_reauth_email(
                to_email=user.email, # use for testing purpose. Will be remove for prod
                otp_code=otp,
                subject="Your Reauthentication Verification Code",
                name=user.full_name
            )
        except Exception:
            return self.get_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "failed to send otp"
            )
        
        return self.get_response(
            status.HTTP_200_OK,
            "otp sent"
        )
    

class ReauthOTPVerifyView(APIView, BaseResponseMixin):
    """
    Verifies the OTP and issues a reauth token
    """
    permission_classes = [IsAuthenticated, ReauthRequiredPermission]
    authentication_classes = [CookieTokenAuthentication]


    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not getattr(user, "is_seller", False):
            return self.get_response(status.HTTP_401_UNAUTHORIZED, "auth_required")

        otp = request.data.get("otp")
        platform = request.data.get("platform", "web")
        if not otp:
            return self.get_response(status.HTTP_400_BAD_REQUEST, "otp required")

        ok = verify_otp(user.id, otp)
        if not ok:
            return self.get_response(
                status.HTTP_403_FORBIDDEN,
                "Invalid otp or too many attempts"
            )

        token = issue_reauth_token(user.id)

        if platform == "mobile":
            # Mobile: return token in JSON so the app can store it (e.g. in secure storage)
            return Response(
                {"detail": "reauth_ok", "reauth_token": token},
                status=status.HTTP_200_OK
            )
        else:
            # Web: set token as HttpOnly cookie
            resp = Response({"detail": "reauth_ok"}, status=status.HTTP_200_OK)
            resp.set_cookie(
                key="reauth_token",
                value=token,   # <- FIXED (was missing)
                httponly=True,
                secure=True,  # only True if HTTPS
                samesite="None",
                max_age=getattr(settings, "REAUTH_TTL", 15 * 60),
            )
            return resp

