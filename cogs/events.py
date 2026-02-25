import discord
from discord.ext import commands
from config import *
import asyncio
import pytz
from datetime import datetime
from utils.webhook_checker import is_webhook_allowed

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_deleted_messages = set()

    @commands.Cog.listener()
    async def on_ready(self):
        print("-" * 50)
        print(f'Logged in as: {self.bot.user.name} ({self.bot.user.id})')
        print(f'Connected to {len(self.bot.guilds)} guilds.')
        target_guild = self.bot.get_guild(GUILD_ID)
        if target_guild:
            print(f'Target guild: {target_guild.name} ({GUILD_ID})')
        else:
            print(f'!!! WARNING: Guild ({GUILD_ID}) not found !!!')
        print("-" * 50)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        welcome = self.bot.get_channel(WELCOME_CHAT)
        if welcome:
            await welcome.send(f'Welcome <@{member.id}>!')

        auto_roles = [
            MEMBER_ROLE,
            1469625744362700821,
            1469622875911884952,
            1469622604066455613,
            1469622304031117466,
            1469625839149781196
        ]

        roles_to_add = []
        for role_id in auto_roles:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Auto-role on join")
            except Exception as e:
                print(f"[JOIN] Error adding roles to {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        bye = self.bot.get_channel(WELCOME_CHAT)
        if bye: 
            await bye.send(f'**{member.display_name}** left the server.')

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if after.guild.id != GUILD_ID: 
            return
        
        logi = after.guild.get_channel(LOGS_CHANNEL_ID)
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        current_time = datetime.now(warsaw_tz).strftime("%Y-%m-%d %H:%M:%S")

        # Anti-Admin/Ban/Kick Guard
        for perm_name in ['administrator', 'ban_members', 'kick_members']:
            if not getattr(before.permissions, perm_name) and getattr(after.permissions, perm_name):
                if after.id not in WHITELISTED_ADMIN:
                    new_perms = after.permissions
                    setattr(new_perms, perm_name, False)
                    await after.edit(permissions=new_perms)
                    if logi:
                        await logi.send(
                            f'<@{OWNER_ID}>\n'
                            f'🛑 Attempted to add **{perm_name}** to role {after.mention}\n'
                            f'🕒 {current_time}'
                        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        logs = member.guild.get_channel(LOGS_ID)
        if not logs: 
            return
        
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        now = datetime.now(warsaw_tz).strftime("%Y-%m-%d %H:%M:%S")

        if before.channel is None and after.channel is not None:
            await logs.send(f'```{now} - {member.display_name} joined: {after.channel.name}```')
        elif before.channel is not None and after.channel is None:
            await logs.send(f'```{now} - {member.display_name} left: {before.channel.name}```')
        elif before.channel != after.channel:
            await logs.send(
                f'```{now} - {member.display_name} moved from {before.channel.name} to {after.channel.name}```')

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        logs = role.guild.get_channel(LOGS_ID)
        if logs:
            async for log in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                await logs.send(f'Role "{role.name}" created by {log.user}')
                break

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        logs = role.guild.get_channel(LOGS_ID)
        if logs:
            async for log in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                await logs.send(f'```Role "{role.name}" deleted by {log.user}```')
                break

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        logs = channel.guild.get_channel(LOGS_ID)
        if logs:
            async for log in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                await logs.send(f'```Channel "{channel.name}" created by {log.user}```')
                break

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        logs = channel.guild.get_channel(LOGS_ID)
        if logs:
            async for log in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                await logs.send(f'```Channel "{channel.name}" deleted by {log.user}```')
                break

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        logs = before.guild.get_channel(LOGS_ID)
        if not logs: 
            return

        if before.nick != after.nick:
            async for log in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                await logs.send(f'{after.mention} nickname changed to "{after.nick}" by {log.user}')
                break

        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]

        if added:
            role_names = ", ".join(r.name for r in added)
            await logs.send(f'{after.mention}```User {after.name} received roles: {role_names}```')
        
        if removed:
            role_names = ", ".join(r.name for r in removed)
            await logs.send(f'{after.mention}```User {after.name} lost roles: {role_names}```')

async def setup(bot):
    await bot.add_cog(Events(bot))