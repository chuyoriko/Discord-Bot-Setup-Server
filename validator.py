from __future__ import annotations

import re
from typing import Any

import discord

MAX_ROLES = 25
MAX_CATEGORIES = 15
MAX_CHANNELS_PER_CATEGORY = 15
MAX_TOTAL_CHANNELS = 80

_CHANNEL_TEXT_RE = re.compile(r"[^a-z0-9-]+")
_ALLOWED_PERMISSIONS = set(discord.Permissions.VALID_FLAGS)


def fallback_blueprint(goal: str) -> dict[str, Any]:
    goal_lower = goal.lower()

    if any(keyword in goal_lower for keyword in ("study", "school", "class", "learning")):
        return {
            "roles": [
                {"name": "Admins", "permissions": ["administrator"], "hoist": True, "mentionable": False},
                {"name": "Mentors", "permissions": ["manage_messages", "mute_members"], "hoist": True, "mentionable": True},
                {"name": "Students", "permissions": [], "hoist": False, "mentionable": True},
            ],
            "categories": [
                {
                    "name": "Start Here",
                    "channels": [
                        {"name": "rules", "type": "text", "topic": "Community rules and expectations"},
                        {"name": "announcements", "type": "text", "topic": "Important updates"},
                    ],
                },
                {
                    "name": "Study Hub",
                    "channels": [
                        {"name": "general-study", "type": "text", "topic": "General study discussion"},
                        {"name": "questions", "type": "text", "topic": "Ask for help on any topic"},
                        {"name": "study-room-1", "type": "voice"},
                        {"name": "study-room-2", "type": "voice"},
                    ],
                },
            ],
        }

    if any(keyword in goal_lower for keyword in ("game", "gaming", "esports", "clan")):
        return {
            "roles": [
                {"name": "Admins", "permissions": ["administrator"], "hoist": True, "mentionable": False},
                {"name": "Moderators", "permissions": ["manage_messages", "kick_members"], "hoist": True, "mentionable": True},
                {"name": "Members", "permissions": [], "hoist": False, "mentionable": True},
            ],
            "categories": [
                {
                    "name": "Start Here",
                    "channels": [
                        {"name": "rules", "type": "text", "topic": "Server rules"},
                        {"name": "announcements", "type": "text", "topic": "News and patch notes"},
                    ],
                },
                {
                    "name": "Community",
                    "channels": [
                        {"name": "general-chat", "type": "text", "topic": "General chat"},
                        {"name": "looking-for-group", "type": "text", "topic": "Find teammates"},
                        {"name": "media", "type": "text", "topic": "Clips and screenshots"},
                    ],
                },
                {
                    "name": "Voice",
                    "channels": [
                        {"name": "Lobby", "type": "voice"},
                        {"name": "Squad 1", "type": "voice"},
                        {"name": "Squad 2", "type": "voice"},
                    ],
                },
            ],
        }

    return {
        "roles": [
            {"name": "Admins", "permissions": ["administrator"], "hoist": True, "mentionable": False},
            {"name": "Moderators", "permissions": ["manage_messages", "manage_channels"], "hoist": True, "mentionable": True},
            {"name": "Members", "permissions": [], "hoist": False, "mentionable": True},
        ],
        "categories": [
            {
                "name": "Start Here",
                "channels": [
                    {"name": "rules", "type": "text", "topic": "Read this first"},
                    {"name": "announcements", "type": "text", "topic": "Important updates"},
                ],
            },
            {
                "name": "Community",
                "channels": [
                    {"name": "general", "type": "text", "topic": "General discussion"},
                    {"name": "introductions", "type": "text", "topic": "Say hi"},
                    {"name": "bot-commands", "type": "text", "topic": "Use bot commands here"},
                ],
            },
            {
                "name": "Voice",
                "channels": [
                    {"name": "General Voice", "type": "voice"},
                    {"name": "Chill Voice", "type": "voice"},
                ],
            },
        ],
    }


def validate_blueprint(blueprint: dict[str, Any], goal: str = "") -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        blueprint = {}

    roles = blueprint.get("roles")
    categories = blueprint.get("categories")

    if not isinstance(roles, list) or not isinstance(categories, list):
        blueprint = fallback_blueprint(goal)
        roles = blueprint["roles"]
        categories = blueprint["categories"]

    validated_roles = _validate_roles(roles)
    validated_categories = _validate_categories(categories)

    if not validated_categories:
        validated_categories = _validate_categories(fallback_blueprint(goal)["categories"])

    return {
        "roles": validated_roles,
        "categories": validated_categories,
    }


