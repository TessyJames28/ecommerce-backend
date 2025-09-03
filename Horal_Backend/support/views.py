from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.db.models import Q, F
from django.utils.timezone import now
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
from users.authentication import CookieTokenAuthentication
import re
from .models import (
    Support, SupportTeam,
    Tickets, Message,
    SupportAttachment
)
from orders.models import OrderReturnRequest
from users.utils import get_or_create_temp_user
from .serializers import (
    TicketsSerializer, SupportSerializer,
    SupportTeamSerializer, StaffSerializer,
    SupportTeamNameSerializer,
    TicketsUpdateSerializer,
    MessageSerializer
)
from .utils import handle_mailgun_attachments
from products.utils import BaseResponseMixin
from sellers_dashboard.helper import validate_uuid
from products.utils import StandardResultsSetPagination
from notifications.models import Notification
from notifications.utils import ALLOWED_NOTIFICATION_MODELS


# Create your views here.

class SupportTeamCreateView(GenericAPIView, BaseResponseMixin):
    """Class for user with is_staff flag to create or list all support team"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportTeamSerializer    

    def post(self, request):
        """API to get all staff"""
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_201_CREATED,
            "Support team member added successfully",
            serializer.data
        )
    

class SupportTeamUpdateView(GenericAPIView, BaseResponseMixin):
    """Class for user with is_staff flag to create or list all support team"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportTeamSerializer


    def patch(self, request, team_id):
        """API to get all staff"""
        try:
            team = SupportTeam.objects.get(team=team_id)
        except SupportTeam.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Team member with this id not found"
            )
        
        serializer = self.get_serializer(
            team,
            data=request.data,
            context={'request': request},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_201_CREATED,
            "Support team member status upgraded successfully",
            serializer.data
        )


class RetrieveAllStaffView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve all staff name from db"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = StaffSerializer

    def get(self, request):
        """API to fetch all users with is_staff flag"""
        staff = CustomUser.objects.filter(is_staff=True)

        serializers = self.get_serializer(staff, many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "All staff returned successfully",
            serializers.data
        )
    

class SupportTeamNameAPIView(GenericAPIView, BaseResponseMixin):
    """Class to retrieve all support team"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportTeamNameSerializer


    def get_queryset(self):
        return SupportTeam.objects.all()

    def get(self, request):
        """Get method to retrieve all support team"""
        query = self.get_queryset()

        serializer = self.get_serializer(query, many=True)

        return self.get_response(
            status.HTTP_200_OK,
            "All support team retrieve successfully",
            serializer.data
        )
    

class CreateSupportView(GenericAPIView, BaseResponseMixin):
    """Class to create a support ticket by user"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportSerializer


    def post(self, request):
        """
        Method to create a support ticket by customers
        """
        serializer = self.get_serializer(  
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "Support ticket created successfully",
            serializer.data
        )
   

class UpdateSupportView(GenericAPIView, BaseResponseMixin):
    """Class to update the support ticket by staff"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportSerializer


    def patch(self, request, support_id):
        """
        Method to partially update the support ticket
        Depending on the status by admin
        """
        value = validate_uuid(support_id)
        try:
            support = Support.objects.get(id=value)
        except Support.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Support request not found"
            )
        
        serializer = self.get_serializer(
            support,
            data=request.data,
            context={'request': request},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "Support ticket status updated successfully",
            serializer.data
        )
    

class SingleSupportView(GenericAPIView, BaseResponseMixin):
    """Class to update the support ticket by staff"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportSerializer


    def get(self, request, support_id):
        """
        Method to retrieve a single support ticket
        """
        value = validate_uuid(support_id)
        try:
            support = Support.objects.get(id=value)
        except Support.DoesNotExist:
            return self.get_response(
                status.HTTP_404_NOT_FOUND,
                "Support request not found"
            )
        
        serializer = self.get_serializer(support)

        return self.get_response(
            status.HTTP_200_OK,
            "Support ticket retrieved successfully",
            serializer.data
        )
    

