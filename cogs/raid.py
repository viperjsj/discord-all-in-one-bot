import discord
from discord.ext import commands
import asyncio
import logging

# Advanced terminal-only logging
logger = logging.getLogger("RAID")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


class Raid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dm")
    async def dm(self, ctx, *, message: str):
        """DM all users in the server with a 5 second delay."""

        # Delete the !dm message
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
            await ctx.author.send(
                f"DM broadcast finished.\nSent: {sent}\nFailed: {failed}"
            )
        except:
            logger.warning("Could not DM the author with results.")


async def setup(bot):
    await bot.add_cog(Raid(bot))

