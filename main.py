from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

from ai import generate_blueprint_with_timeout
from deployer import deploy_blueprint
from validator import validate_blueprint

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
COMMAND_PREFIX = os.getenv("BOT_PREFIX", "!").strip() or "!"
COMMAND_TIMEOUT_SECONDS = int(os.getenv("COMMAND_TIMEOUT_SECONDS", "180"))

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is missing. Set it in .env")

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


def _truncate(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (ID: {bot.user.id if bot.user else 'unknown'})")


@bot.command(name="setup")
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def setup_server(ctx: commands.Context[Any], *, goal: str) -> None:
    await ctx.reply("Generating server blueprint. This may take a moment...")

    try:
        raw_blueprint = await asyncio.wait_for(
            generate_blueprint_with_timeout(goal),
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await ctx.reply("Setup request timed out while generating blueprint.")
        return
    except Exception as exc:
        await ctx.reply(f"Failed to generate blueprint: {_truncate(str(exc), 400)}")
        return

    validated_blueprint = validate_blueprint(raw_blueprint, goal=goal)

    preview = json.dumps(validated_blueprint, indent=2)
    await ctx.reply(f"Blueprint preview:\n```json\n{_truncate(preview, 1500)}\n```\nDeploying now...")

    try:
        summary = await asyncio.wait_for(
            deploy_blueprint(ctx.guild, validated_blueprint),
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await ctx.reply("Setup request timed out during deployment.")
        return
    except Exception as exc:
        await ctx.reply(f"Deployment failed: {_truncate(str(exc), 500)}")
        return

    result = (
        f"Setup complete. Roles: {summary.roles_created}, "
        f"Categories: {summary.categories_created}, Channels: {summary.channels_created}."
    )

    if summary.errors:
        error_lines = "\n".join(f"- {err}" for err in summary.errors[:10])
        result += f"\nSome items were skipped:\n{_truncate(error_lines, 900)}"

    await ctx.reply(result)


@setup_server.error
async def setup_server_error(ctx: commands.Context[Any], error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Usage: !setup <description>. Example: !setup gaming server for school friends")
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You need Manage Server permission to use this command.")
        return

    if isinstance(error, commands.NoPrivateMessage):
        await ctx.reply("This command can only be used inside a server.")
        return

    await ctx.reply(f"Command error: {_truncate(str(error), 400)}")


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
