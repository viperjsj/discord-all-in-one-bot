import discord
from discord.ui import View, Button, button
from utils.ticket_helpers import config, save_config
import traceback
from datetime import datetime
import json


# ================================================================
# TICKET ACTION VIEW
# Persistent view attached to every ticket's welcome message.
# Contains two buttons:
#   - "Close ticket"     — for the creator or staff with manage_channels
#   - "Ask for closure"  — for staff to request the creator to close
# ================================================================

class TicketActionView(View):
    def __init__(self):
        # timeout=None makes it persistent across bot restarts
        super().__init__(timeout=None)

    @button(label="Close ticket", style=discord.ButtonStyle.danger, custom_id="persistent_view_close_ticket")
    async def close_ticket_button(self, interaction: discord.Interaction, button: Button):
        """
        Allows the ticket creator OR staff with manage_channels to close the ticket.
        Opens a confirmation prompt before actually closing.
        """
        is_creator = False
        creator_data = config.get('ticket_creators', {}).get(str(interaction.channel_id))
        if creator_data:
            is_creator = (creator_data.get('user_id') == interaction.user.id)

        if not is_creator and not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("No perms.", ephemeral=True)
            return

        confirm_view = ConfirmCloseView(original_user_id=interaction.user.id)
        await interaction.response.send_message("Are you sure?", view=confirm_view, ephemeral=True)
        confirm_view.message_to_edit = await interaction.original_response()

    @button(label="Ask for closure", style=discord.ButtonStyle.secondary,
            custom_id="persistent_view_request_closure")
    async def request_closure_button(self, interaction: discord.Interaction, button: Button):
        """
        Allows staff to ping the ticket creator asking them to close.
        Can only be used once per ticket (tracked in ticket_config.json).
        """
        creator_data = config.get('ticket_creators', {}).get(str(interaction.channel_id))
        if not creator_data:
            return await interaction.response.send_message("Error.", ephemeral=True)

        creator_id = creator_data.get('user_id')

        # Ticket creator shouldn't use this — they have the Close button
        if interaction.user.id == creator_id:
            return await interaction.response.send_message(
                "You're creator of this ticket, use 'Close' button.", ephemeral=True)

        # Prevent duplicate closure requests
        if str(interaction.channel_id) in config.get('closure_requests', {}):
            return await interaction.response.send_message("Already asked.", ephemeral=True)

        # Save request timestamp and notify the creator
        config.setdefault('closure_requests', {})[str(interaction.channel_id)] = discord.utils.utcnow().isoformat()
        save_config()

        await interaction.channel.send(
            f"<@{creator_id}>, user {interaction.user.mention} ask you to close this ticket..")
        await interaction.response.send_message("Sent.", ephemeral=True)


# ================================================================
# CONFIRM CLOSE VIEW
# Ephemeral confirmation prompt shown after clicking "Close ticket".
# Expires after 120 seconds.
# ================================================================

