from django_celery_beat.models import (
    PeriodicTask, CrontabSchedule,
    IntervalSchedule
)
import json

location = 'sellers_dashboard.tasks.'
order_location = 'orders.tasks.'

def setup_hourly_task():
    """Run every hour: populate shop sales"""
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute='*/15',
        hour='*',
        day_of_month='*',
        month_of_year='*',
    )

    # Register the periodic task
    PeriodicTask.objects.get_or_create(
        name="Populate daily shop sales and daily time series",
        defaults={
            "task": f'{location}populate_daily_shop_sales',
            'interval': schedule,
            'enabled': True
        },
    )

    PeriodicTask.objects.update_or_create(
        name="Aggregate Daily Sales",
        defaults={
            'task': f'{location}aggregate_daily_sales',
            'crontab': schedule,
            'enabled': True
        }
    )


def setup_order_expiration_task():
    """Run every hour: populate shop sales"""
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=30,
        period=IntervalSchedule.MINUTES
    )

    # Register the periodic task
    PeriodicTask.objects.get_or_create(
        name="Expire Pending Orders",
        defaults={
            "task": f'{order_location}expire_pending_orders_task',
            'interval': schedule,
            'enabled': True
        },
    )


def setup_simulation_task():
    """
    Run every 1 hour:
        simulate hourly orders purchased by buyers
    """
    schedule, _ = CrontabSchedule.objects.get_or_create(
        hour='1-23',
        minute='0',
        day_of_month='*',
        month_of_year='*',
    )

    PeriodicTask.objects.update_or_create(
        name="Set up simulation tasks",
        defaults={
            'task': f'{location}simulate_hourly_order',
            'crontab': schedule,
            'enabled': True
        }
    )


def setup_weekly_task():
    """
    Run every 2 hours:
        populate time series
        poulate shop sales
    """
    schedule, _ = CrontabSchedule.objects.get_or_create(
        hour='2,4,6,8,10,12,14,16,18,20,22',
        minute='0',
        day_of_month='*',
        month_of_year='*',
    )

    PeriodicTask.objects.update_or_create(
        name="Aggregate Weekly Sales",
        defaults={
            'task': f'{location}aggregate_weekly_sales',
            'crontab': schedule,
            'enabled': True
        }
    )

    PeriodicTask.objects.update_or_create(
        name="Populate Weekly Time Series",
        defaults={
            'task': f'{location}populate_weekly_shop_sales',
            'crontab': schedule,
            'enabled': True
        }
    )


def setup_monthly_task():
    """
    Run every 4 hours:
        populate time series
        aggregate shop sales
    """
    schedule, _ = CrontabSchedule.objects.get_or_create(
        hour='4,8,12,16,20',
        minute='0',
        day_of_month='*',
        month_of_year='*',
    )

    PeriodicTask.objects.update_or_create(
        name="Aggregate Monthly Sales",
        defaults={
            'task': f'{location}aggregate_monthly_sales',
            'crontab': schedule,
            'enabled': True
        }
    )

    PeriodicTask.objects.update_or_create(
        name="Populate Monthly Time Series",
        defaults={
            'task': f'{location}populate_monthly_shop_sales',
            'crontab': schedule,
            'enabled': True
        }
    )


def setup_yearly_task():
    """
    Run every 7 hours:
        populate time series
        aggregate shop sales
    """
    schedule, _ = CrontabSchedule.objects.get_or_create(
        hour='7,14,21',
        minute='0',
        day_of_month='*',
        month_of_year='*',
    )

    PeriodicTask.objects.update_or_create(
        name="Aggregate Yearly Sales",
        defaults={
            'task': f'{location}aggregate_yearly_sales',
            'crontab': schedule,
            'enabled': True
        }
    )

    PeriodicTask.objects.update_or_create(
        name="Populate Yearly Time Series",
        defaults={
            'task': f'{location}populate_yearly_shop_sales',
            'crontab': schedule,
            'enabled': True
        }
    )


def setup_all_tasks():
    setup_hourly_task()
    setup_weekly_task()
    setup_monthly_task()
    setup_yearly_task()
    setup_simulation_task()
    setup_order_expiration_task()

