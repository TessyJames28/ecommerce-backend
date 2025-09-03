from django.db.models.signals import post_save
from .models import Tickets, Support, Message, SupportTeam
from orders.models import OrderReturnRequest
from django.dispatch import receiver
from .tasks import send_support_email
from django.utils.timezone import now
from django.contrib.contenttypes.models import ContentType
from .utils import (
    generate_received_subject
)
from notifications.tasks import send_email_task
from notifications.models import Notification
from users.models import CustomUser
from django.conf import settings
import re


@receiver(post_save, sender=Support)
def create_ticket_for_support(sender, instance, created, **kwargs):
    print("Triggered")
    if created and instance.status == "pending":
        # Only create if no ticket exists
        if not hasattr(instance, "support_ticket"):
            Tickets.objects.create(
                ticket_type=Tickets.TicketType.SUPPORT,
                parent=instance,
                content_type=ContentType.objects.get_for_model(Support),
                object_id=instance.id
            )

@receiver(post_save, sender=OrderReturnRequest)
def create_ticket_for_return(sender, instance, created, **kwargs):
    if created and instance.status == "requested":
        # Only create if no ticket exists
        if not hasattr(instance, "return_ticket"):
            Tickets.objects.create(
                ticket_type=Tickets.TicketType.RETURNS,
                parent=instance,
                content_type=ContentType.objects.get_for_model(OrderReturnRequest),
                object_id=instance.id
            )


@receiver(post_save, sender=Message)
def send_support_email_signal(sender, instance, created, **kwargs):
    """Signal to send email when staff replies to a support or return ticket"""
    if not created or not instance.from_staff:
        # Only send emails for staff messages
        return
    
    related_obj = instance.parent
    if not related_obj:
        print(f"No related object found for message {instance.id}")
        return

    # Determine recipient based on related object type
    if isinstance(related_obj, Support):
        user_obj = related_obj.customer
        email = related_obj.email or (user_obj.email if user_obj else None)
        name = user_obj.full_name if user_obj else ""
        ticket_type = "support"
    elif isinstance(related_obj, OrderReturnRequest):
        user_obj = related_obj.order_item.order.user
        email = user_obj.email
        name = user_obj.full_name
        ticket_type = "returns"
    else:
        print(f"Unsupported GFK type for message {instance.id}")
        return

    if not email:
        print(f"No email found for message {instance.id}")
        return

    # Get all messages for the current thread
    messages_in_thread = Message.objects.filter(
        content_type=ContentType.objects.get_for_model(type(related_obj)),
        object_id=related_obj.id
    ).order_by("sent_at")

    # Look for the latest subject containing the reference pattern
    ref_subject = None
    ref_pattern = r"\[(SUP|RET)-[A-Z0-9]{8}\]"

    for msg in reversed(messages_in_thread):
        if msg.subject and re.search(ref_pattern, msg.subject):
            ref_subject = msg.subject
            print(f"Ref subject from loop: {ref_subject}")
            break

    # Fallback to the latest message subject or generic if no ref found
    if not ref_subject:
        ref_subject = messages_in_thread.last().subject if messages_in_thread.exists() else "Support Request"
        print(f"Ref subject if none from loop: {ref_subject}")
    # Use this subject for the outgoing staff email
    subject_to_use = ref_subject
    print(f"Subject to use: {subject_to_use}")

    # Compose email body (only the new message)
    body = f"Hello {name},\n\n" \
           f"{instance.body}\n\n" \
           "Our team will get back to you shortly.\n\n" \
           "Note: All further correspondence should be on this email thread."

    # Send email asynchronously
    send_support_email.delay(
        to_email=email,
        subject=subject_to_use,
        body=body,
        ticket_type=ticket_type
    )


