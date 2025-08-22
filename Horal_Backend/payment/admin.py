from django.contrib import admin
from .models import OrderStatusLog, PaystackTransaction

@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ('object_id', 'content_type', 'parent', 'old_status', 'new_status', 'changed_by', 'timestamp')
    list_filter = ('old_status', 'new_status', 'changed_by')
    search_fields = ('order__id',)

@admin.register(PaystackTransaction)
class PaystackTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'reference', 'status', 'refund_successful', 'created_at')
    list_filter = ('status', 'refund_successful')
    search_fields = ('reference', 'email', 'user__email')
