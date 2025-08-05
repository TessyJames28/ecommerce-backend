from django.core.management.base import BaseCommand
from sellers_dashboard.periodic_tasks import setup_all_tasks

class Command(BaseCommand):
    help = "Set up periodic Celery Beat tasks"

    def handle(self, *args, **kwargs):
        setup_all_tasks()
        self.stdout.write(self.style.SUCCESS("Celery Beat tasks scheduled!"))
