"""Core settings package. Exports Celery app for Django integration."""

from .celery import app as celery_app

__all__ = ("celery_app",)
