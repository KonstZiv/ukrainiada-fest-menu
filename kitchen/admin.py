from django.contrib import admin

from kitchen.models import KitchenAssignment, KitchenTicket


@admin.register(KitchenAssignment)
class KitchenAssignmentAdmin(admin.ModelAdmin):
    list_display = ["dish", "kitchen_user"]
    list_filter = ["kitchen_user"]
    search_fields = ["dish__title", "kitchen_user__email"]


@admin.register(KitchenTicket)
class KitchenTicketAdmin(admin.ModelAdmin):
    list_display = ["id", "order_item", "assigned_to", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at", "taken_at", "done_at"]
