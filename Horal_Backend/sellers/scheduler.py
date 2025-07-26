from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
from .tasks import verify_seller_kyc

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(verify_seller_kyc.delay, 'interval', minutes=10)
    scheduler.start()
