import discord
from discord.ext import commands
from discord import app_commands
from config import *
from utils.ticket_helpers import load_config, save_config, config
from views.ticket_views import TicketActionView, ConfirmCloseView, TicketButton, ConfirmationView
import traceback
import json

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_config()

    def _build_panel_embed(self, guild):
        embed = discord.Embed(
            title="TICKET PANEL",
            description="Choose category to create ticket:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Categories:",
            value="**CONFIG** • **PARTNERSHIP** • **GENERAL**",
            inline=False
        )
        embed.add_field(
            name="How does it work?",
            value="1. Click button\n2. Confirm\n3. Wait for staff",
            inline=False
        )
        embed.set_footer(text="Ticket system")
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        return embed

    def _build_panel_view(self):
        view = discord.ui.View(timeout=None)
        types = ["config", "partnership", "general"]
        label_map = {"config": "CONFIG", "partnership": "PARTNERSHIP", "general": "GENERAL"}

        for type_key in types:
            label = label_map.get(type_key, type_key.replace("_", " ").upper())
            style = discord.ButtonStyle.secondary
            view.add_item(TicketButton(ticket_type=type_key, label=label, style=style))

        return view

    async def send_or_update_ticket_panel(self, guild_id: int, channel_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        try:
            channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
        except Exception:
            return

        if not isinstance(channel, discord.TextChannel):
            return

        embed = self._build_panel_embed(guild)
        view = self._build_panel_view()

        # --- Try to edit an existing panel message (if stored in config) ---
        msg_id = config.get('ticket_panel_message_id')
        if msg_id:
            try:
                msg = await channel.fetch_message(int(msg_id))
                await msg.edit(content=None, embed=embed, view=view)
                print(f"[TICKETS] Panel updated (msg {msg_id} in #{channel.name})")
                return
            except discord.NotFound:
                print(f"[TICKETS] Stored message {msg_id} not found, sending a new panel")
                config['ticket_panel_message_id'] = None
                save_config()
            except discord.Forbidden:
                print(f"[TICKETS] Missing permissions to access message {msg_id}")
                return
            except Exception as e:
                print(f"[TICKETS] Error fetching message {msg_id}: {e}")
                config['ticket_panel_message_id'] = None
                save_config()

        # --- Scan recent history to avoid duplicate panels ---
        try:
            async for old_msg in channel.history(limit=50):
                if old_msg.author.id == self.bot.user.id and old_msg.embeds:
                    for emb in old_msg.embeds:
                        if emb.title and "TICKET PANEL" in emb.title:
                            await old_msg.edit(content=None, embed=embed, view=view)
                            config['ticket_panel_message_id'] = str(old_msg.id)
                            save_config()
                            print(f"[TICKETS] Found existing panel in history (msg {old_msg.id}), updated")
                            return
        except Exception as e:
            print(f"[TICKETS] Error while scanning message history: {e}")

        # --- Send new panel ---
        try:
            msg = await channel.send(embed=embed, view=view)
            config['ticket_panel_message_id'] = str(msg.id)
            save_config()
            print(f"[TICKETS] New panel sent (msg {msg.id} in #{channel.name})")
        except Exception as e:
            print(f"[TICKETS] Error sending panel: {e}")

    async def send_ticket_panel_if_configured(self):
        cid = config.get('ticket_panel_channel_id')
        if not cid or not str(cid).isdigit():
            return

        panel_channel_id = int(cid)
        msg_id = config.get('ticket_panel_message_id')

        # If we have a stored message ID, verify it still exists
        if msg_id:
            guild = self.bot.get_guild(GUILD_ID)
            if guild:
                try:
                    channel = guild.get_channel(panel_channel_id) or await guild.fetch_channel(panel_channel_id)
                    if isinstance(channel, discord.TextChannel):
                        msg = await channel.fetch_message(int(msg_id))
                        view = self._build_panel_view()
                        await msg.edit(view=view)
                        print(f"[TICKETS] Panel still exists (msg {msg_id}), re-registered view")
                        return
                except discord.NotFound:
                    print(f"[TICKETS] Panel message (msg {msg_id}) was deleted")
                    config['ticket_panel_message_id'] = None
                    save_config()
                except Exception as e:
                    print(f"[TICKETS] Panel check failed: {e}")

        await self.send_or_update_ticket_panel(GUILD_ID, panel_channel_id)

    @app_commands.command(name="close_ticket", description="Close ticket")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(reason="Reason for closing the ticket (optional)")
    async def close_ticket_command(self, interaction: discord.Interaction, reason: str = None):
        channel = interaction.channel
        user = interaction.user

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("You can use this only on ticket channels.", ephemeral=True)
            return

        creator_data = config.get('ticket_creators', {}).get(str(channel.id))
        if not creator_data or not isinstance(creator_data, dict):
            await interaction.response.send_message("This is not a ticket created by this bot.", ephemeral=True)
            return

        creator_id = creator_data.get('user_id')
        is_creator = (creator_id == user.id) if creator_id else False
        has_manage_channels_perm = channel.permissions_for(user).manage_channels

        if not has_manage_channels_perm and not is_creator:
            await interaction.response.send_message("No perms.", ephemeral=True)
            return

        view = ConfirmationView(original_interaction=interaction, powod=reason)
        await interaction.response.send_message(
            f"{user.mention}, are you sure you want to close (<#{channel.id}>)?",
            view=view,
            ephemeral=True
        )
        view.message = await interaction.original_response()

    @app_commands.command(name="send_ticket_panel", description="Send ticket panel.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(channel="Channel to show panel")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True, thinking=True)
        config['ticket_panel_channel_id'] = str(channel.id)
        config['ticket_panel_message_id'] = None  # force new panel
        save_config()
        await self.send_or_update_ticket_panel(GUILD_ID, channel.id)
        await interaction.followup.send(f"Panel sent to {channel.mention}.", ephemeral=True)

    @app_commands.command(name="show_config", description="Show ticket config.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def show_config(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        load_config()

        try:
            config_str = json.dumps(config, indent=4, ensure_ascii=False, sort_keys=True)
        except Exception as e:
            await interaction.followup.send(f"Error while formatting: {e}", ephemeral=True)
            return

        limit = 1980
        if len(config_str) <= limit:
            await interaction.followup.send(f"```json\n{config_str}\n```", ephemeral=True)
        else:
            parts = []
            current_part = ""
            for line in config_str.splitlines(True):
                if len(current_part) + len(line) > limit:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += line
            if current_part:
                parts.append(current_part)

            first = True
            for i, part in enumerate(parts):
                content_to_send = f"```json\n{part}\n```"
                try:
                    if first:
                        await interaction.followup.send(content_to_send, ephemeral=True)
                        first = False
                    else:
                        await interaction.followup.send(content_to_send, ephemeral=True)
                except discord.HTTPException:
                    break

    @app_commands.command(name="set_category", description="Set ID of category.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(ticket_type=[
        app_commands.Choice(name="Config", value="config"),
        app_commands.Choice(name="Partnership", value="partnership"),
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Closed", value="closed")
    ])
    @app_commands.describe(category_id="Category ID")
    async def set_ticket_category(self, interaction: discord.Interaction, ticket_type: str, category_id: str):
        if not category_id.isdigit():
            await interaction.response.send_message("ID is NaN.", ephemeral=True)
            return

        category_id_int = int(category_id)
        try:
            category = interaction.guild.get_channel(category_id_int) or await interaction.guild.fetch_channel(category_id_int)
            if not category:
                raise discord.NotFound
            if not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message(
                    f"ID {category_id_int} ('{category.name}') is not a category.",
                    ephemeral=True
                )
                return
        except (discord.NotFound, discord.Forbidden) as e:
            await interaction.response.send_message(f"Can't find ID {category_id_int}: {e}", ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("ID error.", ephemeral=True)
            return

        config.setdefault('ticket_categories', {})[ticket_type] = category_id
        save_config()
        await interaction.response.send_message(
            f"Category ID for **'{ticket_type}'** set to **{category_id}** (`{category.name}`).",
            ephemeral=True
        )

    @app_commands.command(name="set_role", description="Set role ID")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(role_key=[
        app_commands.Choice(name="Partnership", value="partnership"),
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Config", value="config")
    ])
    @app_commands.describe(role_id="Role ID")
    async def set_ticket_role(self, interaction: discord.Interaction, role_key: str, role_id: str):
        if not role_id.isdigit():
            await interaction.response.send_message("ID is NaN.", ephemeral=True)
            return

        role_id_int = int(role_id)
        role_obj = interaction.guild.get_role(role_id_int)
        if not role_obj:
            try:
                await interaction.guild.fetch_roles()
                role_obj = interaction.guild.get_role(role_id_int)
            except Exception:
                await interaction.response.send_message(f"ID {role_id_int} not found.", ephemeral=True)
                return

        config.setdefault('ticket_roles', {})[role_key] = role_id
        save_config()
        await interaction.response.send_message(
            f"Role ID for **'{role_key}'** set to **{role_id}** ({role_obj.mention}).",
            ephemeral=True
        )

    @app_commands.command(name="delete_ticket", description="Delete already closed ticket channel")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def delete_ticket(self, interaction: discord.Interaction):
        channel_to_delete = interaction.channel
        user = interaction.user

        if not isinstance(channel_to_delete, discord.TextChannel):
            await interaction.response.send_message("Not a text channel.", ephemeral=True)
            return

        closed_category_id_str = config.get('ticket_categories', {}).get("closed")
        closed_category_id = int(closed_category_id_str) if closed_category_id_str and closed_category_id_str.isdigit() else None

        if not closed_category_id:
            await interaction.response.send_message("Category 'Closed' is not configured.", ephemeral=True)
            return

        if not channel_to_delete.category or channel_to_delete.category.id != closed_category_id:
            await interaction.response.send_message("This ticket is not in the 'Closed' category.", ephemeral=True)
            return

        confirm_view = discord.ui.View(timeout=60.0)
        delete_msg = None

        async def confirm_delete(confirm_interaction: discord.Interaction):
            nonlocal delete_msg
            if confirm_interaction.user.id != interaction.user.id:
                await confirm_interaction.response.send_message("Error.", ephemeral=True)
                return

            try:
                await confirm_interaction.response.send_message(
                    f"Deleting channel `#{channel_to_delete.name}`...", ephemeral=True
                )

                if delete_msg:
                    await delete_msg.edit(content="Confirmed. Deleting...", view=None)

                reason = f"Channel deleted by {user.display_name} ({user.id})"
                await channel_to_delete.delete(reason=reason)

            except Exception as e:
                try:
                    await confirm_interaction.followup.send(f"Error while deleting: {e}", ephemeral=True)
                except Exception:
                    pass
            finally:
                confirm_view.stop()

        async def cancel_delete(cancel_interaction: discord.Interaction):
            if cancel_interaction.user.id != interaction.user.id:
                await cancel_interaction.response.send_message("You can't do this.", ephemeral=True)
                return
            if delete_msg:
                await delete_msg.edit(content="Canceled.", view=None)
            confirm_view.stop()

        confirm_btn = discord.ui.Button(label="Yes, delete", style=discord.ButtonStyle.danger, custom_id="confirm_del_tkt")
        confirm_btn.callback = confirm_delete
        cancel_btn = discord.ui.Button(label="No, cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_del_tkt")
        cancel_btn.callback = cancel_delete

        confirm_view.add_item(confirm_btn)
        confirm_view.add_item(cancel_btn)

        await interaction.response.send_message(
            f"**WARNING:** Are you sure you want to **delete** channel `{channel_to_delete.name}`?.",
            view=confirm_view,
            ephemeral=True
        )
        delete_msg = await interaction.original_response()

    @app_commands.command(name="add_to_ticket", description="Add user to ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(user="User to add")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def add_user_to_ticket(self, interaction: discord.Interaction, user: discord.Member):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Only on ticket channel.", ephemeral=True)
            return

        if str(channel.id) not in config.get('ticket_creators', {}):
            await interaction.response.send_message("Not a ticket.", ephemeral=True)
            return

        closed_category_id_str = config.get('ticket_categories', {}).get("closed")
        closed_category_id = int(closed_category_id_str) if closed_category_id_str and closed_category_id_str.isdigit() else None

        if closed_category_id and channel.category_id == closed_category_id:
            await interaction.response.send_message("Can't add to closed ticket.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        overwrite = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True, add_reactions=True
        )
        try:
            await channel.set_permissions(user, overwrite=overwrite, reason=f"Added by {interaction.user.display_name}")
            await interaction.followup.send(f"Added {user.mention}.", ephemeral=True)
            await channel.send(f"{user.mention} added by {interaction.user.mention}.")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="delete_from_ticket", description="Delete user from ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(user="User to delete")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def remove_user_from_ticket(self, interaction: discord.Interaction, user: discord.Member):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Only on ticket channel.", ephemeral=True)
            return

        if user.id == self.bot.user.id:
            await interaction.response.send_message("Nice try - L.", ephemeral=True)
            return

        ticket_creators = config.get('ticket_creators', {})
        creator_data = ticket_creators.get(str(channel.id))

        if not creator_data:
            await interaction.response.send_message("Not a ticket.", ephemeral=True)
            return

        creator_id = creator_data.get('user_id') if isinstance(creator_data, dict) else None
        if creator_id == user.id:
            await interaction.response.send_message("Can't remove the creator from ticket. Use `/close_ticket`.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if user in channel.overwrites:
                await channel.set_permissions(
                    user,
                    overwrite=None,
                    reason=f"Removed from ticket by {interaction.user.display_name}"
                )
                await interaction.followup.send(f"Successfully removed {user.mention} from this ticket.", ephemeral=True)
                await channel.send(f"{user.mention} removed from ticket by {interaction.user.mention}.")
            else:
                await interaction.followup.send(f"{user.mention} didn't have permissions here.", ephemeral=True)
        except Exception:
            await interaction.followup.send("No perms.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))