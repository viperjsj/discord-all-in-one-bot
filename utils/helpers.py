import re
import discord

async def contains_discord_invite(message: discord.Message) -> bool:
    """Check if a message contains a Discord invite link."""
    invite_patterns = [
        r'discord\.gg/[a-zA-Z0-9]+',
        r'discord\.com/invite/[a-zA-Z0-9]+',
        r'discordapp\.com/invite/[a-zA-Z0-9]+',
        r'dsc\.gg/[a-zA-Z0-9]+',
    ]

    content = message.content.lower()
    for pattern in invite_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False