import discord
from discord.ext import commands
from utils.helpers import contains_discord_invite
from config import *
import asyncio
import time
from utils.webhook_checker import is_webhook_allowed


class InviteProtection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_deleted_messages = set()
        self.mute_tasks = {}

    async def auto_mute_for_invite(self, member: discord.Member, guild: discord.Guild, duration_minutes: int,
                                   is_edit: bool = False):
        muted_role = guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            print(f"[ERROR] Muted role not found for auto-mute")
            return

        if muted_role in member.roles:
            print(f"[INFO] {member.display_name} is already muted, skipping auto-mute")
            return

        # Save roles to DB before muting
        saved_role_ids = [
            role.id for role in member.roles
            if role != muted_role and role != guild.default_role
        ]
        now = time.time()
        expires_at = now + (duration_minutes * 60)

        await self.bot.db.save_mute(
            user_id=member.id,
            guild_id=guild.id,
            role_ids=saved_role_ids,
            muted_by=self.bot.user.id,
            reason=f"Auto-mute: Discord invite {'edit' if is_edit else 'post'}",
            muted_at=now,
            expires_at=expires_at
        )

        try:
            await member.edit(roles=[muted_role], reason=f"Auto-mute: Discord invite {'edit' if is_edit else 'post'}")
        except discord.Forbidden:
            print(f"[ERROR] No permission to mute {member.display_name}")
            await self.bot.db.delete_mute(member.id, guild.id)
            return

        log_channel = guild.get_channel(LOGS_CHANNEL_ID)
        muted_channel = guild.get_channel(MUTED_CHANNEL_ID)
        violation_type = "editing message to invite link" if is_edit else "posting invite link"

        if log_channel:
            await log_channel.send(
                f"🔇 **Auto-mute for invite link**\n"
                f"**User:** {member.mention} ({member.id})\n"
                f"**Duration:** {duration_minutes} minutes\n"
                f"**Reason:** {violation_type.capitalize()}"
            )

        if muted_channel:
            await muted_channel.send(
                f"🔇 {member.mention}, you got **automatically muted** for **{duration_minutes} minutes**.\n"
                f"**Reason:** {violation_type}"
            )

        print(f"[INFO] Auto-muted {member.display_name} for {duration_minutes} minutes ({violation_type})")

        # Start timer
        task = self.bot.loop.create_task(
            self._mute_timer(member, guild, log_channel, duration_minutes * 60)
        )
        self.mute_tasks[member.id] = task

    async def _mute_timer(self, member, guild, log_channel, seconds):
        try:
            await asyncio.sleep(seconds)
            try:
                member = guild.get_member(member.id) or await guild.fetch_member(member.id)
            except Exception:
                await self.bot.db.delete_mute(member.id, guild.id)
                return
            await self._unmute_user(member, guild, log_channel)
        except asyncio.CancelledError:
            pass
        finally:
            self.mute_tasks.pop(member.id, None)

    async def _unmute_user(self, member, guild, log_channel=None):
        muted_role = guild.get_role(MUTED_ROLE_ID)

        mute_data = await self.bot.db.get_mute(member.id, guild.id)
        previous_role_ids = []

        if mute_data and mute_data["roles"]:
            previous_role_ids = [
                int(r) for r in mute_data["roles"].split(",") if r.strip().isdigit()
            ]

        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role, reason="End of auto-mute")

        if previous_role_ids:
            try:
                previous_roles = [
                    guild.get_role(rid) for rid in previous_role_ids if guild.get_role(rid)
                ]
                current_roles = [
                    role for role in member.roles
                    if role != muted_role and role != guild.default_role
                ]

                all_roles = []
                seen = set()
                for role in previous_roles + current_roles:
                    if role and role.id not in seen:
                        all_roles.append(role)
                        seen.add(role.id)

                await member.edit(roles=all_roles, reason="Restored roles after auto-mute")
            except Exception as e:
                print(f"[INVITE] Error restoring roles for {member.name}: {e}")

        await self.bot.db.delete_mute(member.id, guild.id)

        if log_channel:
            await log_channel.send(f"🔊 {member.mention} got automatically unmuted.")

        self.mute_tasks.pop(member.id, None)

    @commands.Cog.listener()
    async def on_ready(self):
        """Restore invite-protection mute timers after restart."""
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        try:
            active_mutes = await self.bot.db.get_all_active_mutes(str(GUILD_ID))
        except Exception as e:
            print(f"[INVITE] Error loading mutes from DB: {e}")
            return

        now = time.time()
        log_channel = guild.get_channel(LOGS_CHANNEL_ID)

        for mute_data in active_mutes:
            user_id = int(mute_data["userId"])

            # Skip mutes that were created by a staff member (manual /mute)
            # Those are handled by moderation.py restore
            muted_by = str(mute_data.get("mutedBy", ""))
            if muted_by and muted_by != str(self.bot.user.id):
                continue

            try:
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            except Exception:
                await self.bot.db.delete_mute(user_id, GUILD_ID)
                continue

            muted_role = guild.get_role(MUTED_ROLE_ID)
            if not muted_role or muted_role not in member.roles:
                await self.bot.db.delete_mute(user_id, GUILD_ID)
                continue

            remaining = mute_data["expiresAt"] - now

            if remaining <= 0:
                print(f"[INVITE] Expired while offline: {member.name}, unmuting now")
                await self._unmute_user(member, guild, log_channel)
            else:
                print(f"[INVITE] Restoring invite-mute timer for {member.name}: {remaining:.0f}s remaining")
                task = self.bot.loop.create_task(
                    self._mute_timer(member, guild, log_channel, remaining)
                )
                self.mute_tasks[user_id] = task

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.webhook_id:
            try:
                webhooks = await message.channel.webhooks()
                for wh in webhooks:
                    if wh.id == message.webhook_id:
                        if await is_webhook_allowed(wh, message.guild):
                            print(f"[WEBHOOK] Webhook message skipped (allowed role) in #{message.channel.name}")
                            return

                        await wh.delete()

                        logi = self.bot.get_channel(LOGS_CHANNEL_ID)
                        if logi:
                            await logi.send(f"🛑 Deleted webhook and message in <#{message.channel.id}>")

                        try:
                            await message.delete()
                        except:
                            pass
                        return

            except Exception as e:
                print(f"[WEBHOOK ERROR] Webhook error: {e}")

        if message.guild and message.guild.id == GUILD_ID:
            user_has_whitelist = any(role.id in WHITELIST_ROLES for role in message.author.roles)

            if not user_has_whitelist:
                if await contains_discord_invite(message):
                    try:
                        self.bot_deleted_messages.add(message.id)
                        await message.delete()

                        log_channel = message.guild.get_channel(LOGS_CHANNEL_ID)
                        if log_channel:
                            await log_channel.send(
                                f"🔗 **Discord invite link deleted**\n"
                                f"**User:** {message.author.mention} ({message.author.id})\n"
                                f"**Channel:** <#{message.channel.id}>\n"
                                f"**Content:** `{message.content[:100]}{'...' if len(message.content) > 100 else ''}`"
                            )

                        try:
                            await message.channel.send(
                                f"{message.author.mention}, nice try. **Muted for 30 minutes.**",
                                delete_after=10
                            )
                        except discord.Forbidden:
                            pass

                        print(f"[INFO] Deleted Discord invite from {message.author} in #{message.channel.name}")

                        await self.auto_mute_for_invite(message.author, message.guild, 30, is_edit=False)

                        async def cleanup_tracking():
                            await asyncio.sleep(2)
                            self.bot_deleted_messages.discard(message.id)

                        self.bot.loop.create_task(cleanup_tracking())

                    except discord.Forbidden:
                        print(f"[ERROR] No permission to delete message in #{message.channel.name}")
                        self.bot_deleted_messages.discard(message.id)
                    except Exception as e:
                        print(f"[ERROR] Failed to delete invite link: {e}")
                        self.bot_deleted_messages.discard(message.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return

        if before.guild and before.guild.id == GUILD_ID:
            user_has_whitelist = any(role.id in WHITELIST_ROLES for role in after.author.roles)

            before_had_invite = await contains_discord_invite(before)
            after_has_invite = await contains_discord_invite(after)

            if not user_has_whitelist and not before_had_invite and after_has_invite:
                try:
                    self.bot_deleted_messages.add(after.id)
                    await after.delete()

                    log_channel = before.guild.get_channel(LOGS_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(
                            f"🔗 **Discord invite link detected (EDITED MESSAGE)**\n"
                            f"**User:** {after.author.mention} ({after.author.id})\n"
                            f"**Channel:** <#{after.channel.id}>\n"
                            f"**Before:** `{before.content[:100]}{'...' if len(before.content) > 100 else ''}`\n"
                            f"**After:** `{after.content[:100]}{'...' if len(after.content) > 100 else ''}`"
                        )

                    try:
                        await after.channel.send(
                            f"{after.author.mention}, nice try editing your message to add invite link. **Muted for 60 minutes.**",
                            delete_after=10
                        )
                    except discord.Forbidden:
                        pass

                    print(f"[INFO] Deleted edited message with invite from {after.author} in #{after.channel.name}")

                    await self.auto_mute_for_invite(after.author, after.guild, 60, is_edit=True)

                    async def cleanup_tracking():
                        await asyncio.sleep(2)
                        self.bot_deleted_messages.discard(after.id)

                    self.bot.loop.create_task(cleanup_tracking())

                except Exception as e:
                    print(f"[ERROR] Failed to delete edited invite: {e}")
                    self.bot_deleted_messages.discard(after.id)

            elif before.content != after.content:
                logs = before.guild.get_channel(LOGS_ID)
                if logs:
                    await logs.send(
                        f'{before.author.mention} edited:\n"{before.content}" -> "{after.content}" in {before.channel.name}'
                    )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return

        if message.id in self.bot_deleted_messages:
            self.bot_deleted_messages.discard(message.id)
            return

        logs = message.guild.get_channel(LOGS_ID)
        if logs and message.content:
            await logs.send(f'{message.author.mention} deleted:\n"{message.content}" in {message.channel.name}')


async def setup(bot):
    await bot.add_cog(InviteProtection(bot))