from rest_framework import serializers
from .models import Support, SupportTeam, Tickets, Message, SupportAttachment
from users.serializers import CustomUserSerializer
from orders.serializers import OrderReturnRequestSerializer
from users.models import CustomUser
from rest_framework.exceptions import ValidationError
from django.utils.timezone import now
from django.db import transaction
from orders.models import OrderReturnRequest
from django.contrib.contenttypes.models import ContentType
from .utils import create_message_for_instance


class SupportAttachmentSerializer(serializers.ModelSerializer):
    """serializer to serialize Support Attachment model"""
    class Meta:
        model = SupportAttachment
        fields = ["id", "message", "url", "alt"]
        extra_kwargs = {
            "message": {"read_only": True}  # not required on input
        }


class SupportSerializer(serializers.ModelSerializer):
    """serializer to serialize Support model"""
    customer = CustomUserSerializer(required=False)
    status = serializers.CharField(required=False)
    attachments = SupportAttachmentSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Support
        fields = [
            "id", "customer", "email", "subject", "body", "reference",
            "attachments", "status", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "email"]


    def validate_status(self, value):
        # normalize
        value = value.strip().lower()

        allowed_statuses = [
            Support.Status.PROCESSING.lower(),
            Support.Status.UNRESOLVED.lower(),
            Support.Status.RESOLVED.lower(),
        ]

        if value not in allowed_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Allowed values: {', '.join(allowed_statuses)}"
            )

        return value
    
    def create(self, validated_data):
        """Override create method"""
        attachment_data = validated_data.pop("attachments", [])
        request = self.context["request"]
        validated_data["customer"] = request.user
        validated_data["email"] = request.user.email

        # Create support
        support = Support.objects.create(**validated_data)

        #Pass attachments to signal via context
        support._attachments_data = attachment_data
        transaction.on_commit(lambda: create_message_for_instance(support))

        return support
    

    def update(self, instance, validated_data):
        status_value = validated_data["status"]

        # statuses that must pass through processing first
        must_pass_through_processing = [
            Support.Status.RESOLVED.lower(),
            Support.Status.UNRESOLVED.lower(),
        ]

        # Get current status
        print(f"ID: {instance.id}")
        support_stat = Support.objects.get(id=instance.id)
        print(f"support stat: {support_stat}")


        # must pass through processing
        print(f"Current status: {support_stat.status}")
        if status_value in must_pass_through_processing and support_stat.status != Support.Status.PROCESSING:
            raise serializers.ValidationError("The ticket must be in processing state first")

        instance.status = status_value
        instance.updated_at = now()
        instance.save(update_fields=["status", "updated_at"])

        return instance



class SupportTeamSerializer(serializers.ModelSerializer):
    """Serializer to serialize Support Team Model"""
    email = serializers.EmailField(read_only=True)
    name = serializers.CharField(read_only=True)

    class Meta:
        model = SupportTeam
        fields = [
            "team", "name", "email", "current_tickets", "is_lead",
            "completed_tickets", "total_tickets", "added_at", "last_completed"
        ]

    def validate_team(self, team):
        # Ensure the user exists and is a staff
        if not team.is_staff:
            raise serializers.ValidationError(
                "The user is not a staff and can't be added as a Support Team"
            )
        return team

    def create(self, validated_data):
        # Automatically set the email from the linked user
        request = self.context["request"]
        validated_data["email"] = validated_data["team"].email
        validated_data["name"] = validated_data["team"].full_name
        if validated_data["is_lead"] and not request.user.is_superuser:
            raise serializers.ValidationError(
                f"YOnly super admin can assign a team lead"
            )
        return super().create(validated_data)
    

    def update(self, instance, validated_data):
        request = self.context["request"]

        # Only allow 'is_lead' field to be updated
        allowed_fields = {"is_lead"}
        if set(validated_data.keys()) != allowed_fields:
            raise serializers.ValidationError(
                "You are not allowed to update anything else except 'is_lead'."
            )

        # Only allow superusers to change is_lead        
        if not request.user.is_superuser:
            raise serializers.ValidationError(
                "Only super admin can assign a team lead."
            )
        instance.is_lead = validated_data["is_lead"]

        instance.save()
        return instance


class SupportTeamNameSerializer(serializers.ModelSerializer):
    """Serializes only the name and email of the support team""" 

    class Meta:
        model = SupportTeam
        fields = ["team", "name", "email", "is_lead"] 


