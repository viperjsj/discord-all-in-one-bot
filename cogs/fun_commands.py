import discord
from discord.ext import commands
from discord import app_commands
from config import GUILD_ID
import random


class FunCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency and response time.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**Bot Latency:** `{latency}ms`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="invite-check", description="Check how many people a user invited")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(user="User to check invites for")
    async def invite_check(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()

        if not user:
            user = interaction.user

        try:
            invites = await interaction.guild.invites()
        except discord.Forbidden:
            await interaction.followup.send("No permission to fetch invites.", ephemeral=True)
            return

        total_uses = 0
        active_links = 0
        user_invites = []

        for invite in invites:
            if invite.inviter and invite.inviter.id == user.id:
                active_links += 1
                total_uses += invite.uses
                if invite.uses > 0:
                    user_invites.append(invite)

        user_invites.sort(key=lambda i: i.uses, reverse=True)

        embed = discord.Embed(
            title=f"Invite stats for {user.display_name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(
            name="Total invites 📨",
            value=f"**{total_uses}**",
            inline=True
        )
        embed.add_field(
            name="Active links 📨",
            value=f"**{active_links}**",
            inline=True
        )

        if user_invites:
            top_invites = user_invites[:5]
            details = ""
            for inv in top_invites:
                expires = "never" if inv.max_age == 0 else f"{inv.max_age // 3600}h"
                details += f"`{inv.code}` — **{inv.uses}** uses (expires: {expires})\n"

            embed.add_field(
                name="Top invite links",
                value=details,
                inline=False
            )
        else:
            embed.add_field(
                name="Top invite links",
                value="No invites with uses found.",
                inline=False
            )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FunCommands(bot))