class ConfirmCloseView(View):
    def __init__(self, original_user_id: int, *, timeout=120):
        super().__init__(timeout=timeout)
        self.original_user_id = original_user_id
        self.message_to_edit = None  # Set after sending so we can edit it later

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the user who clicked the button can interact with this view."""
        return interaction.user.id == self.original_user_id

    @button(label="Confirm", style=discord.ButtonStyle.danger, custom_id="confirm_close_action_internal")
    async def confirm_button_callback(self, interaction: discord.Interaction, button: Button):
        """Confirms closure — calls the internal close logic."""
        await interaction.response.defer()
        success, msg = await _internal_close_ticket(
            interaction.channel, interaction.guild, interaction.user, reason="Close button"
        )
        if self.message_to_edit:
            try:
                await self.message_to_edit.edit(content=msg, view=None)
            except Exception:
                pass
        self.stop()

    @button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_close_action_internal")
    async def cancel_button_callback(self, interaction: discord.Interaction, button: Button):
        """Cancels the close action."""
        await interaction.response.edit_message(content="Canceled.", view=None)
        self.stop()


# ================================================================
# INTERNAL CLOSE TICKET LOGIC
# Shared function used by all close-related actions:
#   - ConfirmCloseView (close button)
#   - ConfirmationView (/close_ticket command)
#
# What it does:
#   1. Moves the channel to the "closed" category
#   2. Removes the ticket creator's permissions
#   3. Renames the channel to "closed-..."
#   4. Cleans up ticket data from ticket_config.json
#   5. Sends a close message and disables the action buttons
# ================================================================

async def _internal_close_ticket(
    channel: discord.TextChannel,
    guild: discord.Guild,
    closing_user: discord.Member,
    reason: str = None
) -> tuple[bool, str]:
    from utils.ticket_helpers import config, save_config, disable_ticket_buttons

    channel_id_str = str(channel.id)
    ticket_creators = config.get('ticket_creators', {})
    creator_data = ticket_creators.get(channel_id_str)

    if not creator_data or not isinstance(creator_data, dict):
        return False, "Ticket data not found."

    ticket_type = creator_data.get('type', 'unknown')

    # Get the closed category from config
    closed_category_id_str = config.get('ticket_categories', {}).get("closed")
    if not closed_category_id_str or not closed_category_id_str.isdigit():
        return False, "Closed category not configured."

    closed_category_id = int(closed_category_id_str)
    closed_category = guild.get_channel(closed_category_id)
    if not isinstance(closed_category, discord.CategoryChannel):
        return False, "Closed category ID is not a category."

    try:
        # Build new permission overwrites:
        # - Everyone: cannot see
        # - Bot: full access
        # - Staff roles for this ticket type: full access
        staff_overwrite = discord.PermissionOverwrite(
            view_channel=True, read_messages=True, send_messages=True,
            add_reactions=True, attach_files=True, embed_links=True,
            manage_messages=True
        )
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: staff_overwrite
        }

        allowed_role_names = config.get('ticket_role_mapping', {}).get(ticket_type, [])
        for role_name in allowed_role_names:
            rid = config.get('ticket_roles', {}).get(role_name)
            if rid and rid.isdigit():
                r = guild.get_role(int(rid))
                if r:
                    new_overwrites[r] = staff_overwrite

        # Apply new permissions
        await channel.edit(overwrites=new_overwrites, reason=f"Closed by {closing_user}")

        # Move to closed category if not already there
        if channel.category_id != closed_category.id:
            await channel.move(
                category=closed_category, end=True,
                sync_permissions=False, reason=f"Closed by {closing_user}"
            )

        # Rename channel to "closed-..."
        new_name = f"closed-{channel.name.replace('closed-', '')}"[:100]
        if channel.name != new_name:
            await channel.edit(name=new_name, reason=f"Ticket closed by {closing_user}")

        # Remove from active tickets in config
        config.get('ticket_creators', {}).pop(channel_id_str, None)
        config.get('closure_requests', {}).pop(channel_id_str, None)
        save_config()

        # Send close message and disable the action buttons
        msg = f"**Ticket closed** by {closing_user.mention}."
        if reason:
            msg += f"\n**Reason:** {reason}"
        await channel.send(msg)
        await disable_ticket_buttons(channel)

        return True, f"Closed <#{channel.id}>."

    except Exception as e:
        traceback.print_exc()
        return False, f"Error: {e}"


# ================================================================
# CONFIRMATION VIEW
# Used by the /close_ticket slash command.
# Similar to ConfirmCloseView but triggered via command, not button.
# ================================================================

class ConfirmationView(View):
    def __init__(self, original_interaction, powod, timeout=60):
        super().__init__(timeout=timeout)
        self.original_interaction = original_interaction
        self.powod = powod
        self.message = None

    async def interaction_check(self, interaction):
        """Only the user who used the command can interact."""
        return interaction.user.id == self.original_interaction.user.id

    @discord.ui.button(label="Yes, close", style=discord.ButtonStyle.danger)
    async def yes_callback(self, interaction, button):
        await interaction.response.defer()
        success, msg = await _internal_close_ticket(
            self.original_interaction.channel,
            self.original_interaction.guild,
            interaction.user,
            reason=self.powod
        )
        await interaction.followup.send(msg, ephemeral=True)
        self.stop()

    @discord.ui.button(label="No, cancel", style=discord.ButtonStyle.secondary)
    async def no_callback(self, interaction, button):
        await interaction.response.edit_message(content="Canceled.", view=None)
        self.stop()


# ================================================================
# CONFIRM BUTTON
# Button that actually creates the ticket channel after user confirms.
# Used inside TicketButton's confirmation prompt.
# ================================================================

class ConfirmButton(Button):
    def __init__(self, ticket_type: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_type = ticket_type

    async def callback(self, interaction: discord.Interaction):
        from utils.ticket_helpers import config, save_config
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        # Get category for this ticket type from config
        cat_id_str = config.get('ticket_categories', {}).get(self.ticket_type)
        if not cat_id_str:
            return await interaction.followup.send("No categories for this type.", ephemeral=True)

        category = guild.get_channel(int(cat_id_str))
        if not category:
            return await interaction.followup.send("Category not found.", ephemeral=True)

        # Increment ticket counter for this type
        counters = config.setdefault('ticket_counters', {})
        counters[self.ticket_type] = counters.get(self.ticket_type, 0) + 1
        ticket_number = counters[self.ticket_type]

        # Build safe channel name: "{number}-{type}-{username}"
        user_name_safe = "".join(
            c for c in user.display_name.replace(' ', '-')
            if c.isalnum() or c in ('-', '_')
        ).lower() or "user"
        ticket_channel_name = f'{ticket_number}-{self.ticket_type}-{user_name_safe}'[:100]

        # Base permissions: everyone can't see, creator and bot can
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
        }

        # Add staff roles from ticket_role_mapping
        role_map = config.get('ticket_role_mapping', {}).get(self.ticket_type, [])
        mentions = []
        for r_name in role_map:
            rid = config.get('ticket_roles', {}).get(r_name)
            if rid and rid.isdigit():
                role = guild.get_role(int(rid))
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    mentions.append(role.mention)

        try:
            # Create the ticket channel
            ch = await category.create_text_channel(
                name=ticket_channel_name,
                overwrites=overwrites,
                reason=f"Ticket '{self.ticket_type}' by {user.display_name}"
            )

            # Send welcome message with action buttons
            welcome_message_content = (
                f"Welcome {user.mention}! Your **{self.ticket_type.upper()}** ticket has been created. "
                f"Number: **{ticket_number}**\n\n"
            )
            if mentions:
                welcome_message_content += f"\n\nMentioned: {' '.join(mentions)}"

            action_view = TicketActionView()
            welcome_msg = await ch.send(welcome_message_content, view=action_view)

            # Save ticket data to config
            config.setdefault('ticket_creators', {})[str(ch.id)] = {
                'user_id': user.id,
                'type': self.ticket_type,
                'welcome_msg_id': welcome_msg.id if welcome_msg else None
            }
            save_config()

            # Send user info embed for staff reference
            user_info_embed = discord.Embed(
                title="Info about user",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            user_info_embed.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
            user_info_embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)

            member_roles = [r.mention for r in sorted(user.roles[1:], key=lambda r: r.position, reverse=True)]
            roles_text = "\n".join(member_roles) if member_roles else "None"
            if len(roles_text) > 1024:
                roles_text = roles_text[:1020] + "\n..."
            user_info_embed.add_field(name=f"Roles ({len(member_roles)})", value=roles_text, inline=False)

            try:
                await ch.send(embed=user_info_embed)
            except Exception:
                pass

            await interaction.followup.send(f"Created: {ch.mention}.", ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send("Error while creating.", ephemeral=True)


# ================================================================
# TICKET BUTTON
# Shown on the ticket panel embed.
# Each button represents a ticket category (config, partnership, general, etc.)
# Clicking opens a confirmation prompt before creating the ticket.
# Prevents duplicate open tickets of the same type per user.
# ================================================================

class TicketButton(Button):
    def __init__(self, ticket_type: str, *args, **kwargs):
        # custom_id must be unique and persistent across restarts
        super().__init__(*args, **kwargs, custom_id=f"create_ticket_{ticket_type}")
        self.ticket_type = ticket_type

    async def callback(self, interaction: discord.Interaction):
        from utils.ticket_helpers import config

        # Check if user already has an open ticket of this type
        for cid, data in config.get('ticket_creators', {}).items():
            if data.get('user_id') == interaction.user.id and data.get('type') == self.ticket_type:
                ch = interaction.guild.get_channel(int(cid))
                closed_id = config.get('ticket_categories', {}).get("closed")
                if ch and (not closed_id or ch.category_id != int(closed_id)):
                    return await interaction.response.send_message(
                        f"You already have ticket of this type: <#{cid}>", ephemeral=True
                    )

        # Build confirmation prompt with unique custom_id (timestamp prevents conflicts)
        confirm_view = View(timeout=60)
        ts = int(discord.utils.utcnow().timestamp())

        btn_confirm = ConfirmButton(
            self.ticket_type,
            label="Confirm",
            style=discord.ButtonStyle.green,
            custom_id=f"conf_{self.ticket_type}_{ts}"
        )
        btn_cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

        async def cancel(itx):
            await itx.response.edit_message(content="Canceled.", view=None)

        btn_cancel.callback = cancel

        confirm_view.add_item(btn_confirm)
        confirm_view.add_item(btn_cancel)

        await interaction.response.send_message(
            f"Create **{self.ticket_type.upper()}** ticket?",
            view=confirm_view,
            ephemeral=True
        )