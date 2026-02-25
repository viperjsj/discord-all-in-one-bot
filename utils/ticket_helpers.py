import json
import os
import discord
from config import CONFIG_FILE

default_config_structure = {
    'ticket_categories': {},
    'ticket_roles': {},
    'ticket_role_mapping': {},
    'ticket_panel_channel_id': None,
    'ticket_panel_message_id': None,
    'ticket_counters': {},
    'ticket_creators': {},
    'closure_requests': {},
}

config = default_config_structure.copy()


def load_config():
    global config
    config = default_config_structure.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                for key in default_config_structure:
                    config[key] = loaded_config.get(key, default_config_structure[key])
                print(f"INFO: Config loaded from {CONFIG_FILE}")
        except Exception as e:
            print(f"ERROR: Config loading failed: {e}. Using defaults.")
            config = default_config_structure.copy()
    else:
        print(f"INFO: No {CONFIG_FILE} found. Will be created on save.")


def save_config():
    global config
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False, sort_keys=True)
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to save config: {e}")


async def disable_ticket_buttons(channel: discord.TextChannel):
    """Disable action buttons on a ticket's welcome message after closing."""
    from views.ticket_views import TicketActionView

    channel_id_str = str(channel.id)
    creator_data = config.get('ticket_creators', {}).get(channel_id_str)
    welcome_msg_id = creator_data.get('welcome_msg_id') if isinstance(creator_data, dict) else None

    if welcome_msg_id:
        try:
            welcome_msg = await channel.fetch_message(welcome_msg_id)
            if welcome_msg:
                disabled_view = TicketActionView()
                for item in disabled_view.children:
                    item.disabled = True
                await welcome_msg.edit(
                    content=welcome_msg.content.split("\n\n**(Ticket Closed)**")[0] + "\n\n**(Ticket Closed)**",
                    view=disabled_view
                )
        except Exception as e:
            print(f"[TICKET] Error disabling buttons: {e}")