from payment.utils import get_bank_code
from django.conf import settings
import requests
from rest_framework.exceptions import ValidationError
from .models import Payout
from users.models import CustomUser
from shops.models import Shop
import uuid
from sellers_dashboard.utils import get_withdrawable_revenue
from django.utils.timezone import now
from decimal import Decimal
import os, random



def verify_bank_account(account_number, bank_code):
    """
    Function to verify sellers bank details on paystack
    """
    url = f"{settings.PAYSTACK_BASE_URL}/bank/resolve"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    params = {
        "account_number": account_number,
        "bank_code": bank_code
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
    except Exception as e:
        raise Exception(f"Error verifying bank on paystack: {e}")

    if data.get("status") is True:
        return data["data"]["account_name"]
    else:
        return None


def create_transfer_recipient(name, account_number, bank_code):
    """
    Function to create transfer recipient on paystack
    """
    url = f"{settings.PAYSTACK_BASE_URL}/transferrecipient"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
    except Exception as e:
        raise ValidationError(f"Error creating transfer receipient: {e}")
    
    if data.get("status") is True:
        return data["data"]["recipient_code"]
    else:
        raise ValidationError(f"Failed to create trasfer recipient: {data}")


def initiate_payout(recipient_code, seller, amount_kobo=None, payout=None, reason="Payout"):
    """
    Function to handle the initialization of seller's payout
    """

    url = f"{settings.PAYSTACK_BASE_URL}/transfer"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    if amount_kobo is not None:
        # Use the provided amount for retries
        amount_naira = (Decimal(amount_kobo) / Decimal(100)).quantize(Decimal("0.01"))
        if payout and isinstance(payout, Payout):
            withdrawable = payout.total_withdrawable
            commission = payout.commission
        else:
            withdrawable = None
            commission = None
    else:
        user = CustomUser.objects.get(id=seller.id)
        shop = Shop.objects.get(owner=user.kyc)
        withdrawable = get_withdrawable_revenue(shop.id)

        if withdrawable <= 0:
            raise ValidationError("No withdrawable balance available.")

        withdrawable = Decimal(str(withdrawable))
        commission = (withdrawable * Decimal("0.05")).quantize(Decimal("0.01"))
        amount_naira = withdrawable - commission

    payload = {
        "source": "balance",
        "amount": int(amount_naira * 100),
        "recipient": recipient_code,
        "reason": reason,
        "reference": payout.reference_id if payout else str(uuid.uuid4())  # custom reference
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
    except Exception as e:
        raise Exception(f"Error initializing payout: {e}")

    amount = data.get("data", {}).get("amount")
    if data.get("status") is True:
        transfer_code = data["data"]["transfer_code"]

        # Check if its a retry
        if payout:
            # Update existing payout retry
            payout.paystack_transfer_code = transfer_code
            payout.last_retry_at = now()
            payout.save(update_fields=[
                "paystack_transfer_code", "last_retry_at"
            ])
        else:
            # Save payout record
            Payout.objects.get_or_create(
                seller=seller,
                reference_id=data["data"]["reference"],
                amount_naira=amount / 100,
                paystack_transfer_code=transfer_code,
                total_withdrawable=withdrawable,
                commission=commission,
                status=Payout.StatusChoices.PROCESSING,
                reason=reason
            )

        return transfer_code
    else:
        raise ValidationError(f"Paystack tranfer initiation failed: {data}")
