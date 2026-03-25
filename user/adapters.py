"""Custom allauth adapters for social account integration."""

from __future__ import annotations

from typing import Any

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest

from user.models import CommunicationChannel, User


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Set registration_source and auto-create email CommunicationChannel."""

    def save_user(
        self,
        request: HttpRequest,
        sociallogin: Any,
        form: Any = None,
    ) -> User:
        user: User = super().save_user(request, sociallogin, form)  # type: ignore[assignment]

        # Record how the user registered.
        provider = sociallogin.account.provider
        source_map = {
            "google": User.RegistrationSource.GOOGLE,
            "facebook": User.RegistrationSource.FACEBOOK,
            "instagram": User.RegistrationSource.INSTAGRAM,
            "telegram": User.RegistrationSource.TELEGRAM,
        }
        user.registration_source = source_map.get(
            provider, User.RegistrationSource.EMAIL
        )
        user.save(update_fields=["registration_source"])

        # Auto-create verified email channel.
        if user.email:
            CommunicationChannel.objects.get_or_create(
                user=user,
                channel_type=CommunicationChannel.ChannelType.EMAIL,
                defaults={
                    "address": user.email,
                    "is_verified": True,
                    "priority": 0,
                },
            )

        return user
