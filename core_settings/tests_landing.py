"""Tests for the central landing page."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_landing_page_returns_200(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_landing_contains_menu_link(client: Client) -> None:
    response = client.get("/")
    content = response.content.decode()
    assert 'href="/menu/"' in content


@pytest.mark.django_db
def test_landing_contains_news_link(client: Client) -> None:
    response = client.get("/")
    content = response.content.decode()
    assert 'href="/news/"' in content
