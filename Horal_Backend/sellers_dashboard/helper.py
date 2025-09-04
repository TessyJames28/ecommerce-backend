from datetime import date, timedelta
from rest_framework.exceptions import ValidationError
import uuid

def get_day_start(d: date) -> date:
    return d

def get_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

def get_month_start(d: date) -> date:
    return d.replace(day=1)

def get_year_start(d: date) -> date:
    return d.replace(month=1, day=1)


def validate_uuid(value):
    """Function to handle id validation"""
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise ValidationError("Invalid ID format. Must be a valid UUID.")

    return value
