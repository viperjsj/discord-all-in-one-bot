import discord
from discord.ext import commands
from discord import app_commands
import traceback
from config import *
from utils.ticket_helpers import load_config
from utils.database import Database
from views.ticket_views import TicketActionView

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.messages = True
intents.message_content = True
intents.webhooks = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)


async def load_extensions():
    extensions = [
        "cogs.events",
        "cogs.moderation",
        "cogs.tickets",
        "cogs.fun_commands",
        "cogs.status_monitor",
        "cogs.invite_protection",
        "cogs.webhook_monitor",
        "cogs.webhook_manager",
        "cogs.leveling",
        "cogs.level_commands",
        "cogs.giveaways",
        "cogs.cs2_patches",
    ]
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded: {extension}")
        except Exception as e:
            print(f"❌ Failed to load {extension}: {e}")
            traceback.print_exc()


@bot.event
async def on_ready():
    print("-" * 30)
    print(f'Logged in as: {bot.user.name} ({bot.user.id})')
    print(f'Connected to {len(bot.guilds)} guilds.')
    target_guild = bot.get_guild(GUILD_ID)
    if target_guild:
        print(f'Target guild: {target_guild.name} ({GUILD_ID})')
    else:
        print(f'!!! WARNING: Guild ({GUILD_ID}) not found !!!')
    print("-" * 30)

    print("INFO: Connecting to SQLite database...")
    bot.db = Database()
    await bot.db.setup()

    print("INFO: Loading ticket config...")
    load_config()

    print("INFO: Registering persistent views...")
    try:
        bot.add_view(TicketActionView())
        print("INFO: Registered TicketActionView.")
    except Exception as e:
        print(f"CRITICAL ERROR registering persistent views: {e}")
        traceback.print_exc()

    await load_extensions()

    if GUILD_ID:
        target_guild_obj = discord.Object(id=GUILD_ID)
        print(f"INFO: Syncing commands for guild {GUILD_ID}...")
        try:
            synced_commands = await bot.tree.sync(guild=target_guild_obj)
            print(f"INFO: Synced {len(synced_commands)} commands.")
            if synced_commands:
                print("INFO: Command list:")
                for cmd in sorted(synced_commands, key=lambda c: c.name):
                    print(f"  -> /{cmd.name} (ID: {cmd.id})")
        except Exception as e_sync:
            print(f"SYNC ERROR: {e_sync}")
            traceback.print_exc()

    print("INFO: Checking ticket panel...")
    try:
        tickets_cog = bot.get_cog("Tickets")
        if tickets_cog:
            await tickets_cog.send_ticket_panel_if_configured()
    except Exception as e:
        print(f"TICKET PANEL ERROR: {e}")

    print("-" * 30 + f"\n>>> Bot {bot.user.name} IS READY! <<<\n" + "-" * 30)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Command error: {error}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"You don't have permission to use this command.\nMissing: **{missing}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"You don't have permission to use this command.\nMissing: **{missing}**",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    if isinstance(error, app_commands.CommandOnCooldown):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"⏳ Cooldown! Try again in **{error.retry_after:.1f}s**.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"⏳ Cooldown! Try again in **{error.retry_after:.1f}s**.",
                    ephemeral=True
                )
        except Exception:
            pass
        return

    print(f"[CMD ERROR] /{interaction.command.name if interaction.command else '?'}: {error}")


if __name__ == "__main__":
    if not TOKEN or len(TOKEN) < 55:
        print("CRITICAL ERROR: No token provided!")
        exit(1)
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("CRITICAL ERROR: Invalid token!")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")