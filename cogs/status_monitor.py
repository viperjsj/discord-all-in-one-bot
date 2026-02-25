import discord
from discord.ext import commands
from config import *

class StatusMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not isinstance(after, discord.Member):
            return

        guild = self.bot.get_guild(GUILD_ID)
        if not guild or after.guild.id != GUILD_ID:
            return

        role = guild.get_role(ROLE_ID)
        if not role:
            return

        if any(r.id in WHITELIST_ROLES for r in after.roles):
            return

        custom_status = next(
            (activity for activity in after.activities if isinstance(activity, discord.CustomActivity) and any(
                status in str(activity.state) for status in TARGET_CUSTOM_STATUSES)),
            None
        )

        channel = guild.get_channel(CHANNEL_ID)
        try:
            if custom_status:
                if role not in after.roles:
                    await after.add_roles(role)
                    if channel:
                        await channel.send(
                            f'{after.mention} set the status and received role **{role.name}**'
                        )
            else:
                if role in after.roles:
                    await after.remove_roles(role)
                    if channel:
                        await channel.send(
                            f'{after.mention} removed the status and lost role **{role.name}**'
                        )
        except:
            pass

async def setup(bot):
    await bot.add_cog(StatusMonitor(bot))