class SingleSupportTeamView(GenericAPIView, BaseResponseMixin):
    """Class to view a single support team data"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = SupportTeamSerializer


    def get(self, request, team_id):
        """Retrieve a single support team data"""
        if not team_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Please provide team member id"
            )
        
        value = validate_uuid(team_id)

        try:
            support_team = SupportTeam.objects.get(team=value)
        except SupportTeam.DoesNotExist:
            return self.get_response(
                status.HTTP_200_OK,
                "Support team member with this uuid does not exists",
            )
        
        serializer = self.get_serializer(support_team)

        return self.get_response(
            status.HTTP_200_OK,
            "Support team data retrieve successfully",
            serializer.data
        )
    

class SingleSupportTicketView(GenericAPIView, BaseResponseMixin):
    """
    Class to retrieve a single support ticket data
    """
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = TicketsSerializer

    def get(self, request, ticket_id):
        """Retrive a single support ticket data"""
        if not ticket_id:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "Please provide the support id"
            )
        
        value = validate_uuid(ticket_id)

        try:
            ticket = Tickets.objects.get(id=value)
        except Tickets.DoesNotExist:
            return self.get_response(
                status.HTTP_400_BAD_REQUEST,
                "No ticket found with this id"
            )
        
        serializer = self.get_serializer(ticket)

        return self.get_response(
            status.HTTP_200_OK,
            "Ticket data retrieved successfully",
            serializer.data
        )


class AllTicketsListView(GenericAPIView, BaseResponseMixin):
    """
    API endpoint to list all tickets with optional filtering
    """
    # Disable all authentication backends
    pagination_class = StandardResultsSetPagination
    serializer_class = TicketsSerializer
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]

    def get_queryset(self):
        return Tickets.objects.all()

    def get(self, request, *args, **kwargs):
        """Get all tickets with optional filtering"""
        # Get query parameters
        ticket_status = request.query_params.get('status')
        ticket_type = request.query_params.get('type')
        ticket_state = request.query_params.get('state')
        assigned = request.query_params.get('assigned')
        created = request.query_params.get('date')


        queryset = self.get_queryset()
    
        query = Q()
    
        if ticket_status:
            query &= Q(status__iexact=ticket_status)

        if ticket_type:
            query &= Q(ticket_type__iexact=ticket_type)
        if ticket_state:
            query &= Q(ticket_state__iexact=ticket_state)

        if assigned:
            query &= (
                Q(assigned_to__exact=assigned) | 
                Q(re_assigned_to__exact=assigned)
            )

        if created:
            query &= Q(created_at__icontains=created)

        # Apply filter to queryset
        filtered_queryset = queryset.filter(query).order_by("-created_at")

        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data["status"] = "success"
            paginated_response.data["status_code"] = status.HTTP_200_OK
            paginated_response.data["message"] = "Tickets retrieved successfully"
            return paginated_response
        
        # no pagination
        serializer = self.get_serializer(filtered_queryset, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            "Tickets retrieved successfully",
            serializer.data
        )
    

class UpdateTicketView(GenericAPIView, BaseResponseMixin):
    """Class to update the ticket by staff"""
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]
    serializer_class = TicketsUpdateSerializer


    def patch(self, request, ticket_id):
        """
        Method to partially update the support ticket
        Depending on the status by admin
        """
        value = validate_uuid(ticket_id)

        ticket = get_object_or_404(Tickets, id=value)

        serializer = self.get_serializer(
            ticket,
            data=request.data,
            context={'request': request},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self.get_response(
            status.HTTP_200_OK,
            "Ticket updated successfully",
            serializer.data
        )



class SupportMessageListCreateView(GenericAPIView, BaseResponseMixin):
    """
    View to list and create support messages under a specific support thread
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAdminUser]
    authentication_classes = [CookieTokenAuthentication]

    def get_support(self):
        """Helper to retrieve the support instance"""
        ticket_id = self.kwargs.get("pk")
        type = self.request.query_params.get("type")
        if type == "returns":
            return get_object_or_404(OrderReturnRequest, id=ticket_id)
        else:
            return get_object_or_404(Support, id=ticket_id)

    def get_queryset(self):
        support = self.get_support()
        print(f"Support object: {support} ({support.__class__.__name__})")

        if isinstance(support, OrderReturnRequest):
            return Message.objects.filter(
                content_type=ContentType.objects.get_for_model(OrderReturnRequest),
                object_id=support.id
            ).order_by("sent_at")
        elif isinstance(support, Support):
            return Message.objects.filter(
                content_type=ContentType.objects.get_for_model(Support),
                object_id=support.id
            ).order_by("sent_at")
        else:
            return Message.objects.none()


    def get(self, request, pk):
        """List all messages for a support thread"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return self.get_response(
            status.HTTP_200_OK,
            "Messages retrieved successfully",
            serializer.data
        )

    def post(self, request, pk):
        """Create a new message under a support thread"""
        support = self.get_support()
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request, "support": support}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            content_type=ContentType.objects.get_for_model(Support),
            object_id=support.id,
            parent=support
        )
        return self.get_response(
            status.HTTP_201_CREATED,
            "Message created successfully",
            serializer.data
        )



class SupportEmailWebhookView(APIView, BaseResponseMixin):
    """Webhook to retrieve and ingest customers messages"""
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """
        Mailgun webhook to handle the retrieval and saving
        of customer emails for support request
        """
        from .utils import extract_reply_body

        sender = request.data.get("sender")
        recipient = request.data.get("recipient")
        subject = request.data.get("subject")
        body_plain = request.data.get("body-plain")
        clean_body = extract_reply_body(body_plain)
        attachments = request.FILES 

        # Try to find the customer in the system
        try:
            customer = get_or_create_temp_user(email=sender)
        except CustomUser.DoesNotExist:
            pass

        match = re.search(r"\[(SUP|RET)-[A-Z0-9]{8}\]", subject)
        print(f"Match: {match}")
        print(f"Subject: {subject}")

        if match:
            reference = match.group(0).strip("[]")

            print(f"Reference: {reference}")

            # Try to find an existing ticket with that reference
            support_ticket = Support.objects.filter(
                email=sender, subject__icontains=F("subject"), reference=reference
            ).first()
            print(f"Support ticket: {support_ticket}")

        else:
            # No reference → always create a brand new ticket
            support_ticket = Support.objects.create(
                customer=customer if customer else None,
                email=sender,
                subject=subject,
                body=clean_body,
                status=Support.Status.PENDING,
                source=Support.Source.EMAIL,
            )

        # Save message against the ticket
        msg = Message.objects.create(
            parent=support_ticket,
            sender=support_ticket.customer,
            subject=subject,
            team_email=recipient,
            body=clean_body,
            sent_at=now(),
        )

        # Handle attachments
        if attachments:
            handle_mailgun_attachments(attachments, msg)

        # Notifications only if ticket already exists and is assigned
        try:
            ticket = Tickets.objects.get(
                content_type=ContentType.objects.get_for_model(Support),
                object_id=support_ticket.id,
            )
            if ticket.ticket_state == Tickets.State.ASSIGNED:
                if ticket.re_assigned:
                    Notification.objects.create(
                        user=ticket.re_assigned_to.team,
                        type=Notification.Type.SUPPORT,
                        channel=Notification.ChannelChoices.INAPP,
                        subject=subject,
                        message=clean_body,
                        content_type=ContentType.objects.get_for_model(Message),
                        parent=msg,
                        object_id=msg.id,
                    )
                else:
                    Notification.objects.create(
                        user=ticket.assigned_to.team,
                        type=Notification.Type.SUPPORT,
                        channel=Notification.ChannelChoices.INAPP,
                        subject=subject,
                        message=clean_body,
                        content_type=ContentType.objects.get_for_model(Message),
                        object_id=msg.id,
                    )
        except Tickets.DoesNotExist:
            pass

        return Response(
            {"status": "ok", "message_id": msg.id},
            status=status.HTTP_201_CREATED,
        )
