from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

import discord


T = TypeVar("T")
MAX_RETRIES = 4
BASE_DELAY_SECONDS = 0.6
MAX_BACKOFF_SECONDS = 8.0


@dataclass
class DeploySummary:
    roles_created: int
    categories_created: int
    channels_created: int
    errors: list[str]


def _permission_overwrites_for_everyone(guild: discord.Guild) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    everyone = guild.default_role
    return {everyone: discord.PermissionOverwrite(read_messages=True)}


def _build_permissions(permission_names: list[str]) -> discord.Permissions:
    permissions = discord.Permissions.none()
    for name in permission_names:
        if name in discord.Permissions.VALID_FLAGS:
            setattr(permissions, name, True)
    return permissions


def _compute_backoff(attempt: int) -> float:
    exponential = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
    with_jitter = exponential + random.uniform(0.05, 0.35)
    return min(MAX_BACKOFF_SECONDS, with_jitter)


async def _run_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    label: str,
) -> T:
    attempt = 1

    while True:
        try:
            return await operation()
        except discord.HTTPException as exc:
            is_retryable = exc.status == 429 or 500 <= exc.status < 600
            if not is_retryable or attempt >= MAX_RETRIES:
                raise

            retry_after = None
            if exc.status == 429:
                retry_after = getattr(exc, "retry_after", None)

            delay = float(retry_after) if isinstance(retry_after, (int, float)) else _compute_backoff(attempt)
            delay = max(BASE_DELAY_SECONDS, min(MAX_BACKOFF_SECONDS, delay))
            await asyncio.sleep(delay)
            attempt += 1
        except asyncio.TimeoutError:
            if attempt >= MAX_RETRIES:
                raise
            await asyncio.sleep(_compute_backoff(attempt))
            attempt += 1


async def _safe_create(
    operation: Callable[[], Awaitable[T]],
    *,
    errors: list[str],
    forbidden_message: str,
    failure_prefix: str,
) -> T | None:
    try:
        result = await _run_with_retry(operation, label=failure_prefix)
        await asyncio.sleep(BASE_DELAY_SECONDS)
        return result
    except discord.Forbidden:
        errors.append(forbidden_message)
        return None
    except discord.HTTPException as exc:
        errors.append(f"{failure_prefix}: {exc}")
        return None


async def deploy_blueprint(guild: discord.Guild, blueprint: dict[str, Any]) -> DeploySummary:
    errors: list[str] = []
    roles_created = 0
    categories_created = 0
    channels_created = 0

    roles = blueprint.get("roles", [])
    categories = blueprint.get("categories", [])

    existing_roles = {role.name.casefold(): role for role in guild.roles}

    for role_data in roles:
        name = role_data["name"]
        if name.casefold() in existing_roles:
            continue

        permissions = _build_permissions(role_data.get("permissions", []))
        color_value = role_data.get("color")
        color = discord.Color(color_value) if isinstance(color_value, int) else discord.Color.default()

        created_role = await _safe_create(
            lambda: guild.create_role(
                name=name,
                permissions=permissions,
                colour=color,
                hoist=bool(role_data.get("hoist", False)),
                mentionable=bool(role_data.get("mentionable", False)),
                reason="Automated setup by Discord AI autosetup bot",
            ),
            errors=errors,
            forbidden_message=f"Missing permission to create role: {name}",
            failure_prefix=f"Failed to create role {name}",
        )

        if created_role is not None:
            roles_created += 1
            existing_roles[name.casefold()] = created_role

    existing_categories = {channel.name.casefold(): channel for channel in guild.categories}

    for category_data in categories:
        category_name = category_data["name"]

        if category_name.casefold() in existing_categories:
            category = existing_categories[category_name.casefold()]
        else:
            created_category = await _safe_create(
                lambda: guild.create_category(
                    name=category_name,
                    overwrites=_permission_overwrites_for_everyone(guild),
                    reason="Automated setup by Discord AI autosetup bot",
                ),
                errors=errors,
                forbidden_message=f"Missing permission to create category: {category_name}",
                failure_prefix=f"Failed to create category {category_name}",
            )

            if created_category is None:
                continue

            category = created_category
            categories_created += 1
            existing_categories[category_name.casefold()] = created_category

        existing_text = {channel.name.casefold(): channel for channel in category.text_channels}
        existing_voice = {channel.name.casefold(): channel for channel in category.voice_channels}

        for channel_data in category_data.get("channels", []):
            channel_name = channel_data["name"]
            channel_type = channel_data.get("type", "text")

            if channel_type == "voice":
                if channel_name.casefold() in existing_voice:
                    continue

                created_voice = await _safe_create(
                    lambda: guild.create_voice_channel(
                        name=channel_name,
                        category=category,
                        bitrate=int(channel_data.get("bitrate", 64000)),
                        user_limit=int(channel_data.get("user_limit", 0)),
                        reason="Automated setup by Discord AI autosetup bot",
                    ),
                    errors=errors,
                    forbidden_message=f"Missing permission to create voice channel: {channel_name}",
                    failure_prefix=f"Failed to create voice channel {channel_name}",
                )

                if created_voice is not None:
                    channels_created += 1
                    existing_voice[channel_name.casefold()] = created_voice
            else:
                if channel_name.casefold() in existing_text:
                    continue

                created_text = await _safe_create(
                    lambda: guild.create_text_channel(
                        name=channel_name,
                        category=category,
                        topic=channel_data.get("topic"),
                        nsfw=bool(channel_data.get("nsfw", False)),
                        slowmode_delay=int(channel_data.get("slowmode", 0)),
                        reason="Automated setup by Discord AI autosetup bot",
                    ),
                    errors=errors,
                    forbidden_message=f"Missing permission to create text channel: {channel_name}",
                    failure_prefix=f"Failed to create text channel {channel_name}",
                )

                if created_text is not None:
                    channels_created += 1
                    existing_text[channel_name.casefold()] = created_text

    return DeploySummary(
        roles_created=roles_created,
        categories_created=categories_created,
        channels_created=channels_created,
        errors=errors,
    )