@receiver(post_save, sender=Support)
def send_support_received_email(sender, instance, created, **kwargs):
    print("Triggered email sending")
    if created:
        if not instance.email:
            print("No email found, skipping sending")
            return
        subject = generate_received_subject(instance)
        body = f"Hello {instance.customer.full_name if instance.customer else ''},\n\n" \
               f"We have received your support request:\n\n{instance.body}\n\n" \
               "Our team will get back to you shortly." \
               "\n\nNote: All further correspondence should be on this email thread."

        from_email = f"support@{settings.MAILGUN_DOMAIN}"
        # Trigger async email
        send_email_task.delay(
            recipient=instance.email,
            subject=subject,
            body=body,
            from_email=f"Support <{from_email}>"
        )
        print(f"Final body to send: {body}")

        # Get sender horal bot

        sender = CustomUser.objects.get(email=from_email)

        # Create the message
        Message.objects.create(
            parent=instance,
            sender=sender,
            subject=subject,
            body=body,
            sent_at=now(),
            from_staff=True,
        )



@receiver(post_save, sender=Tickets)
def update_user_on_processing_status_email(sender, instance, created, **kwargs):
    """
    Signal to update user on changes to their ticket
    Once the assigned team start processing the request
    """
    print("Triggered email sending")
    if created or instance.status != Tickets.Status.PROCESSING:
        return

    # Access the related object via the GFK
    related_obj = instance.parent
    print(f"Related_obj: {related_obj}")
    if not related_obj:
        print(f"No related object found for ticket {instance.id}")
        return

    # Determine user info based on ticket type
    if instance.ticket_type == "returns" and isinstance(related_obj, OrderReturnRequest):
        user_obj = related_obj.order_item.order.user
        name = user_obj.full_name
        email = user_obj.email
        from_email = f"Returns <returns@{settings.MAILGUN_DOMAIN}>"
    elif instance.ticket_type == "support" and isinstance(related_obj, Support):
        print(f"Support related obj: {related_obj}")
        print(f"Support user: {related_obj.customer}")
        user_obj = related_obj.customer if related_obj.customer else None
        name = user_obj.full_name if related_obj.customer else None
        email = related_obj.email
        from_email = f"Support <support@{settings.MAILGUN_DOMAIN}>"
    else:
        print(f"Unsupported ticket type or GFK mismatch for ticket {instance.id}")
        return

    # Send email asynchronously
    subject = generate_received_subject(instance)
    body = f"Hello {name if name else ''},\n\n" \
           f"Our team has picked up your ticket and will update you on the progress\n\n" \
           "\n\nNote: All further correspondence should be on this email thread."
    print(f"from email: {from_email}")
    send_email_task.delay(
        recipient=email,
        subject=subject,
        body=body,
        from_email=from_email
    )


@receiver(post_save, sender=Tickets)
def create_notification(sender, created, instance, **kwargs):
    """Signal to create a notification when a team member is assigned a ticket"""
    if instance.ticket_state != Tickets.State.ASSIGNED:
        return
    
    # # Optionally: check if this was just assigned
    # if not created:
    #     old = sender.objects.get(id=instance.id)
    #     if old.ticket_state == Tickets.State.ASSIGNED:
    #         # Already assigned before, skip
    #         return
    
    user = instance.re_assigned_to.team if instance.re_assigned else instance.assigned_to.team
    
    # Set the right type
    if instance.ticket_type == Tickets.TicketType.RETURNS:
        type = Notification.Type.ORDER_RETURN
    elif instance.ticket_type == Tickets.TicketType.SUPPORT:
        type = Notification.Type.SUPPORT
    

    notification = Notification.objects.create(
        user=user,
        type=type,
        channel=Notification.ChannelChoices.INAPP,
        subject=f"New ticket",
        message=f"You have been assigned a new ticket on '{instance.ticket_type}'",
        content_type=ContentType.objects.get_for_model(Tickets),
        parent=instance,
        object_id=instance.id,
        status=Notification.Status.SENT,  # mark as sent immediately for in-app
    )

    # Optional: log for debugging
    print(f"Notification created and marked as sent: {notification.id}")


