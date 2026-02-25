import discord
from discord.ext import commands
from discord import app_commands
from config import *
import asyncio
import time


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mute_tasks = {}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.restore_mutes()

    async def restore_mutes(self):
        """Restore mute timers from the database after a bot restart."""
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        try:
            active_mutes = await self.bot.db.get_all_active_mutes(str(GUILD_ID))
        except Exception as e:
            print(f"[MUTE] Error loading mutes from DB: {e}")
            return

        now = time.time()
        log_channel = guild.get_channel(LOGS_CHANNEL_ID)

        for mute_data in active_mutes:
            user_id = int(mute_data["userId"])
            expires_at = mute_data["expiresAt"]

            try:
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            except Exception:
                # User left the server — clean up DB
                await self.bot.db.delete_mute(user_id, GUILD_ID)
                continue

            muted_role = guild.get_role(MUTED_ROLE_ID)
            if not muted_role or muted_role not in member.roles:
                # Not muted anymore — clean up DB
                await self.bot.db.delete_mute(user_id, GUILD_ID)
                continue

            remaining = expires_at - now

            if remaining <= 0:
                # Mute expired while the bot was offline — unmute now
                print(f"[MUTE] Expired while offline: {member.name}, unmuting now")
                await self.unmute_user(member, guild, log_channel, is_auto=True)
            else:
                # Still active — create timer for remaining time
                print(f"[MUTE] Restoring timer for {member.name}: {remaining:.0f}s remaining")
                task = self.bot.loop.create_task(
                    self._mute_timer(member, guild, log_channel, remaining)
                )
                self.mute_tasks[user_id] = task

    async def _mute_timer(self, user, guild, log_channel, seconds):
        """Background task that waits and then unmutes."""
        try:
            await asyncio.sleep(seconds)
            # Re-fetch member in case cache is stale
            try:
                member = guild.get_member(user.id) or await guild.fetch_member(user.id)
            except Exception:
                await self.bot.db.delete_mute(user.id, guild.id)
                return
            await self.unmute_user(member, guild, log_channel, is_auto=True)
        except asyncio.CancelledError:
            pass
        finally:
            self.mute_tasks.pop(user.id, None)

    async def unmute_user(self, user, guild, log_channel=None, is_auto=True):
        """Handles unmuting — restores roles from DB."""
        muted_role = guild.get_role(MUTED_ROLE_ID)

        # Get saved roles from DB
        mute_data = await self.bot.db.get_mute(user.id, guild.id)
        previous_role_ids = []

        if mute_data and mute_data["roles"]:
            previous_role_ids = [
                int(r) for r in mute_data["roles"].split(",") if r.strip().isdigit()
            ]

        # Remove muted role
        if muted_role and muted_role in user.roles:
            await user.remove_roles(muted_role, reason="End of mute")

        # Restore previous roles
        if previous_role_ids:
            try:
                previous_roles = [
                    guild.get_role(rid) for rid in previous_role_ids if guild.get_role(rid)
                ]
                current_roles = [
                    role for role in user.roles
                    if role != muted_role and role != guild.default_role
                ]

                all_roles = []
                seen = set()
                for role in previous_roles + current_roles:
                    if role and role.id not in seen:
                        all_roles.append(role)
                        seen.add(role.id)

                await user.edit(roles=all_roles, reason="Restored roles after mute")
            except Exception as e:
                print(f"[MUTE] Error restoring roles for {user.name}: {e}")

        # Clean up DB
        await self.bot.db.delete_mute(user.id, guild.id)

        if log_channel and is_auto:
            await log_channel.send(f"🔊 {user.mention} got automatically unmuted.")

        self.mute_tasks.pop(user.id, None)

    @app_commands.command(name="mute", description="Mute for exact amount of time (minutes).")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(user="User to mute", time="Time (minutes)", reason="Reason")
    @app_commands.default_permissions(administrator=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member, time: int, reason: str):
        await interaction.response.defer()

        user_role_ids = [role.id for role in interaction.user.roles]
        if not any(role_id in MUTE_ROLES_ALLOWED for role_id in user_role_ids):
            await interaction.followup.send(
                f'hey <@{interaction.user.id}>, you cant use this command because you are fucking random\n'
                f'bye :)\n\n'
                f'<@{user.id}>, <@{interaction.user.id}> tried to mute you'
            )
            return

        if user.id in NO_MUTE_USERS or any(r.id in NO_MUTE_ROLES for r in user.roles):
            await interaction.followup.send(
                f'nice try\n'
                f'<@{user.id}>, <@{interaction.user.id}> tried to mute you'
            )
            return

        muted_role = interaction.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            await interaction.followup.send("❌ Role 'muted' does not exist.", ephemeral=True)
            return

        if muted_role in user.roles:
            await interaction.followup.send("❌ User is already muted.", ephemeral=True)
            return

        # Save roles to DB before removing them
        saved_role_ids = [role.id for role in user.roles if role != muted_role and role != interaction.guild.default_role]
        now = time_module_now()
        expires_at = now + (time * 60)

        await self.bot.db.save_mute(
            user_id=user.id,
            guild_id=interaction.guild.id,
            role_ids=saved_role_ids,
            muted_by=interaction.user.id,
            reason=reason,
            muted_at=now,
            expires_at=expires_at
        )

        try:
            await user.edit(roles=[muted_role], reason=f"Muted by {interaction.user} - {reason}")
        except discord.Forbidden:
            await self.bot.db.delete_mute(user.id, interaction.guild.id)
            await interaction.followup.send("No perms.", ephemeral=True)
            return

        # Logs
        log_channel = interaction.guild.get_channel(LOGS_CHANNEL_ID)
        muted_channel = interaction.guild.get_channel(MUTED_CHANNEL_ID)

        await interaction.followup.send(
            f"🔇 {user.mention} you got muted for {time} minutes. Reason: **{reason}**."
        )
        if log_channel:
            await log_channel.send(
                f"🔇 {user.mention} got muted for **{time} minutes** by {interaction.user.mention}. Reason: **{reason}**."
            )
        if muted_channel:
            await muted_channel.send(
                f"🔇 {user.mention}, got muted by {interaction.user.mention} for **{time} minutes**.\n**Reason:** {reason}."
            )

        # Timer task
        task = self.bot.loop.create_task(
            self._mute_timer(user, interaction.guild, log_channel, time * 60)
        )
        self.mute_tasks[user.id] = task

    @app_commands.command(name="unmute", description="Unmute user.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(user="User to unmute")
    @app_commands.default_permissions(administrator=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()

        user_role_ids = [role.id for role in interaction.user.roles]
        if not any(role_id in MUTE_ROLES_ALLOWED for role_id in user_role_ids):
            await interaction.followup.send(
                f'hey <@{interaction.user.id}>, you cant use this command because you are fucking random\nbye :)'
            )
            return

        # Check if user is actually muted (DB or role)
        mute_data = await self.bot.db.get_mute(user.id, interaction.guild.id)
        has_muted_role = MUTED_ROLE_ID in [r.id for r in user.roles]

        if not mute_data and not has_muted_role:
            await interaction.followup.send("User is not muted.", ephemeral=True)
            return

        # Cancel timer if exists
        if user.id in self.mute_tasks:
            self.mute_tasks[user.id].cancel()
            del self.mute_tasks[user.id]

        log_channel = interaction.guild.get_channel(LOGS_CHANNEL_ID)
        await self.unmute_user(user, interaction.guild, log_channel, is_auto=False)

        await interaction.followup.send(f"🔊 {user.mention} unmuted.")
        if log_channel:
            await log_channel.send(
                f"🔊 {user.mention} got unmuted by {interaction.user.mention}."
            )


def time_module_now():
    return time.time()


async def setup(bot):
    await bot.add_cog(Moderation(bot))