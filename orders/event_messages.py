"""Order event message catalog for i18n.

All message keys are English templates with %(name)s placeholders.
Wrapped in gettext_noop() so makemessages extracts them into .po files.
"""

from django.utils.translation import gettext_noop

# --- Message keys (extracted by makemessages) ---

MESSAGES: dict[str, str] = {
    "order_submitted": gettext_noop("Order submitted: %(items_summary)s"),
    "order_accepted": gettext_noop("%(staff_label)s accepted the order"),
    "order_verified": gettext_noop(
        "%(staff_label)s verified the order and sent it to the kitchen"
    ),
    "kitchen_skip": gettext_noop(
        "Auto: %(staff_label)s skipped kitchen — %(count)s dishes auto-closed"
    ),
    "order_delivered": gettext_noop("%(staff_label)s delivered the order"),
    "ticket_delivered_auto": gettext_noop(
        "Auto: %(staff_label)s delivered %(dish_title)s"
        " (kitchen: %(old_status)s → Done)"
    ),
    "ticket_delivered": gettext_noop("%(staff_label)s delivered %(dish_title)s"),
    "order_delivered_all": gettext_noop(
        "%(staff_label)s delivered the order (all portions)"
    ),
    "cash_payment": gettext_noop("Cash payment €%(price)s accepted by %(staff_label)s"),
    "online_payment": gettext_noop("Online payment €%(price)s — success"),
    "senior_payment": gettext_noop(
        "%(method_label)s payment €%(price)s confirmed by senior waiter"
    ),
    "order_modified": gettext_noop("Order modified: %(summary)s"),
    "order_cancelled": gettext_noop("Order cancelled"),
    "ticket_taken": gettext_noop(
        "Kitchen: %(staff_label)s started preparing %(dish_title)s"
    ),
    "ticket_taken_auto": gettext_noop(
        "Auto: %(staff_label)s skipped 'Take' step for %(dish_title)s"
    ),
    "ticket_done": gettext_noop("Kitchen: %(staff_label)s prepared %(dish_title)s"),
    "all_ready": gettext_noop("All dishes ready! Waiting for waiter to deliver"),
    "ticket_handoff": gettext_noop(
        "Kitchen: %(staff_label)s handed off %(dish_title)s to waiter"
    ),
}

# --- CSS class mapping for terminal log styling ---

MSG_CLASS: dict[str, str] = {
    "order_submitted": "msg-created",
    "order_accepted": "msg-accepted",
    "order_verified": "msg-approved",
    "kitchen_skip": "msg-warning",
    "order_delivered": "msg-delivered",
    "ticket_delivered_auto": "msg-warning",
    "ticket_delivered": "msg-delivered",
    "order_delivered_all": "msg-delivered",
    "cash_payment": "msg-paid",
    "online_payment": "msg-paid",
    "senior_payment": "msg-paid",
    "order_modified": "msg-modified",
    "order_cancelled": "msg-cancelled",
    "ticket_taken": "msg-kitchen",
    "ticket_taken_auto": "msg-warning",
    "ticket_done": "msg-kitchen-done",
    "all_ready": "msg-ready",
    "ticket_handoff": "msg-handoff",
}
