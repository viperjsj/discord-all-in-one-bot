# --- BOT TOKEN ---
TOKEN = 'MTU1NDg5MzIxODkxNzc3NzUwOQ.GQQxBC._GjGjNkTN9wxwbMHFH5f9bj4QUQzd9aEJEldSE'

# --- SERVER & CHANNELS ---
GUILD_ID = 0                  # Your Discord server ID
CHANNEL_ID = 0                # Status monitor channel ID
LOGS_CHANNEL_ID = 0           # Mod logs channel ID
LOGS_ID = 0                   # General logs channel ID (edits, deletes, voice)
WELCOME_CHAT = 0              # Welcome / goodbye messages channel ID
MUTED_CHANNEL_ID = 0          # Channel where muted users are notified
LEVEL_UP_CHANNEL_ID = 0       # Channel where level up cards are sent
CS2_PATCH_CHANNEL_ID = 0      # Channel where CS2 patch notes are posted

# --- ROLES ---
ROLE_ID = 0                   # Status monitor reward role ID
OWNER_ID = 0                  # Server owner user ID
MEMBER_ROLE = 0               # Main role given on join (additional roles configured directly in cogs/events.py)
MUTED_ROLE_ID = 0             # Muted role ID

# Roles that bypass invite link protection
WHITELIST_ROLES = []

# Roles that can use /mute and /unmute
MUTE_ROLES_ALLOWED = []

# Roles that cannot be muted
NO_MUTE_ROLES = []

# Users that cannot be muted (user IDs)
NO_MUTE_USERS = []

# Roles whitelisted from anti-admin permission guard
WHITELISTED_ADMIN = []

# Roles allowed to create/use webhooks
ALLOWED_WEBHOOK_ROLES = []

# --- STATUS MONITOR ---
# Custom statuses that trigger role reward
TARGET_CUSTOM_STATUSES = [".gg/yourserver", "discord.gg/yourserver", "/youserver"]

# --- TICKET SYSTEM ---
CONFIG_FILE = 'ticket_config.json'

# --- DATABASES ---
DB_FILE = 'levels.db'
DB_FILE_MUTE = 'mutes.db'
DB_FILE_GIVEAWAY = 'giveaways.db'

# --- CS2 PATCH NOTES ---
CS2_RSS_URL = "https://store.steampowered.com/feeds/news/app/730/"

# --- LEVELING SYSTEM ---
XP_MIN = 5                    # Minimum XP per message
XP_MAX = 15                   # Maximum XP per message
XP_MULTIPLIER = 100           # XP required = level * XP_MULTIPLIER
XP_COOLDOWN = 15              # Seconds between XP gains from messages
VOICE_XP_PER_MINUTE = 10      # XP per minute in voice channel (min 2 active users)

# --- LEVEL REWARDS ---
# Format: { level: role_id }
# User receives the role when reaching that level.
# Previous level roles are automatically removed.
LEVEL_REWARDS = {
    1: 0,
    2: 0,
    3: 0,
    5: 0,
    10: 0,
    15: 0,
    20: 0,
    25: 0,
    30: 0,
    35: 0,
    40: 0,
    45: 0,
    50: 0,
    55: 0,
    60: 0,
    65: 0,
    70: 0,
    75: 0,
    80: 0,
    85: 0,
    90: 0,
    95: 0,
    100: 0,
}
