"""Celery tasks for news digest generation and delivery."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="news.send_daily_digest")
def send_daily_digest() -> None:
    """Collect articles from last 24h, summarize via LLM, send to daily subscribers."""
    _send_digest("daily", hours=24)


@shared_task(name="news.send_weekly_digest")
def send_weekly_digest() -> None:
    """Collect articles from last 7 days, summarize via LLM, send to weekly subscribers."""
    _send_digest("weekly", hours=168)


@shared_task(name="news.send_urgent_notification")
def send_urgent_notification(article_id: int) -> None:
    """Send urgent article to all urgent + daily + weekly subscribers immediately."""
    from news.delivery import deliver_to_user
    from news.models import Article, DigestSubscription

    try:
        article = Article.objects.get(pk=article_id, status=Article.Status.PUBLISHED)
    except Article.DoesNotExist:
        logger.warning("Urgent article #%s not found or not published", article_id)
        return

    subscribers = DigestSubscription.objects.filter(
        is_active=True,
    ).select_related("user")

    subject = f"🔴 {article.title}"
    body = f"{article.title}\n\n{article.description}\n\nhttps://{_get_domain()}/news/{article.pk}/"

    sent = 0
    for sub in subscribers:
        if deliver_to_user(sub.user, subject, body):
            sent += 1

    logger.info(
        "Urgent notification for article #%s sent to %d subscribers", article_id, sent
    )


def _send_digest(frequency: str, hours: int) -> None:
    """Send digest for the given frequency and time window."""
    from news.delivery import deliver_to_user
    from news.models import Article, DigestSubscription

    since = timezone.now() - timedelta(hours=hours)
    articles = Article.objects.filter(
        status=Article.Status.PUBLISHED,
        created_at__gte=since,
    ).order_by("-created_at")

    if not articles.exists():
        logger.info("No new articles for %s digest", frequency)
        return

    subscribers = DigestSubscription.objects.filter(
        frequency=frequency,
        is_active=True,
    ).select_related("user")

    if not subscribers.exists():
        logger.info("No %s subscribers", frequency)
        return

    # Build digest content.
    summary = _summarize_articles(articles)
    article_links = "\n".join(
        f"• {a.title}\n  https://{_get_domain()}/news/{a.pk}/" for a in articles
    )

    now = timezone.now()
    sent = 0
    for sub in subscribers:
        subject = f"📰 Dobro Djelo — {'Щоденний' if frequency == 'daily' else 'Щотижневий'} дайджест"
        body = f"{summary}\n\n{article_links}\n\n---\nDobro Djelo"
        if deliver_to_user(sub.user, subject, body):
            sub.last_sent_at = now
            sub.save(update_fields=["last_sent_at"])
            sent += 1

    logger.info(
        "%s digest sent to %d subscribers (%d articles)",
        frequency,
        sent,
        articles.count(),
    )


def _summarize_articles(articles: object) -> str:  # type: ignore[override]
    """Summarize articles via Gemini. Falls back to simple list if unavailable."""
    if not settings.GEMINI_API_KEY:
        return "Нові публікації:"

    try:
        from google import genai

        titles = [f"- {a.title}: {a.description}" for a in articles]  # type: ignore[union-attr,attr-defined]
        prompt = (
            "Узагальни ці новини українського культурного центру в 2-3 реченнях українською:\n\n"
            + "\n".join(titles)
        )
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text or "Нові публікації:"
    except Exception:
        logger.exception("LLM summarization failed")
        return "Нові публікації:"


def _get_domain() -> str:
    """Get site domain from settings."""
    return getattr(
        settings, "TG_WEBHOOK_BASE_URL", "https://restoran-service.pythoncourse.me"
    ).replace("https://", "")
