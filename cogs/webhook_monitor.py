import discord
from discord.ext import commands, tasks
from config import *
import asyncio
from utils.webhook_checker import is_webhook_allowed

class WebhookMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_webhooks.start()
    
    def cog_unload(self):
        self.check_webhooks.cancel()
    
    @tasks.loop(seconds=60)
    async def check_webhooks(self):
        """Checks and deletes unauthorized webhooks every 60 seconds."""
        
        for guild in self.bot.guilds:
            if guild.id != GUILD_ID:
                continue
                
            for channel in guild.text_channels:
                try:
                    webhooks = await channel.webhooks()
                    for webhook in webhooks:
                        if await is_webhook_allowed(webhook, guild):
                            print(f"[WEBHOOK] Skipped webhook (allowed role) in #{channel.name}")
                            continue
                        
                        await webhook.delete()
                        print(f'[WEBHOOK] Deleted webhook in channel: {channel.name}')
                        
                        logi = guild.get_channel(LOGS_CHANNEL_ID)
                        if logi:
                            await logi.send(
                                f"<@{OWNER_ID}>\n"
                                f"🛑 Deleted **webhook** in channel: <#{channel.id}>\n"
                                f"**Name:** {webhook.name}\n"
                                "``` ```"
                            )
                            
                except discord.Forbidden:
                    print(f"[WEBHOOK] Missing permissions in #{channel.name}")
                except discord.HTTPException as e:
                    print(f"[WEBHOOK] HTTP error in #{channel.name}: {e}")
                except Exception as e:
                    print(f"[WEBHOOK] Error in #{channel.name}: {e}")
    
    @check_webhooks.before_loop
    async def before_check_webhooks(self):
        await self.bot.wait_until_ready()
        print("[WEBHOOK] Bot ready, starting webhook monitoring...")

async def setup(bot):
    await bot.add_cog(WebhookMonitor(bot))