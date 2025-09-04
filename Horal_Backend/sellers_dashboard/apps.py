from django.apps import AppConfig


class SellersDashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sellers_dashboard'


    def ready(self):
        import sellers_dashboard.signals