def _validate_roles(roles: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for role in roles:
        if len(output) >= MAX_ROLES:
            break
        if not isinstance(role, dict):
            continue

        name = _clean_display_name(role.get("name"), fallback="Role")
        name = _dedupe_name(name, seen_names)
        seen_names.add(name.casefold())

        parsed_color = _parse_color(role.get("color"))
        permissions = _normalize_permissions(role.get("permissions", []))

        item: dict[str, Any] = {
            "name": name,
            "permissions": permissions,
            "hoist": bool(role.get("hoist", False)),
            "mentionable": bool(role.get("mentionable", False)),
        }
        if parsed_color is not None:
            item["color"] = parsed_color

        output.append(item)

    return output


def _validate_categories(categories: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    total_channels = 0

    for category in categories:
        if len(output) >= MAX_CATEGORIES or total_channels >= MAX_TOTAL_CHANNELS:
            break
        if not isinstance(category, dict):
            continue

        category_name = _clean_display_name(category.get("name"), fallback="Category")
        category_name = _dedupe_name(category_name, seen_categories)
        seen_categories.add(category_name.casefold())

        raw_channels = category.get("channels", [])
        if not isinstance(raw_channels, list):
            raw_channels = []

        validated_channels: list[dict[str, Any]] = []
        seen_channel_names: set[str] = set()

        for channel in raw_channels:
            if len(validated_channels) >= MAX_CHANNELS_PER_CATEGORY or total_channels >= MAX_TOTAL_CHANNELS:
                break
            if not isinstance(channel, dict):
                continue

            channel_type = _normalize_channel_type(channel.get("type"))

            if channel_type == "text":
                channel_name = _clean_text_channel_name(channel.get("name"), fallback="channel")
            else:
                channel_name = _clean_display_name(channel.get("name"), fallback="Voice")

            channel_name = _dedupe_name(channel_name, seen_channel_names)
            seen_channel_names.add(channel_name.casefold())

            validated = {
                "name": channel_name,
                "type": channel_type,
            }

            if channel_type == "text":
                topic = _clean_topic(channel.get("topic"))
                if topic:
                    validated["topic"] = topic
                validated["nsfw"] = bool(channel.get("nsfw", False))
                validated["slowmode"] = _clamp_int(channel.get("slowmode"), 0, 21600, default=0)
            else:
                validated["bitrate"] = _clamp_int(channel.get("bitrate"), 8000, 384000, default=64000)
                validated["user_limit"] = _clamp_int(channel.get("user_limit"), 0, 99, default=0)

            validated_channels.append(validated)
            total_channels += 1

        if validated_channels:
            output.append({"name": category_name, "channels": validated_channels})

    return output


def _normalize_permissions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    output: list[str] = []
    for permission in value:
        if not isinstance(permission, str):
            continue
        normalized = permission.strip().lower()
        if normalized in _ALLOWED_PERMISSIONS and normalized not in output:
            output.append(normalized)

    return output


def _normalize_channel_type(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() == "voice":
        return "voice"
    return "text"


def _clean_display_name(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return fallback
    return cleaned[:100]


def _clean_text_channel_name(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback

    name = value.strip().lower().replace(" ", "-")
    name = _CHANNEL_TEXT_RE.sub("-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")

    if not name:
        return fallback

    return name[:100]


def _clean_topic(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    topic = value.strip()
    if not topic:
        return ""
    return topic[:1024]


def _clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, numeric))


def _parse_color(value: Any) -> int | None:
    if isinstance(value, int):
        return max(0, min(0xFFFFFF, value))

    if isinstance(value, str):
        normalized = value.strip().lower().replace("#", "")
        if normalized.startswith("0x"):
            normalized = normalized[2:]
        if re.fullmatch(r"[0-9a-f]{6}", normalized):
            return int(normalized, 16)

    return None


def _dedupe_name(name: str, seen: set[str]) -> str:
    if name.casefold() not in seen:
        return name

    index = 2
    while True:
        candidate = f"{name}-{index}"
        if candidate.casefold() not in seen:
            return candidate[:100]
        index += 1
