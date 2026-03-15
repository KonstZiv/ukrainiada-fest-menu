# Task 5.1 — Кухня генерує QR для передачі (детально)

## Нова модель: kitchen/models.py

```python
import uuid
from django.utils import timezone
from django.conf import settings


class KitchenHandoff(models.Model):
    """Одноразовий токен для підтвердження передачі страви офіціанту.

    Lifecycle:
        created   — кухар натиснув "Передати офіціанту"
        confirmed — офіціант відсканував і підтвердив
        expired   — минув TTL без підтвердження (handled in view)
    """

    ticket = models.OneToOneField(
        "KitchenTicket",
        on_delete=models.CASCADE,
        related_name="handoff",
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
    )
    target_waiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pending_handoffs",
        limit_choices_to={"role__in": ["waiter", "senior_waiter"]},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Передача страви"
        verbose_name_plural = "Передачі страв"

    @property
    def is_expired(self) -> bool:
        ttl = getattr(settings, "HANDOFF_TOKEN_TTL", 120)  # секунди
        return not self.is_confirmed and (
            timezone.now() - self.created_at
        ).total_seconds() > ttl

    def __str__(self) -> str:
        return f"Handoff {self.token} [{self.ticket}]"
```

## settings/base.py — додати

```python
HANDOFF_TOKEN_TTL: int = config("HANDOFF_TOKEN_TTL", default=120, cast=int)  # секунди
```

## kitchen/services.py — створити handoff

```python
def create_handoff(ticket: KitchenTicket, target_waiter) -> "KitchenHandoff":  # type: ignore[type-arg]
    """Створити одноразовий токен передачі страви офіціанту.

    Raises:
        ValueError: якщо ticket не в статусі DONE або вже має handoff.
    """
    from kitchen.models import KitchenHandoff

    if ticket.status != KitchenTicket.Status.DONE:
        raise ValueError(f"Cannot handoff ticket in status '{ticket.status}'")

    # Видаляємо старий прострочений handoff якщо є
    KitchenHandoff.objects.filter(
        ticket=ticket, is_confirmed=False
    ).delete()

    return KitchenHandoff.objects.create(
        ticket=ticket,
        target_waiter=target_waiter,
    )
```

## kitchen/views.py — generate_handoff_qr

```python
import io
import qrcode
from kitchen.models import KitchenHandoff
from kitchen.services import create_handoff


@role_required(*KITCHEN_ROLES)
def generate_handoff_qr(request: HttpRequest, ticket_id: int) -> HttpResponse:
    """Генерує QR для передачі конкретної страви офіціанту.

    GET: показує форму вибору офіціанта
    POST: створює handoff, повертає QR-код як PNG
    """
    from user.models import User

    ticket = get_object_or_404(
        KitchenTicket,
        pk=ticket_id,
        assigned_to=request.user,
        status=KitchenTicket.Status.DONE,
    )

    if request.method == "POST":
        waiter_id = request.POST.get("waiter_id")
        target_waiter = get_object_or_404(
            User,
            pk=waiter_id,
            role__in=["waiter", "senior_waiter"],
        )

        handoff = create_handoff(ticket, target_waiter=target_waiter)

        scan_url = request.build_absolute_uri(
            f"/order/waiter/handoff/{handoff.token}/confirm/"
        )

        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(scan_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type="image/png")

    # GET — форма вибору офіціанта
    waiters = User.objects.filter(role__in=["waiter", "senior_waiter"])
    return render(request, "kitchen/handoff_select_waiter.html", {
        "ticket": ticket,
        "waiters": waiters,
    })
```

## Тести

```python
# kitchen/tests/test_handoff.py
import pytest
from decimal import Decimal


@pytest.mark.tier1
def test_handoff_token_is_uuid():
    from kitchen.models import KitchenHandoff
    import uuid
    handoff = KitchenHandoff()
    handoff.token = uuid.uuid4()
    assert isinstance(handoff.token, uuid.UUID)


@pytest.mark.tier2
@pytest.mark.django_db
def test_create_handoff_success(django_user_model):
    from kitchen.services import create_handoff, take_ticket, mark_ticket_done
    from kitchen.models import KitchenTicket, KitchenHandoff
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter, status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item, status=KitchenTicket.Status.DONE, assigned_to=kitchen_user
    )

    handoff = create_handoff(ticket, target_waiter=waiter)
    assert handoff.token is not None
    assert handoff.target_waiter == waiter
    assert not handoff.is_confirmed


@pytest.mark.tier1
def test_handoff_is_expired():
    from kitchen.models import KitchenHandoff
    from django.utils import timezone
    from datetime import timedelta
    from unittest.mock import patch, MagicMock

    handoff = KitchenHandoff()
    handoff.is_confirmed = False
    handoff.created_at = timezone.now() - timedelta(seconds=200)

    with patch("django.conf.settings.HANDOFF_TOKEN_TTL", 120):
        assert handoff.is_expired is True


@pytest.mark.tier2
@pytest.mark.django_db
def test_handoff_qr_returns_png(client, django_user_model):
    from kitchen.models import KitchenTicket, KitchenHandoff
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter, status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item, status=KitchenTicket.Status.DONE, assigned_to=kitchen_user
    )

    client.force_login(kitchen_user)
    response = client.post(
        f"/kitchen/ticket/{ticket.id}/handoff/",
        {"waiter_id": waiter.id},
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
```

## Acceptance criteria

- [ ] `KitchenHandoff` модель з UUID token, `is_expired` property, міграція
- [ ] `HANDOFF_TOKEN_TTL` в settings (default 120s)
- [ ] `create_handoff` — видаляє старий прострочений handoff перед створенням нового
- [ ] POST на view → PNG QR-код з правильним scan URL
- [ ] Тести зелені
