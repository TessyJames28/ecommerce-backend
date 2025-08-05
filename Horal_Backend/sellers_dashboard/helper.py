from datetime import date, timedelta

def get_day_start(d: date) -> date:
    return d

def get_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

def get_month_start(d: date) -> date:
    return d.replace(day=1)

def get_year_start(d: date) -> date:
    return d.replace(month=1, day=1)
