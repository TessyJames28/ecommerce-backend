from decimal import Decimal


def apply_coupon_discount(order, discount_amount=3000):
    """
    Apply a fixed discount to the product cost only.
    Shipping cost remains unchanged.

    Args:
        order (Order): The order instance to apply the discount on.
        discount_amount (Decimal | float | int): Amount to deduct.

    Returns:
        Order: Updated order instance.
    """
    discount_amount = Decimal(discount_amount)
    if discount_amount < 0:
        raise ValueError("Discount amount cannot be negative")
    
    # Ensure we don't substract more than product total
    discount_amount = min(discount_amount, order.product_total)

    # Apply discount
    order.product_total -= discount_amount
    order.total_amount = order.total_amount - discount_amount
    order.discount_applied = True
    order.save(update_fields=["product_total", "total_amount", "discount_applied"])

    return order
     