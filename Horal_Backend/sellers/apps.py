from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class SellersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sellers'

    def ready(self):
        import sellers.signals