@receiver(post_save, sender=Tickets)
def update_support_returns_to_processing(sender, instance, **kwargs):
    """
    Signal to automatically update the support and returns
    status to processing once a ticket status is updated to processing
    """
    if instance.status != Tickets.Status.PROCESSING:
        return
    
    # if setting ticket to completed, underlying object must be done
    # Access the related object via the GFK
    related_obj = instance.parent
    print(f"Related_obj: {related_obj}")
    print(f"Related_obj type: {type(related_obj)}")
    # print(f"instance ticket type: {related_obj.ticket_type}")
    if not related_obj:
        print(f"No related object found for ticket {instance.id}")
        
    # Determine user info based on ticket type
    if instance.ticket_type == "returns" and isinstance(related_obj, OrderReturnRequest):
        returns_obj = related_obj
        print(f"Returns obj: {returns_obj}")
        returns_obj.status = OrderReturnRequest.Status.PROCESSING
        returns_obj.save(update_fields=["status"])
    elif isinstance(related_obj, Support):
        support_obj = related_obj
        print(f"Support obj: {support_obj}")
        support_obj.status = Support.Status.PROCESSING
        support_obj.save(update_fields=["status"])
    else:
        print(f"Unsupported ticket type or GFK mismatch for ticket {instance.id}")
        return
    

@receiver(post_save, sender=OrderReturnRequest)
def update_returns_ticket_status_to_completion(sender, instance, **kwargs):
    """
    Signal to update ticket status to completed
    Once an order return ticket is marked as completed
    after successful refund
    
    or when marked as rejected
    """
    if instance.status not in [
        OrderReturnRequest.Status.COMPLETED,
        OrderReturnRequest.Status.REJECTED,
        OrderReturnRequest.Status.APPROVED
    ]:
        return
    
    # Identify the ticket
    ticket = Tickets.objects.get(
        content_type=ContentType.objects.get_for_model(OrderReturnRequest),
        object_id=instance.id
    )
    
    # Ensure it's the correct ticket
    if ticket.ticket_type == "returns" and ticket.ticket_state == "assigned":
        if instance.status in [
            OrderReturnRequest.Status.REJECTED,
            OrderReturnRequest.Status.COMPLETED
        ]:
            # get assigned team and update ticket
            holder = ticket.re_assigned_to or ticket.assigned_to
            if hasattr(holder, "completed_tickets"):
                holder.completed_tickets = (holder.completed_tickets or 0) + 1
            if hasattr(holder, "current_tickets"):
                holder.current_tickets = max(0, (holder.current_tickets or 0) - 1)
            if hasattr(holder, "last_completed"):
                holder.last_completed = now()
            holder.save(update_fields=["completed_tickets", "current_tickets", "last_completed"])
            ticket.status = Tickets.Status.COMPLETED
            ticket.updated_at = now()
            ticket.save(update_fields=["status", "updated_at"])

    if instance.status == OrderReturnRequest.Status.COMPLETED:
        return
    else:
        # Info customer on the successful resolution of their ticket
        user_obj = instance.order_item.order.user if instance.order_item else None
        name = user_obj.full_name if instance.order_item else None
        email = user_obj.email

        # Get subject from previous messages
        msg = Message.objects.filter(object_id=instance.id).last()


        # Send email asynchronously
        # subject = generate_received_subject(instance)
        subject = msg.subject

        if instance.status == OrderReturnRequest.Status.APPROVED:
            body = f"Hello {name if name else ''},\n\n" \
                f"Your order return request has been approve\n\n" \
                f"We are currently processing payment. You will receive it with" \
                f"7 business days." \
                "\n\nThanks for shopping on Horal. We hope the next shopping experience" \
                "Will be better."
        elif instance.status == OrderReturnRequest.Status.REJECTED:
            body = f"Hello {name if name else ''},\n\n" \
                    f"We are sorry to inform you that order return request has been rejected\n\n" \
                    f"Upon detail review from our team, we found out discrepancies which you" \
                    f"failed to give plausible explanation." \
                    "\n\nThanks for shopping on Horal. We hope the next shopping experience" \
                    "Will be better."

        send_email_task.delay(
            recipient=email,
            subject=subject,
            body=body,
            from_email=f"Returns <returns@{settings.MAILGUN_DOMAIN}>"
        )
        
        
