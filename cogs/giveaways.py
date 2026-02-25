import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import *
import time
import random
from datetime import datetime


class GiveawayJoinButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="🎉 Join Giveaway",
            custom_id="giveaway_join"
        )

    async def callback(self, interaction: discord.Interaction):
        giveaway = await interaction.client.db.get_giveaway_by_message(interaction.message.id)
        if not giveaway:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return

        if giveaway["ended"]:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        if str(interaction.user.id) == giveaway["hostedById"]:
            await interaction.response.send_message("You can't join your own giveaway.", ephemeral=True)
            return

        entries = await interaction.client.db.get_giveaway_entries(giveaway["id"])

        if str(interaction.user.id) in entries:
            await interaction.client.db.remove_giveaway_entry(giveaway["id"], interaction.user.id)
            count = await interaction.client.db.get_giveaway_entry_count(giveaway["id"])

            cog = interaction.client.get_cog("Giveaways")
            if cog:
                await cog.update_giveaway_embed(giveaway, count)

            await interaction.response.send_message("You left the giveaway.", ephemeral=True)
            return

        await interaction.client.db.add_giveaway_entry(giveaway["id"], interaction.user.id)
        count = await interaction.client.db.get_giveaway_entry_count(giveaway["id"])

        cog = interaction.client.get_cog("Giveaways")
        if cog:
            await cog.update_giveaway_embed(giveaway, count)

        await interaction.response.send_message("You joined the giveaway! Good luck! 🎉", ephemeral=True)


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GiveawayJoinButton())


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.forced_winners = {}
        self.giveaway_loop.start()

    def cog_unload(self):
        self.giveaway_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(GiveawayView())

    def generate_public_id(self, guild_name, number):
        now = datetime.utcnow()
        clean_name = "".join(c for c in guild_name if c.isalnum()).upper()[:8]
        return f"{clean_name}-{now.strftime('%y%m')}-{number:04d}"

    def build_giveaway_embed(self, prize, hosted_by_name, ends_at, winner_count, required_invites, participants, public_id, ended=False, winners_text=None):
        if ended:
            embed = discord.Embed(title=f"{prize} 🎉", color=discord.Color.dark_grey())
        else:
            embed = discord.Embed(title=f"{prize} 🎉", color=discord.Color.gold())

        embed.add_field(name="Hosted by", value=hosted_by_name, inline=True)

        if ended:
            embed.add_field(name="Ended at", value=f"<t:{int(ends_at)}:F>", inline=True)
        else:
            embed.add_field(name="Ending at", value=f"<t:{int(ends_at)}:R> (<t:{int(ends_at)}:F>)", inline=True)

        embed.add_field(name="Winners", value=str(winner_count), inline=True)

        if required_invites > 0:
            embed.add_field(name="Required invites to win", value=str(required_invites), inline=True)

        embed.add_field(name="Participants", value=str(participants), inline=True)

        if ended and winners_text:
            embed.add_field(name="🏆 Winners", value=winners_text, inline=False)
        elif ended and not winners_text:
            embed.add_field(name="🏆 Winners", value="No valid winners.", inline=False)

        embed.set_footer(text=f"ID: {public_id}")

        return embed

    async def update_giveaway_embed(self, giveaway, participant_count=None):
        try:
            guild = self.bot.get_guild(int(giveaway["guildId"]))
            if not guild:
                return
            channel = guild.get_channel(int(giveaway["channelId"]))
            if not channel:
                return
            message = await channel.fetch_message(int(giveaway["messageId"]))
            if not message:
                return

            if participant_count is None:
                participant_count = await self.bot.db.get_giveaway_entry_count(giveaway["id"])

            try:
                hosted_by = guild.get_member(int(giveaway["hostedById"])) or await guild.fetch_member(int(giveaway["hostedById"]))
                hosted_by_name = hosted_by.display_name
            except Exception:
                hosted_by_name = "Unknown"

            embed = self.build_giveaway_embed(
                prize=giveaway["prize"],
                hosted_by_name=hosted_by_name,
                ends_at=giveaway["endsAt"],
                winner_count=giveaway["winnerCount"],
                required_invites=giveaway["requiredInvites"],
                participants=participant_count,
                public_id=giveaway["publicId"]
            )

            await message.edit(embed=embed)
        except Exception as e:
            print(f"[GIVEAWAY] Error updating embed: {e}")

    async def get_user_invite_count(self, guild, user_id):
        try:
            invites = await guild.invites()
            total = 0
            for invite in invites:
                if invite.inviter and invite.inviter.id == user_id:
                    total += invite.uses
            return total
        except Exception:
            return 0

    async def pick_winners(self, giveaway, guild):
        entries = await self.bot.db.get_giveaway_entries(giveaway["id"])
        required_invites = giveaway["requiredInvites"]
        winner_count = giveaway["winnerCount"]
        hosted_by_id = str(giveaway["hostedById"])
        giveaway_id = giveaway["id"]

        entries = [e for e in entries if e != hosted_by_id]

        forced = self.forced_winners.pop(giveaway_id, [])

        winners = []
        reroll_messages = []
        used_ids = set()

        for forced_user_id in forced:
            if len(winners) >= winner_count:
                break
            try:
                member = guild.get_member(forced_user_id) or await guild.fetch_member(forced_user_id)
                winners.append(member)
                used_ids.add(str(forced_user_id))
            except Exception:
                pass

        remaining_entries = [e for e in entries if e not in used_ids]
        random.shuffle(remaining_entries)

        checked_users = set()

        for user_id_str in remaining_entries:
            if len(winners) >= winner_count:
                break

            if user_id_str in checked_users:
                continue
            checked_users.add(user_id_str)

            user_id = int(user_id_str)

            try:
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            except Exception:
                reroll_messages.append(
                    f"<@{user_id}> won, but is no longer in the server. Rerolling."
                )
                continue

            if required_invites > 0:
                invite_count = await self.get_user_invite_count(guild, user_id)
                if invite_count < required_invites:
                    reroll_messages.append(
                        f"{member.mention} won, but had not enough invites ({invite_count}/{required_invites}). Rerolling."
                    )
                    continue

            winners.append(member)

        return winners, reroll_messages

    async def announce_winners(self, channel, giveaway, winners, reroll_messages, is_reroll=False):
        for msg in reroll_messages:
            await channel.send(msg)

        if winners:
            winners_mentions = ", ".join(w.mention for w in winners)
            if is_reroll:
                await channel.send(
                    f"**Reroll!** Congratulations {winners_mentions}! You won **{giveaway['prize']}**! 🎉"
                )
            else:
                await channel.send(
                    f"Congratulations {winners_mentions}! You won **{giveaway['prize']}**! 🎉"
                )
        else:
            await channel.send(f"No valid winners for **{giveaway['prize']}**. 😔")

    async def finalize_giveaway(self, giveaway, guild, winners, reroll_messages, is_reroll=False):
        try:
            channel = guild.get_channel(int(giveaway["channelId"]))
            if not channel:
                return
            message = await channel.fetch_message(int(giveaway["messageId"]))
        except Exception:
            return

        try:
            hosted_by = guild.get_member(int(giveaway["hostedById"])) or await guild.fetch_member(int(giveaway["hostedById"]))
            hosted_by_name = hosted_by.display_name
        except Exception:
            hosted_by_name = "Unknown"

        participant_count = await self.bot.db.get_giveaway_entry_count(giveaway["id"])

        if winners:
            winners_text = "\n".join(w.mention for w in winners)
            winners_ids = ",".join(str(w.id) for w in winners)
        else:
            winners_text = None
            winners_ids = ""

        await self.bot.db.end_giveaway(giveaway["id"], winners_ids)

        embed = self.build_giveaway_embed(
            prize=giveaway["prize"],
            hosted_by_name=hosted_by_name,
            ends_at=giveaway["endsAt"],
            winner_count=giveaway["winnerCount"],
            required_invites=giveaway["requiredInvites"],
            participants=participant_count,
            public_id=giveaway["publicId"],
            ended=True,
            winners_text=winners_text
        )

        await message.edit(embed=embed, view=None)
        await self.announce_winners(channel, giveaway, winners, reroll_messages, is_reroll=is_reroll)

    async def end_giveaway_by_data(self, giveaway):
        guild = self.bot.get_guild(int(giveaway["guildId"]))
        if not guild:
            await self.bot.db.end_giveaway(giveaway["id"], "")
            return

        winners, reroll_messages = await self.pick_winners(giveaway, guild)
        await self.finalize_giveaway(giveaway, guild, winners, reroll_messages)

    async def resolve_giveaway(self, interaction, giveaway_id_str):
        giveaway = await self.bot.db.get_giveaway_by_public_id(giveaway_id_str.strip())

        if not giveaway:
            await interaction.followup.send("Giveaway not found.", ephemeral=True)
            return None

        is_admin = interaction.user.guild_permissions.administrator
        is_creator = str(interaction.user.id) == giveaway["creatorId"]

        if not is_admin and not is_creator:
            await interaction.followup.send("Only the creator or an administrator can manage this giveaway.", ephemeral=True)
            return None

        return giveaway

    async def send_log(self, guild, message):
        log_channel = guild.get_channel(LOGS_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(message)
            except Exception:
                pass

    # --- LOOP ---
    @tasks.loop(seconds=15)
    async def giveaway_loop(self):
        try:
            active = await self.bot.db.get_active_giveaways()
            now = time.time()

            for giveaway in active:
                if giveaway["endsAt"] <= now:
                    await self.end_giveaway_by_data(giveaway)
        except Exception as e:
            print(f"[GIVEAWAY] Loop error: {e}")

    @giveaway_loop.before_loop
    async def before_giveaway_loop(self):
        await self.bot.wait_until_ready()

    # --- PARSE TIME ---
    def parse_duration(self, duration_str):
        duration_str = duration_str.strip().lower()
        total_seconds = 0
        current_number = ""

        for char in duration_str:
            if char.isdigit():
                current_number += char
            elif char in ("s", "m", "h", "d", "w"):
                if not current_number:
                    return None
                num = int(current_number)
                if char == "s":
                    total_seconds += num
                elif char == "m":
                    total_seconds += num * 60
                elif char == "h":
                    total_seconds += num * 3600
                elif char == "d":
                    total_seconds += num * 86400
                elif char == "w":
                    total_seconds += num * 604800
                current_number = ""
            else:
                return None

        if current_number:
            total_seconds += int(current_number) * 60

        return total_seconds if total_seconds > 0 else None

    # --- COMMANDS ---
    @app_commands.command(name="giveaway", description="Create a giveaway")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        prize="What are you giving away? (required)",
        duration="Duration (e.g. 1h, 30m, 1d, 2h30m) (required)",
        channel="Channel to send giveaway in (defaults to current)",
        winners="Number of winners (default: 1)",
        required_invites="Required invites to win (default: 0)",
        hosted_by="Who is hosting? (defaults to you)"
    )
    async def create_giveaway(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: str,
        channel: discord.TextChannel = None,
        winners: int = 1,
        required_invites: int = 0,
        hosted_by: discord.Member = None
    ):
        await interaction.response.defer(ephemeral=True)

        if not channel:
            channel = interaction.channel

        if winners < 1 or winners > 50:
            await interaction.followup.send("Winners must be between 1 and 50.", ephemeral=True)
            return

        if required_invites < 0:
            await interaction.followup.send("Required invites can't be negative.", ephemeral=True)
            return

        seconds = self.parse_duration(duration)
        if not seconds:
            await interaction.followup.send(
                "Invalid duration format. Use e.g. `30m`, `1h`, `2h30m`, `1d`.",
                ephemeral=True
            )
            return

        if seconds < 60:
            await interaction.followup.send("Minimum duration is 1 minute.", ephemeral=True)
            return

        if seconds > 2592000:
            await interaction.followup.send("Maximum duration is 30 days.", ephemeral=True)
            return

        if not hosted_by:
            hosted_by = interaction.user

        ends_at = time.time() + seconds

        number = await self.bot.db.get_next_giveaway_number(interaction.guild.id)
        public_id = self.generate_public_id(interaction.guild.name, number)

        embed = self.build_giveaway_embed(
            prize=prize,
            hosted_by_name=hosted_by.display_name,
            ends_at=ends_at,
            winner_count=winners,
            required_invites=required_invites,
            participants=0,
            public_id=public_id
        )

        view = GiveawayView()
        msg = await channel.send(embed=embed, view=view)

        await self.bot.db.create_giveaway(
            public_id=public_id,
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            message_id=msg.id,
            host_id=interaction.user.id,
            hosted_by_id=hosted_by.id,
            creator_id=interaction.user.id,
            prize=prize,
            winner_count=winners,
            required_invites=required_invites,
            ends_at=ends_at
        )

        await self.send_log(
            interaction.guild,
            f"🎉 **Giveaway created**\n"
            f"**Prize:** {prize}\n"
            f"**ID:** `{public_id}`\n"
            f"**Channel:** {channel.mention}\n"
            f"**Created by:** {interaction.user.mention}\n"
            f"**Hosted by:** {hosted_by.mention}\n"
            f"**Message ID:** `{msg.id}`"
        )

        await interaction.followup.send(
            f"Giveaway **{prize}** created in {channel.mention}!\n`ID: {public_id}`",
            ephemeral=True
        )

    @app_commands.command(name="giveaway-end", description="End a giveaway early")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(giveaway_id="Giveaway ID (from footer)")
    async def end_giveaway_cmd(self, interaction: discord.Interaction, giveaway_id: str):
        await interaction.response.defer(ephemeral=True)

        giveaway = await self.resolve_giveaway(interaction, giveaway_id)
        if not giveaway:
            return

        if giveaway["ended"]:
            await interaction.followup.send("Giveaway already ended.", ephemeral=True)
            return

        await self.send_log(
            interaction.guild,
            f"**Giveaway ended early** 🎉\n"
            f"**ID:** `{giveaway['publicId']}`\n"
            f"**Ended by:** {interaction.user.mention}\n"
            f"**Message ID:** `{giveaway['messageId']}`"
        )

        await self.end_giveaway_by_data(giveaway)
        await interaction.followup.send(f"Giveaway `{giveaway['publicId']}` ended.", ephemeral=True)

    @app_commands.command(name="giveaway-reroll", description="Reroll giveaway winners")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(giveaway_id="Giveaway ID (from footer)")
    async def reroll_giveaway(self, interaction: discord.Interaction, giveaway_id: str):
        await interaction.response.defer(ephemeral=True)

        giveaway = await self.resolve_giveaway(interaction, giveaway_id)
        if not giveaway:
            return

        if not giveaway["ended"]:
            await interaction.followup.send("Giveaway hasn't ended yet.", ephemeral=True)
            return

        guild = interaction.guild
        winners, reroll_messages = await self.pick_winners(giveaway, guild)
        await self.finalize_giveaway(giveaway, guild, winners, reroll_messages, is_reroll=True)

        winners_text = ", ".join(w.mention for w in winners) if winners else "None"
        await self.send_log(
            interaction.guild,
            f"**Giveaway rerolled** 🎉\n"
            f"**ID:** `{giveaway['publicId']}`\n"
            f"**Rerolled by:** {interaction.user.mention}\n"
            f"**New winners:** {winners_text}\n"
            f"**Message ID:** `{giveaway['messageId']}`"
        )

        await interaction.followup.send(f"Giveaway `{giveaway['publicId']}` rerolled.", ephemeral=True)

    @app_commands.command(name="giveaway-setwinner", description="Pre-set a guaranteed winner (applied when giveaway ends)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(giveaway_id="Giveaway ID (from footer)", user="User to guarantee as winner")
    async def set_winner(self, interaction: discord.Interaction, giveaway_id: str, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        giveaway = await self.resolve_giveaway(interaction, giveaway_id)
        if not giveaway:
            return

        if giveaway["ended"]:
            await interaction.followup.send("Giveaway already ended. Use `/giveaway-reroll` instead.", ephemeral=True)
            return

        if str(user.id) == giveaway["hostedById"]:
            await interaction.followup.send("The host can't win their own giveaway.", ephemeral=True)
            return

        giveaway_id_int = giveaway["id"]

        if giveaway_id_int not in self.forced_winners:
            self.forced_winners[giveaway_id_int] = []

        if user.id in self.forced_winners[giveaway_id_int]:
            await interaction.followup.send(f"{user.mention} is already set as a guaranteed winner.", ephemeral=True)
            return

        if len(self.forced_winners[giveaway_id_int]) >= giveaway["winnerCount"]:
            await interaction.followup.send(
                f"Already set {len(self.forced_winners[giveaway_id_int])}/{giveaway['winnerCount']} winners.",
                ephemeral=True
            )
            return

        self.forced_winners[giveaway_id_int].append(user.id)

        await self.send_log(
            interaction.guild,
            f"**Giveaway winner pre-set** 🎉\n"
            f"**ID:** `{giveaway['publicId']}`\n"
            f"**Set by:** {interaction.user.mention}\n"
            f"**Guaranteed winner:** {user.mention}\n"
            f"**Message ID:** `{giveaway['messageId']}`"
        )

        await interaction.followup.send(
            f"{user.mention} is now a guaranteed winner for `{giveaway['publicId']}`.\n"
            f"They will win when the giveaway ends.",
            ephemeral=True
        )

    @app_commands.command(name="giveaway-participants", description="Show giveaway participants")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(giveaway_id="Giveaway ID (from footer)")
    async def giveaway_participants(self, interaction: discord.Interaction, giveaway_id: str):
        await interaction.response.defer(ephemeral=True)

        giveaway = await self.bot.db.get_giveaway_by_public_id(giveaway_id.strip())
        if not giveaway:
            await interaction.followup.send("Giveaway not found.", ephemeral=True)
            return

        entries = await self.bot.db.get_giveaway_entries(giveaway["id"])
        count = len(entries)

        if count == 0:
            embed = discord.Embed(
                title=f"Participants — {giveaway['prize']}",
                description="No participants yet.",
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"ID: {giveaway['publicId']}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild = interaction.guild

        # Build participant list
        lines = []
        for i, user_id_str in enumerate(entries, 1):
            user_id = int(user_id_str)
            member = guild.get_member(user_id)
            if member:
                name = f"{member.mention} ({member.name})"
            else:
                name = f"<@{user_id}> (left server)"
            lines.append(f"**{i}.** {name}")

        # Check for forced winners
        forced = self.forced_winners.get(giveaway["id"], [])
        forced_text = ""
        if forced:
            forced_names = []
            for uid in forced:
                m = guild.get_member(uid)
                forced_names.append(m.mention if m else f"<@{uid}>")
            forced_text = f"\n\n⭐ **Pre-set winners:** {', '.join(forced_names)}"

        # Split into chunks if too long
        full_text = "\n".join(lines) + forced_text

        if len(full_text) <= 4000:
            embed = discord.Embed(
                title=f"Participants — {giveaway['prize']}",
                description=full_text,
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"ID: {giveaway['publicId']} | Total: {count}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Split into multiple embeds
            chunks = []
            current_chunk = ""
            for line in lines:
                if len(current_chunk) + len(line) + 1 > 3900:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += "\n" + line if current_chunk else line
            if current_chunk:
                chunks.append(current_chunk)

            for i, chunk in enumerate(chunks):
                title = f"Participants — {giveaway['prize']}"
                if len(chunks) > 1:
                    title += f" ({i + 1}/{len(chunks)})"

                desc = chunk
                if i == len(chunks) - 1:
                    desc += forced_text

                embed = discord.Embed(
                    title=title,
                    description=desc,
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"ID: {giveaway['publicId']} | Total: {count}")
                await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))