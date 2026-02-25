import discord
from discord.ext import commands, tasks
import random
import time
import io
import json
import subprocess
import base64
import aiohttp
from config import *


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {}
        self.voice_xp_loop.start()

    def cog_unload(self):
        self.voice_xp_loop.cancel()

    # --- HELPER: Avatar to Base64 ---
    async def get_avatar_base64(self, user):
        try:
            url = user.display_avatar.with_format("png").with_size(128).url
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode('utf-8')
                        return f"data:image/png;base64,{b64}"
        except Exception as e:
            print(f"[AVATAR ERROR] {e}")
        return None

    async def render_js(self, type_name, payload):
        try:
            process = subprocess.Popen(
                ["node", "render/runner.js", type_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=json.dumps(payload).encode('utf-8'))

            if process.returncode != 0:
                print(f"[RENDER ERROR] {stderr.decode('utf-8')}")
                return None

            return stdout
        except Exception as e:
            print(f"[RENDER EXCEPTION] {e}")
            return None

    async def process_levelup(self, user, guild, new_level, remaining_xp):
        await self.bot.db.level_up(user.id, guild.id, new_level, remaining_xp)

        channel = guild.get_channel(LEVEL_UP_CHANNEL_ID)
        if not channel:
            return

        avatar_b64 = await self.get_avatar_base64(user)

        # Fetch rank and total XP
        rank_pos = await self.bot.db.get_rank(user.id, guild.id)
        doc = await self.bot.db.get_user(user.id, guild.id)
        total_xp = doc.get("totalXp", 0) if doc else 0

        payload = {
            "username": user.name,
            "avatarURL": avatar_b64,
            "level": new_level,
            "xp": remaining_xp,
            "rank": rank_pos,
            "totalXp": total_xp
        }

        image_data = await self.render_js("levelup", payload)

        file = None
        if image_data:
            file = discord.File(io.BytesIO(image_data), filename="levelup.png")

        reward_text = ""
        if new_level in LEVEL_REWARDS:
            new_role_id = LEVEL_REWARDS[new_level]
            new_role = guild.get_role(new_role_id)

            if new_role:
                # Remove all previous level roles
                roles_to_remove = []
                for lvl, role_id in LEVEL_REWARDS.items():
                    if lvl < new_level:
                        old_role = guild.get_role(role_id)
                        if old_role and old_role in user.roles:
                            roles_to_remove.append(old_role)

                try:
                    if roles_to_remove:
                        await user.remove_roles(*roles_to_remove, reason=f"Level up to {new_level}")

                    if new_role not in user.roles:
                        await user.add_roles(new_role, reason=f"Level reward {new_level}")

                    reward_text = f"\nYou gained role: **{new_role.name}**!"
                except Exception as e:
                    print(f"[LEVEL] Error updating roles: {e}")

        await channel.send(
            content=f"{user.mention} reached level **{new_level}**!{reward_text}",
            file=file
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return

        now = time.time()
        if now - self.xp_cooldowns.get(message.author.id, 0) < XP_COOLDOWN:
            return
        self.xp_cooldowns[message.author.id] = now

        xp_gain = random.randint(XP_MIN, XP_MAX)
        doc = await self.bot.db.add_message_xp(message.author.id, message.guild.id, xp_gain)

        if doc["xp"] >= doc["level"] * XP_MULTIPLIER:
            await self.process_levelup(
                message.author, message.guild,
                doc["level"] + 1, doc["xp"] - doc["level"] * XP_MULTIPLIER
            )

    @tasks.loop(seconds=60)
    async def voice_xp_loop(self):
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                active = [m for m in channel.members if not m.bot and not (m.voice.self_deaf or m.voice.deaf)]
                if len(active) < 2:
                    continue
                for member in active:
                    doc = await self.bot.db.add_voice_xp(member.id, guild.id, VOICE_XP_PER_MINUTE)
                    if doc["xp"] >= doc["level"] * XP_MULTIPLIER:
                        await self.process_levelup(
                            member, guild,
                            doc["level"] + 1, doc["xp"] - doc["level"] * XP_MULTIPLIER
                        )

    @voice_xp_loop.before_loop
    async def before_voice(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Leveling(bot))