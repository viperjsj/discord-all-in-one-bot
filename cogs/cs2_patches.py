import discord
from discord.ext import commands, tasks
import feedparser
import re
import json
import os
from html import unescape
from config import GUILD_ID, CS2_RSS_URL, CS2_PATCH_CHANNEL_ID

DATA_FILE = "cs2_last_patch.json"


class CS2Patches(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_link = self.load_last_post()
        self.check_cs2_updates.start()

    def cog_unload(self):
        self.check_cs2_updates.cancel()

    def load_last_post(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    return json.load(f).get("last_link")
            except Exception:
                pass
        return None

    def save_last_post(self, link):
        with open(DATA_FILE, "w") as f:
            json.dump({"last_link": link}, f)
        self.last_link = link

    def parse_patch_notes(self, html):
        html = unescape(html)
        clean = re.sub('<.*?>', '', html)

        formatted = ""
        sections = re.split(r'\[(.*?)\]', clean)

        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                if i + 1 >= len(sections):
                    break

                section_name = sections[i].strip()
                content = sections[i + 1].strip()

                formatted += f"\n**{section_name.title()}**\n"

                # Fix missing spaces in CamelCase words (e.g. OverpassFixed -> Overpass Fixed)
                content = re.sub(r'([a-z])([A-Z])', r'\1 \2', content)

                if section_name.upper() == "MAPS":
                    lines = content.split(".")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        words = line.split()

                        # Detect map name (starts with capital letter)
                        if words and words[0][0].isupper():
                            map_name = words[0]
                            rest = " ".join(words[1:]).strip()

                            formatted += f"**{map_name}**\n"

                            if rest:
                                if not rest.endswith("."):
                                    rest += "."
                                formatted += f"- {rest}\n"
                        else:
                            if not line.endswith("."):
                                line += "."
                            formatted += f"- {line}\n"
                else:
                    # Other sections - split by sentences
                    sentences = re.split(r'\.(?=\s|[A-Z])', content)

                    for sentence in sentences:
                        sentence = sentence.strip()
                        if not sentence:
                            continue
                        if not sentence.endswith("."):
                            sentence += "."
                        formatted += f"- {sentence}\n"

                formatted += "\n"

        return formatted.strip()[:4000]

    @tasks.loop(minutes=5)
    async def check_cs2_updates(self):
        try:
            feed = feedparser.parse(CS2_RSS_URL)

            if not feed.entries:
                return

            latest = feed.entries[0]

            if latest.link == self.last_link:
                return

            # First run — just save, don't post
            if self.last_link is None:
                self.save_last_post(latest.link)
                print(f"[CS2] Initial patch saved: {latest.title}")
                return

            self.save_last_post(latest.link)

            channel = self.bot.get_channel(CS2_PATCH_CHANNEL_ID)
            if not channel:
                print(f"[CS2] Channel {CS2_PATCH_CHANNEL_ID} not found")
                return

            description = self.parse_patch_notes(latest.summary)

            embed = discord.Embed(
                title=latest.title,
                url=latest.link,
                description=description,
                color=0xf1c40f
            )
            embed.set_author(name="Counter-Strike 2")
            embed.set_thumbnail(url="https://cdn.cloudflare.steamstatic.com/steam/apps/730/capsule_184x69.jpg")

            await channel.send(embed=embed)
            print(f"[CS2] New patch posted: {latest.title}")

        except Exception as e:
            print(f"[CS2] Error checking updates: {e}")

    @check_cs2_updates.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(CS2Patches(bot))