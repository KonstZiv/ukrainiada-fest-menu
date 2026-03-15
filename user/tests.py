from unittest.mock import MagicMock

import pytest

from user.models import User
from user.roles import is_kitchen_staff, is_management, is_waiter_staff


def test_all_roles_defined() -> None:
    roles = [r.value for r in User.Role]
    assert "manager" in roles
    assert "kitchen_supervisor" in roles
    assert "kitchen" in roles
    assert "senior_waiter" in roles
    assert "waiter" in roles
    assert "visitor" in roles
    assert "production" not in roles
    assert "finance" not in roles


def test_is_kitchen_staff() -> None:
    user = MagicMock(spec=User)
    user.Role = User.Role

    user.role = User.Role.KITCHEN
    assert is_kitchen_staff(user) is True

    user.role = User.Role.KITCHEN_SUPERVISOR
    assert is_kitchen_staff(user) is True

    user.role = User.Role.WAITER
    assert is_kitchen_staff(user) is False


def test_is_waiter_staff() -> None:
    user = MagicMock(spec=User)
    user.Role = User.Role

    user.role = User.Role.WAITER
    assert is_waiter_staff(user) is True

    user.role = User.Role.SENIOR_WAITER
    assert is_waiter_staff(user) is True

    user.role = User.Role.KITCHEN
    assert is_waiter_staff(user) is False


def test_is_management() -> None:
    user = MagicMock(spec=User)
    user.Role = User.Role

    user.role = User.Role.MANAGER
    assert is_management(user) is True

    user.role = User.Role.VISITOR
    assert is_management(user) is False


def test_dish_availability_choices() -> None:
    from menu.models import Dish

    values = [a.value for a in Dish.Availability]
    assert "available" in values
    assert "low" in values
    assert "out" in values


def test_dish_availability_default() -> None:
    from menu.models import Dish

    dish = Dish(title="Test", description="", price=1, weight=100, calorie=100)
    assert dish.availability == Dish.Availability.AVAILABLE


@pytest.mark.django_db
def test_dish_list_excludes_out(client) -> None:  # type: ignore[no-untyped-def]
    from menu.models import Category, Dish

    cat = Category.objects.create(title="Test", description="t", number_in_line=1)
    Dish.objects.create(
        title="Available",
        description="",
        price=1,
        weight=100,
        calorie=100,
        category=cat,
        availability="available",
    )
    Dish.objects.create(
        title="OutOfStock",
        description="",
        price=1,
        weight=100,
        calorie=100,
        category=cat,
        availability="out",
    )
    response = client.get("/menu/dishes/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Available" in content
    assert "OutOfStock" not in content