@receiver(post_save, sender=Support)
def update_support_ticket_status_to_completion(sender, instance, **kwargs):
    """
    Signal to update ticket status to completed
    Once support request ticket is marked as resolved
    """
    if instance.status != Support.Status.RESOLVED:
        return
    
    # Identify the ticket
    ticket = Tickets.objects.get(
        content_type=ContentType.objects.get_for_model(Support),
        object_id=instance.id
    )
    
    # Ensure it's the correct ticket
    print(f"Ticket instance: {ticket}")
    if ticket.ticket_type == "support" and ticket.ticket_state == "assigned":
        # get assigned team and update ticket
        holder = ticket.re_assigned_to or ticket.assigned_to
        if hasattr(holder, "completed_tickets"):
            holder.completed_tickets = (holder.completed_tickets or 0) + 1
        if hasattr(holder, "current_tickets"):
            holder.current_tickets = max(0, (holder.current_tickets or 0) - 1)
        if hasattr(holder, "last_completed"):
            holder.last_completed = now()
        holder.save(update_fields=["completed_tickets", "current_tickets", "last_completed"])
        ticket.status = Tickets.Status.COMPLETED
        ticket.updated_at = now()
        ticket.save(update_fields=["status", "updated_at"])

    # Info customer on the successful resolution of their ticket
    user_obj = instance.customer if instance.customer else None
    name = user_obj.full_name if instance.customer else None
    email = instance.email

    # Get subject from previous messages
    msg = Message.objects.filter(object_id=instance.id).last()


    # Send email asynchronously
    # subject = generate_received_subject(instance)
    subject = msg.subject
    body = f"Hello {name if name else ''},\n\n" \
           f"Your ticket has been marked resolved and completed\n\n" \
           "\n\nPlease take a moment to rate your experience."

    send_email_task.delay(
        recipient=email,
        subject=subject,
        body=body,
        from_email=f"Support <support@{settings.MAILGUN_DOMAIN}>"
    )

    # Delete user if a temporary user after ticket resolution
    if user_obj.is_temporary:
        user_obj.delete()


@receiver(post_save, sender=Support)
def notify_team_lead_of_unresolved_ticket(sender, instance, **kwargs):
    """
    Signal to notify the team lead of unresolved request ticket
    To either reassign the ticket or handle it by their self
    """
    print("Triggered for unresolved")
    if instance.status != Support.Status.UNRESOLVED:
        return
    
    # Get the team lead and team member in charge of the ticket
    lead = SupportTeam.objects.filter(
        is_lead=True
    ).first()
    print(f"Lead team: {lead}")

    # Identify the ticket and team in charge
    ticket = Tickets.objects.get(
        content_type=ContentType.objects.get_for_model(Support),
        object_id=instance.id
    )
    
    holder = ticket.re_assigned_to or ticket.assigned_to
    subject = f"Unresolved ticket for support request: {ticket.id}"
    body = f"Hello {lead.name}\n\n" \
            f"There is an unresolved support ticket for ticket" \
            f"{ticket.id} marked as unresolved by team member: {holder.name}" \
            f"\nPlease proceed to reassign the ticket to someone with higher" \
            f"authority or handle it yourself.\n\n" \
            f"Thanks"
    
    print("About to send notification")
    # Notify team lead:
    Notification.objects.create(
        user=lead.team,
        type=Notification.Type.SUPPORT,
        subject=subject,
        message=body,
        content_type=ContentType.objects.get_for_model(Support),
        parent=instance,
        object_id=instance.id,
        status=Notification.Status.SENT,
    )

