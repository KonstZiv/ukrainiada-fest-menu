from django.contrib import admin

from orders.models import Order, OrderEvent, OrderItem, StepEscalation


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ["timestamp", "message", "actor_label"]
    ordering = ["timestamp"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["subtotal_display"]

    def subtotal_display(self, obj: OrderItem) -> str:
        """Display subtotal for the item."""
        return f"\u20ac{obj.subtotal:.2f}"

    subtotal_display.short_description = "Сума"  # type: ignore[attr-defined]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "status",
        "payment_status",
        "waiter",
        "created_at",
        "total_price_display",
    ]
    list_filter = ["status", "payment_status"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "submitted_at",
        "accepted_at",
        "approved_at",
        "ready_at",
        "delivered_at",
        "payment_confirmed_at",
    ]
    inlines = [OrderItemInline, OrderEventInline]

    def total_price_display(self, obj: Order) -> str:
        """Display total price for the order."""
        return f"\u20ac{obj.total_price:.2f}"

    total_price_display.short_description = "Сума"  # type: ignore[attr-defined]


@admin.register(StepEscalation)
class StepEscalationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "step",
        "level",
        "owner",
        "owner_role",
        "order",
        "ticket",
        "created_at",
        "resolved_at",
    ]
    list_filter = ["step", "level"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["order", "ticket", "owner", "caused_by"]
