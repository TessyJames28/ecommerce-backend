import logging
from celery import Task
from celery.exceptions import OperationalError as CeleryOperationalError
from kombu.exceptions import OperationalError as KombuOperationalError
import redis

logger = logging.getLogger(__name__)

_original_delay = Task.delay

def safe_delay(self, *args, **kwargs):
    try:
        return _original_delay(self, *args, **kwargs)
    except (CeleryOperationalError, KombuOperationalError, redis.exceptions.ConnectionError) as e:
        logger.error(
            f"[SafeCelery] Failed to enqueue task {self.name}: {e}",
             exc_info=True  # includes traceback in logs
        )
        return {"status": "failed", "reason": str(e)}

Task.delay = safe_delay


import os
from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "Horal_Backend.settings"
)

app = Celery("Horal_Backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
