import discord
from discord.ext import commands
from discord import app_commands
import io
import json
import subprocess
import base64
import aiohttp
import time
import asyncio
from config import *

# ========== AVATAR CACHE ==========
class AvatarCache:
    def __init__(self, max_size=1000, ttl=300):
        self.cache = {}
        self.ttl = ttl
        self.max_size = max_size
        self.access_times = {}

    def get(self, user_id):
        if user_id in self.cache:
            data, timestamp = self.cache[user_id]
            if time.time() - timestamp < self.ttl:
                self.access_times[user_id] = time.time()
                return data
            else:
                del self.cache[user_id]
                if user_id in self.access_times:
                    del self.access_times[user_id]
        return None

    def set(self, user_id, b64_data):
        if len(self.cache) >= self.max_size:
            if self.access_times:
                oldest_user = min(self.access_times.items(), key=lambda x: x[1])[0]
                if oldest_user in self.cache:
                    del self.cache[oldest_user]
                if oldest_user in self.access_times:
                    del self.access_times[oldest_user]
        self.cache[user_id] = (b64_data, time.time())
        self.access_times[user_id] = time.time()

    def clear(self):
        self.cache.clear()
        self.access_times.clear()

avatar_cache = AvatarCache()

# ========== COOLDOWN ==========
class CommandCooldown:
    def __init__(self):
        self.cooldowns = {}
        self.cooldown_time = 15

    def check(self, user_id):
        current_time = time.time()
        if user_id in self.cooldowns:
            if current_time - self.cooldowns[user_id] < self.cooldown_time:
                return False
        self.cooldowns[user_id] = current_time
        return True

    def get_remaining(self, user_id):
        current_time = time.time()
        if user_id in self.cooldowns:
            elapsed = current_time - self.cooldowns[user_id]
            if elapsed < self.cooldown_time:
                return self.cooldown_time - elapsed
        return 0

rank_cooldown = CommandCooldown()
top_cooldown = CommandCooldown()


class LevelCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    # --- Avatar URL with cache ---
    async def get_avatar_base64(self, user):
        try:
            cached = avatar_cache.get(user.id)
            if cached:
                return cached
            avatar_url = str(user.display_avatar.with_format("png").with_size(256))
            print(f"[AVATAR] {user.name}: {avatar_url}")
            avatar_cache.set(user.id, avatar_url)
            return avatar_url
        except Exception as e:
            print(f"[AVATAR ERROR] {e}")
            return "https://cdn.discordapp.com/embed/avatars/0.png"

    # --- RENDER BRIDGE (STDIN) ---
    async def render_js(self, type_name, payload):
        try:
            process = subprocess.Popen(
                ["node", "render/runner.js", type_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            json_data = json.dumps(payload).encode('utf-8')
            stdout, stderr = process.communicate(input=json_data)

            if stderr:
                print(f"[RENDER STDERR] {stderr.decode('utf-8', errors='ignore')[:500]}")

            if process.returncode != 0:
                print(f"[RENDER ERROR] Exit code: {process.returncode}")
                return None

            if not stdout or len(stdout) < 100:
                print(f"[RENDER WARN] Output too small: {len(stdout) if stdout else 0}")
                return None

            debug_file = f"/tmp/debug_{type_name}.png"
            with open(debug_file, 'wb') as f:
                f.write(stdout)
            print(f"[RENDER DEBUG] Saved {len(stdout)} bytes to {debug_file}")
            print(f"[RENDER DEBUG] First 8 bytes: {stdout[:8].hex()}")

            png_magic = b'\x89PNG\r\n\x1a\n'
            png_start = stdout.find(png_magic)

            if png_start > 0:
                print(f"[RENDER FIX] Trimming {png_start} bytes before PNG")
                stdout = stdout[png_start:]
            elif png_start < 0:
                print(f"[RENDER WARN] No PNG magic found!")

            return stdout

        except Exception as e:
            print(f"[RENDER EXCEPTION] {e}")
            return None

    # --- HELPER: Update level roles ---
    async def update_level_roles(self, user, guild, new_level):
        """Remove all level roles and add the correct one for new_level."""
        if not LEVEL_REWARDS:
            return None

        roles_to_remove = []
        role_to_add = None

        # Find highest reward level <= new_level
        applicable_levels = [lvl for lvl in LEVEL_REWARDS.keys() if lvl <= new_level]
        target_level = max(applicable_levels) if applicable_levels else None

        for lvl, role_id in LEVEL_REWARDS.items():
            role = guild.get_role(role_id)
            if not role:
                continue

            if lvl == target_level:
                role_to_add = role
            elif role in user.roles:
                roles_to_remove.append(role)

        try:
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove, reason=f"Level set to {new_level}")

            if role_to_add and role_to_add not in user.roles:
                await user.add_roles(role_to_add, reason=f"Level set to {new_level}")
                return role_to_add
            elif role_to_add and role_to_add in user.roles:
                return role_to_add
        except Exception as e:
            print(f"[LEVEL] Error updating roles: {e}")

        return role_to_add

    # --- COMMAND: RANK ---
    @app_commands.command(name="rank", description="Shows your rank")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def rank(self, interaction: discord.Interaction):
        if not rank_cooldown.check(interaction.user.id):
            remaining = rank_cooldown.get_remaining(interaction.user.id)
            await interaction.response.send_message(
                f"⏳ Wait {remaining:.1f} seconds before trying `/rank` again!",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        doc = await self.bot.db.get_user(interaction.user.id, interaction.guild.id)
        if not doc:
            await interaction.followup.send("No data.", ephemeral=True)
            return

        needed = doc["level"] * XP_MULTIPLIER
        rank_pos = await self.bot.db.get_rank(interaction.user.id, interaction.guild.id)

        avatar_url = await self.get_avatar_base64(interaction.user)

        # calculate total XP across all levels
        total_xp = doc.get("totalXp", None)
        if total_xp is None:
            total_xp = int(XP_MULTIPLIER * doc["level"] * (doc["level"] - 1) / 2) + doc["xp"]

        payload = {
            "username": interaction.user.name,
            "avatarURL": avatar_url,
            "userData": {
                "level": doc["level"],
                "xp": doc["xp"],
                "messages": doc.get("messages", 0),
                "voiceMinutes": doc.get("voiceMinutes", 0),
                "totalXp": total_xp,
            },
            "requiredXP": needed,
            "rank": rank_pos
        }

        image = await self.render_js("rank", payload)
        if image:
            await interaction.followup.send(file=discord.File(io.BytesIO(image), filename="rank.png"))
        else:
            progress = (doc["xp"] / needed * 100) if needed > 0 else 0
            embed = discord.Embed(
                title=f"Rank #{rank_pos} | Level {doc['level']}",
                description=(
                    f"**{interaction.user.name}**\n"
                    f"XP: {doc['xp']}/{needed} ({progress:.1f}%)\n"
                    f"Messages: {doc.get('messages', 0)}\n"
                    f"Voice time: {doc.get('voiceMinutes', 0)} minutes\n"
                    f"Total XP: {total_xp}"
                ),
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)

    # --- TOP HELPER ---
    async def _render_top_generic(self, interaction, sort_by, title_suffix=""):
        if not top_cooldown.check(interaction.user.id):
            remaining = top_cooldown.get_remaining(interaction.user.id)
            await interaction.response.send_message(
                f"⏳ Wait {remaining:.1f} seconds before trying again!",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        lb = await self.bot.db.get_leaderboard(interaction.guild.id, sort_by, 10)
        if not lb:
            await interaction.followup.send("No data.", ephemeral=True)
            return

        users_payload = []
        for u in lb:
            try:
                member_id = int(u["userId"])
                member = interaction.guild.get_member(member_id)
                if not member:
                    member = await interaction.guild.fetch_member(member_id)

                avatar = await self.get_avatar_base64(member)
                username = member.name
                print(f"[TOP] User: {username}, Avatar URL: {avatar[:80] if avatar else 'None'}...")
            except Exception as e:
                print(f"[TOP ERROR] {e}")
                avatar = None
                username = "Unknown"

            users_payload.append({
                "username": username,
                "avatar": avatar,
                "level": u["level"],
                "xp": u["xp"],
                "messages": u.get("messages", 0),
                "voiceMinutes": u.get("voiceMinutes", 0),
            })

        image = await self.render_js("top", {
            "guildName": f"{interaction.guild.name} {title_suffix}".strip(),
            "users": users_payload,
            "sortBy": sort_by,
        })

        if image:
            await interaction.followup.send(file=discord.File(io.BytesIO(image), filename="leaderboard.png"))
        else:
            embed = discord.Embed(
                title=f"Leaderboard {title_suffix}",
                color=discord.Color.gold()
            )
            for i, u in enumerate(lb[:10], 1):
                try:
                    member = interaction.guild.get_member(int(u["userId"]))
                    name = member.name if member else f"ID: {u['userId']}"
                except:
                    name = f"ID: {u['userId']}"
                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"Level: {u['level']} | XP: {u['xp']}",
                    inline=False
                )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="toplvl", description="Leaderboard - lvl")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def toplvl(self, interaction: discord.Interaction):
        await self._render_top_generic(interaction, "level")

    @app_commands.command(name="topmessages", description="Leaderboard - messages")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def top_messages(self, interaction: discord.Interaction):
        await self._render_top_generic(interaction, "messages", "(Messages)")

    @app_commands.command(name="topvoice", description="Leaderboard - vc")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def top_voice(self, interaction: discord.Interaction):
        await self._render_top_generic(interaction, "voiceMinutes", "(Voice)")

    # --- ADMIN ---
    @app_commands.command(name="setlevel", description="Set user level (admin)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_level(self, interaction: discord.Interaction, user: discord.Member, level: int):
        if level < 1 or level > 200:
            await interaction.response.send_message("Level must be between 1 and 200.", ephemeral=True)
            return

        await interaction.response.defer()

        await self.bot.db.set_level(user.id, interaction.guild.id, level)

        # Update roles
        new_role = await self.update_level_roles(user, interaction.guild, level)

        await interaction.followup.send(f"Set **level {level}** for {user.mention}")

    @app_commands.command(name="addxp", description="Add XP to user (admin)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def add_xp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if amount < 1 or amount > 10000:
            await interaction.response.send_message("XP must be between 1 and 10000.", ephemeral=True)
            return

        await interaction.response.defer()

        doc = await self.bot.db.add_xp(user.id, interaction.guild.id, amount)
        required_xp = doc["level"] * XP_MULTIPLIER

        if doc["xp"] >= required_xp:
            new_level = doc["level"] + 1
            remaining = doc["xp"] - required_xp
            leveling_cog = self.bot.get_cog("Leveling")
            if leveling_cog:
                await leveling_cog.process_levelup(user, interaction.guild, new_level, remaining)
                await interaction.followup.send(f"Added **{amount} XP** for {user.mention}. Level UP!")
            else:
                await self.bot.db.level_up(user.id, interaction.guild.id, new_level, remaining)
                await self.update_level_roles(user, interaction.guild, new_level)
                await interaction.followup.send(f"Added **{amount} XP** for {user.mention}. Level UP!")
        else:
            await interaction.followup.send(f"Added **{amount} XP** for {user.mention}.")

    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())


async def setup(bot):
    await bot.add_cog(LevelCommands(bot))