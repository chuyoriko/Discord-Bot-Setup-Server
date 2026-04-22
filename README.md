# Discord AI Auto Setup Bot

Automate Discord server setup with one command.

This bot uses your custom OpenAI-compatible endpoint to generate a server blueprint (roles, categories, text channels, voice channels), validates it, then deploys it safely with retry/backoff handling.

## Features

- `!setup <description>` command to auto-build server structure
- AI-generated blueprint from custom endpoint (`/v1/responses`)
- Validation + sanitization before deployment
- Skips already-existing roles/channels/categories
- Handles permission errors without crashing
- Retry with exponential backoff + jitter for Discord API 429/5xx

## Project Structure

- `main.py` — bot entrypoint and command handling
- `ai.py` — calls OpenAI-compatible Responses API
- `validator.py` — validates and sanitizes blueprint
- `deployer.py` — creates roles/categories/channels with retry logic
- `.env.example` — environment variable template
- `requirements.txt` — dependencies

## Requirements

- Python 3.10+
- A Discord bot token
- Your OpenAI-compatible API key

## Setup

1. Clone repository

```bash
git clone <your-repo-url>
cd discord-bot-autosetup
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Create `.env`

Copy `.env.example` to `.env` and fill values:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
OPENAI_API_KEY=your_client_api_key_here
OPENAI_BASE_URL=https://ai.riko.my/v1
OPENAI_MODEL=gpt-5.4
OPENAI_INSTRUCTIONS=You are a helpful assistant.
BOT_PREFIX=!
AI_REQUEST_TIMEOUT_SECONDS=30
COMMAND_TIMEOUT_SECONDS=180
```

4. Run bot

```bash
python main.py
```

## Discord Bot Permissions

Minimum recommended bot permissions:

- Manage Roles
- Manage Channels
- View Channels
- Send Messages
- Read Message History

For easiest setup/testing, you can use `Administrator`.

User who runs command must have:

- Manage Server (`manage_guild`)

## Usage

In your Discord server:

```txt
!setup gaming server for school friends
```

Example goals:

- `!setup study community for SPM students`
- `!setup startup founder networking server`
- `!setup anime and manga discussion club`

## How It Works

1. Command receives your goal text
2. `ai.py` requests blueprint JSON from your API
3. `validator.py` sanitizes names/limits/permissions
4. `deployer.py` creates resources sequentially
5. Bot returns summary + skipped/error items (if any)

## Rate Limit Handling

The deployer reduces rate-limit risk by:

- Sequential resource creation (no burst parallel creation)
- Base delay between successful creates
- Retry for `429` and `5xx`
- Exponential backoff with jitter

Note: No bot can "bypass" Discord limits. This project follows best-practice mitigation.

## Troubleshooting

### Bot does not respond

- Ensure bot is online (`python main.py` running)
- Check `DISCORD_BOT_TOKEN`
- Confirm bot has access to the server/channel
- Ensure prefix matches `BOT_PREFIX`

### `You need Manage Server permission`

Your Discord account (not just bot) needs `Manage Server` to run `!setup`.

### AI request fails / fallback used

If API is unavailable or invalid response is returned, bot uses fallback blueprint from `validator.py`.

Check:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- API availability

### Some channels/roles not created

- Check final summary for skipped errors
- Ensure bot role is above roles it tries to create/manage
- Ensure required permissions are granted

## Security Notes

- Never commit real `.env` to GitHub
- Rotate API keys if leaked
- Use least-privilege bot permissions in production

## License

MIT (or your preferred license)