class TicketsSerializer(serializers.ModelSerializer):
    """Serializer to serialize ticket model"""
    ticket_data = serializers.SerializerMethodField()
    assigned_to = SupportTeamSerializer()
    re_assigned_to = SupportTeamSerializer()

    class Meta:
        model = Tickets
        fields = [
            "id", "ticket_type", "ticket_state", "ticket_data",
            "assigned_to", "re_assigned", "re_assigned_to", "status",
            "assigned_at", "re_assigned_at", "updated_at"
        ]

    def get_ticket_data(self, obj):
        """Dynamically serialize the linked object based on its type"""
        if not obj.parent:
            return None

        # Determine the type of the linked object
        model_class = obj.parent.__class__
        print(f"Check model class: {model_class}")
        if model_class.__name__ == "Support":
            from .serializers import SupportSerializer
            return SupportSerializer(obj.parent).data
        elif model_class.__name__ == "OrderReturnRequest":
            from orders.serializers import OrderReturnRequestSerializer
            return OrderReturnRequestSerializer(obj.parent).data
        else:
            return None

    


class TicketsUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Ticket"""
    # Read-only nested output
    assigned_to = SupportTeamSerializer(read_only=True)
    re_assigned_to = SupportTeamSerializer(read_only=True)

    # Write-only inputs
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=SupportTeam.objects.all(), required=False, write_only=True
    )
    re_assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=SupportTeam.objects.all(), required=False, write_only=True
    )
    status = serializers.CharField(required=False)
    ticket_state = serializers.CharField(required=False)

    class Meta:
        model = Tickets
        fields = [
            "id", "ticket_type", "ticket_state", "assigned_to", "re_assigned",
            "re_assigned_to", "status", "assigned_at",
            "re_assigned_at", "updated_at",
            # write-only fields:
            "assigned_to_id", "re_assigned_to_id",
        ]
        read_only_fields = ["id", "assigned_at", "re_assigned_at", "updated_at", "ticket_type"]

    # --- validators: normalize and enforce choices (case-insensitive) ---

    def validate_status(self, value):
        v = value.strip().lower()
        allowed = [c[0] for c in Tickets.Status.choices]  # ["processing", "completed"]
        if v not in allowed:
            raise serializers.ValidationError(f"Invalid status. Allowed values: {', '.join(allowed)}")
        return v

    def validate_ticket_state(self, value):
        v = value.strip().lower()
        allowed = [c[0] for c in Tickets.State.choices]  # ["assigned","unassigned"]
        if v not in allowed:
            raise serializers.ValidationError(f"Invalid ticket state. Allowed values: {', '.join(allowed)}")
        return v

    def _require_lead(self, request_user):
        try:
            staff = SupportTeam.objects.get(team=request_user)
        except SupportTeam.DoesNotExist:
            raise serializers.ValidationError("The user is not a support team")
        # if not getattr(staff, "is_lead", False):
        #     raise serializers.ValidationError("You are not authorized to assign or reassign tickets")
        return staff

    @transaction.atomic
    def update(self, instance, validated_data):
        # Pull write-only inputs
        new_assignee = validated_data.pop("assigned_to_id", None)
        new_reassignee = validated_data.pop("re_assigned_to_id", None)

        # Normalize strings if provided
        status_value = validated_data.get("status", None)
        ticket_state_value = validated_data.get("ticket_state", None)

        request = self.context.get("request")

        # --- Assignment / state rules ---

        # If trying to assign/reassign or change state, caller must be a lead support staff
        if new_assignee or new_reassignee or ticket_state_value:
            print(f"Staff: {request.user} \nName: {request.user.full_name}")
            self._require_lead(request.user)

        # Cannot reassign if never assigned
        if new_reassignee and not instance.assigned_to:
            raise serializers.ValidationError("You cannot reassign a ticket that was never assigned")

        # If ticket_state is being set to assigned, ensure an assignee is provided in this request
        if ticket_state_value and ticket_state_value == Tickets.State.ASSIGNED and not (new_assignee or new_reassignee):
            raise serializers.ValidationError("You cannot set ticket_state=assigned without assigning the ticket")

        # Apply initial assignment
        if new_assignee:
            # First-time assignment or same assignee
            instance.assigned_to = new_assignee
            instance.assigned_at = now()
            instance.ticket_state = Tickets.State.ASSIGNED
            instance.updated_at = now()
            if hasattr(new_assignee, "current_tickets"):
                new_assignee.current_tickets = (new_assignee.current_tickets or 0) + 1
            if hasattr(new_assignee, "total_tickets"):
                new_assignee.total_tickets = (new_assignee.total_tickets or 0) + 1
            new_assignee.added_at = now()
            new_assignee.save(update_fields=["current_tickets", "total_tickets", "added_at"])
            instance.save(update_fields=["assigned_to", "assigned_at", "updated_at", "ticket_state"])

        # Explicit reassignment path via re_assigned_to_id
        if new_reassignee:
            if instance.assigned_to and instance.assigned_to != new_reassignee:
                # decrement old assignee
                old = instance.assigned_to
                if hasattr(old, "current_tickets"):
                    old.current_tickets = max(0, (old.current_tickets or 0) - 1)
                    old.save(update_fields=["current_tickets"])

                instance.re_assigned = True
                instance.re_assigned_to = new_reassignee
                instance.re_assigned_at = now()
                instance.updated_at = now()

                if hasattr(new_reassignee, "current_tickets"):
                    new_reassignee.current_tickets = (new_reassignee.current_tickets or 0) + 1
                if hasattr(new_reassignee, "total_tickets"):
                    new_reassignee.total_tickets = (new_reassignee.total_tickets or 0) + 1
                new_reassignee.added_at = now()
                new_reassignee.save(update_fields=["current_tickets", "total_tickets", "added_at"])
                instance.save(update_fields=["re_assigned", "re_assigned_to", "re_assigned_at", "updated_at"])

        # ticket_state change
        if ticket_state_value:
            instance.ticket_state = ticket_state_value
            instance.updated_at = now()
            instance.save(update_fields=["ticket_state", "updated_at"])

        # --- Status rules ---

        if status_value:
            # must be assigned before processing
            if status_value == Tickets.Status.PROCESSING and not instance.assigned_to:
                raise serializers.ValidationError("Ticket must be assigned before it can be processed")

            # must pass through processing before completed
            if status_value == Tickets.Status.COMPLETED and instance.status != Tickets.Status.PROCESSING:
                raise serializers.ValidationError("The ticket must be in processing state first")

            # apply status
            instance.status = status_value
            instance.updated_at = now()
            instance.save(update_fields=["status", "updated_at"])

        return instance


class StaffSerializer(serializers.ModelSerializer):
    """Serializers for staff, showing only name and email"""

    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "email"]


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Support messages between staff and customers"""
    sender = CustomUserSerializer(required=False)
    attachments = SupportAttachmentSerializer(many=True, required=False)

    class Meta:
        model = Message
        fields = [
            "id", "sender", "from_staff", "subject",
            "content_type", "object_id", "body", "attachments", "sent_at"
        ]
        read_only_fields = ["sender", "from_staff", "content_type", "object_id", "sent_at"]


    def create(self, validated_data):
        request = self.context.get("request")
        support = self.context.get("support")   # passed from Support view
        return_obj = self.context.get("return") # passed from Return view
        print(f"User auth: {request.user.is_authenticated}")
        print(f"User: {request.user}")

        # Attach sender info
        if request and request.user.is_authenticated:
            validated_data["sender"] = request.user
            validated_data["from_staff"] = request.user.is_staff
            validated_data["team_email"] = request.user.email

        subject = None

        # Handle Support context
        if support:
            validated_data["content_type"] = ContentType.objects.get_for_model(Support)
            validated_data["object_id"] = support.id
            validated_data["parent"] = support

            # Maintain subject with "Re:" prefix if replying
            last_message = Message.objects.filter(
                content_type=ContentType.objects.get_for_model(Support),
                object_id=support.id
            ).order_by("-sent_at").first()

            if last_message and last_message.subject:
                if last_message.subject.startswith("Re:"):
                    subject = last_message.subject
                else:
                    subject = f"Re: {last_message.subject}"
            else:
                subject = f"Support #{support.id}"

        # Handle Return context
        elif return_obj:
            validated_data["content_type"] = ContentType.objects.get_for_model(type(return_obj))
            validated_data["object_id"] = return_obj.id
            validated_data["parent"] = return_obj

            last_message = Message.objects.filter(
                content_type=ContentType.objects.get_for_model(type(return_obj)),
                object_id=return_obj.id
            ).order_by("-sent_at").first()

            if last_message and last_message.subject:
                if last_message.subject.startswith("Re:"):
                    subject = last_message.subject
                else:
                    subject = f"Re: {last_message.subject}"
            else:
                subject = f"Return #{return_obj.id}"

        else:
            raise ValueError("Neither support nor return context was provided to MessageSerializer.")

        validated_data["subject"] = subject

        # Handle attachments
        attachments_data = validated_data.pop("attachments", [])
        message = Message.objects.create(**validated_data)

        for attachment in attachments_data:
            SupportAttachment.objects.create(message=message, **attachment)

        return message

    
