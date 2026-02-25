import discord
from discord.ext import commands
from discord import app_commands
from config import *
from utils.webhook_checker import can_user_create_webhook


class WebhookManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="check_webhook_permission", description="Check if you can create webhooks")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def check_webhook_permission(self, interaction: discord.Interaction):
        can_create = await can_user_create_webhook(interaction.user)

        role_mentions = []
        for role_id in ALLOWED_WEBHOOK_ROLES:
            role = interaction.guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)

        if can_create:
            embed = discord.Embed(
                title="You can create webhooks ✅",
                description=f"Because: {' '.join(role_mentions) if role_mentions else 'No role names'}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="You can't create webhooks ❌",
                description=f"You don't have required roles.\n\n**Allowed roles:**\n{' '.join(role_mentions) if role_mentions else 'No roles'}",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="list_webhooks", description="Show all webhooks on server")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_webhooks(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        webhook_list = []
        allowed_count = 0
        not_allowed_count = 0

        for channel in interaction.guild.text_channels:
            try:
                webhooks = await channel.webhooks()
                if webhooks:
                    channel_info = f"**#{channel.name}** ({len(webhooks)} webhooks):\n"

                    for wh in webhooks:
                        if wh.user:
                            user_display = wh.user.name

                            # Convert User to Member for role check
                            member = interaction.guild.get_member(wh.user.id)
                            if member:
                                is_allowed = await can_user_create_webhook(member)
                            else:
                                is_allowed = False
                        else:
                            user_display = "N/A"
                            is_allowed = False

                        status = "ALLOWED ✅" if is_allowed else "NOT ALLOWED ❌"

                        if is_allowed:
                            allowed_count += 1
                        else:
                            not_allowed_count += 1

                        channel_info += f"• `{wh.name}` - {user_display} - {status}\n"

                    webhook_list.append(channel_info)

            except discord.Forbidden:
                webhook_list.append(f"**#{channel.name}** - No perms ❌")

        if not webhook_list:
            await interaction.followup.send("No webhooks on server.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Webhooks on server",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(
            name="Stats",
            value=f"✅ Allowed: {allowed_count}\n❌ Not allowed: {not_allowed_count}\n📊 Sum: {allowed_count + not_allowed_count}",
            inline=False
        )

        text = "\n\n".join(webhook_list)
        if len(text) > 1000:
            embed.description = text[:1000] + "\n\n..."
            await interaction.followup.send(embed=embed, ephemeral=True)

            remaining = text[1000:]
            chunks = [remaining[i:i+2000] for i in range(0, len(remaining), 2000)]
            for chunk in chunks:
                embed2 = discord.Embed(description=chunk, color=discord.Color.blue())
                await interaction.followup.send(embed=embed2, ephemeral=True)
        else:
            embed.description = text
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WebhookManager(bot))