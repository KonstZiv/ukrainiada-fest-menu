"""Tests for news articles, comments, moderation, and digest subscriptions."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from news.models import Article, ArticleComment, ArticleMainImage
from user.models import CommunicationChannel, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def editor(django_user_model: Any) -> User:
    """User with editor role."""
    return django_user_model.objects.create_user(
        email="editor@test.com",
        username="editor",
        password="testpass123",
        role="editor",
    )


@pytest.fixture
def visitor(django_user_model: Any) -> User:
    """User with visitor role."""
    return django_user_model.objects.create_user(
        email="visitor@test.com",
        username="visitor",
        password="testpass123",
        role="visitor",
    )


@pytest.fixture
def published_article(editor: User) -> Article:
    """Create a published article with a main image."""
    article = Article.objects.create(
        title="Published",
        title_uk="Опублікована",
        description="Short desc",
        description_uk="Короткий опис",
        content="Full text here",
        content_uk="Повний текст тут",
        status=Article.Status.PUBLISHED,
        author=editor,
    )
    ArticleMainImage.objects.create(
        article=article,
        title="img",
        image="test.jpg",
    )
    return article


@pytest.fixture
def draft_article(editor: User) -> Article:
    """Draft article (not visible to visitors)."""
    return Article.objects.create(
        title="Draft",
        title_uk="Чернетка",
        description="Draft desc",
        description_uk="Опис чернетки",
        content="Draft body",
        content_uk="Тіло чернетки",
        status=Article.Status.DRAFT,
        author=editor,
    )


# ---------------------------------------------------------------------------
# Article list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_article_list_returns_200(client: Client) -> None:
    response = client.get("/news/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_article_list_shows_only_published(
    client: Client,
    published_article: Article,
    draft_article: Article,
) -> None:
    response = client.get("/news/")
    content = response.content.decode()
    assert published_article.title in content
    assert draft_article.title not in content


# ---------------------------------------------------------------------------
# Article detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_article_detail_returns_200(client: Client, published_article: Article) -> None:
    response = client.get(f"/news/{published_article.pk}/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Article create (editor required)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_article_create_requires_editor(client: Client, visitor: User) -> None:
    client.force_login(visitor)
    response = client.get("/news/create/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_comment_saved_as_pending(
    client: Client,
    published_article: Article,
    visitor: User,
) -> None:
    """Comment submitted by a user with a verified channel is saved as PENDING."""
    CommunicationChannel.objects.create(
        user=visitor,
        channel_type=CommunicationChannel.ChannelType.EMAIL,
        address=visitor.email,
        is_verified=True,
    )
    client.force_login(visitor)
    response = client.post(
        f"/news/{published_article.pk}/comment/",
        {"message": "Great article!"},
    )
    assert response.status_code == 302
    comment = ArticleComment.objects.get(article=published_article, author=visitor)
    assert comment.status == ArticleComment.Status.PENDING


@pytest.mark.django_db
def test_moderate_comments_requires_editor(client: Client, visitor: User) -> None:
    client.force_login(visitor)
    response = client.get("/news/comments/moderate/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_approve_comment_changes_status(
    client: Client,
    published_article: Article,
    editor: User,
    visitor: User,
) -> None:
    comment = ArticleComment.objects.create(
        article=published_article,
        author=visitor,
        message="Nice!",
        status=ArticleComment.Status.PENDING,
    )
    client.force_login(editor)
    response = client.post(f"/news/comments/{comment.pk}/approve/")
    assert response.status_code == 302
    comment.refresh_from_db()
    assert comment.status == ArticleComment.Status.APPROVED
    assert comment.moderated_by == editor


# ---------------------------------------------------------------------------
# Digest subscription
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_subscription_page_requires_verified_channel(
    client: Client, visitor: User
) -> None:
    """User without a verified channel is redirected to channels page."""
    client.force_login(visitor)
    response = client.get("/news/subscription/")
    assert response.status_code == 302
    assert "/user/channels/" in response["Location"]
