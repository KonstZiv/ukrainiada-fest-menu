"""Tests for PWA manifest, service worker, and offline page (Tasks 7.3+7.4)."""

from __future__ import annotations

import json
import os

import pytest
from django.test import Client


def test_manifest_json_is_valid() -> None:
    manifest_path = os.path.join("staticfiles", "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    assert manifest["name"] == "Festival Menu — Ukrainiada"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/menu/"
    assert len(manifest["icons"]) == 2


def test_service_worker_exists() -> None:
    assert os.path.exists(os.path.join("staticfiles", "js", "sw.js"))


def test_offline_detector_exists() -> None:
    assert os.path.exists(os.path.join("staticfiles", "js", "offline_detector.js"))


def test_pwa_icons_exist() -> None:
    assert os.path.exists(os.path.join("staticfiles", "icons", "icon-192.png"))
    assert os.path.exists(os.path.join("staticfiles", "icons", "icon-512.png"))


@pytest.mark.django_db
def test_offline_page_returns_200(client: Client) -> None:
    response = client.get("/offline/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "з'єднання" in content.lower() or "з\u2019єднання" in content


@pytest.mark.django_db
def test_base_template_has_manifest(client: Client) -> None:
    response = client.get("/menu/")
    content = response.content.decode()
    assert "manifest.json" in content


@pytest.mark.django_db
def test_base_template_has_sw_registration(client: Client) -> None:
    response = client.get("/menu/")
    content = response.content.decode()
    assert "serviceWorker" in content


@pytest.mark.django_db
def test_base_template_has_theme_color(client: Client) -> None:
    response = client.get("/menu/")
    content = response.content.decode()
    assert 'name="theme-color"' in content
