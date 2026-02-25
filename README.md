# Discord All-in-One Bot 🤖

A powerful, modular Discord bot originally designed for a FiveM community, now expanded into a full-featured server manager. Includes Ticket System, Leveling (with Rank Cards), Giveaways, Moderation, and more.

---

## ✨ Features

### 🎫 Advanced Ticket System
* **Category Binding:** Bind specific ticket types to Discord categories.
* **Smart Lifecycle:** Create -> Close -> Re-open/Delete flow.
* **Persistent Panel:** Auto-updating ticket panel with buttons.
* **Role Mapping:** Define which staff roles see which ticket types.
* **Transcript:** Logs are sent to a designated channel.

### 📈 Leveling System
* **XP Tracking:** Gain XP for messages and voice activity.
* **Rank Cards:** Beautiful Canvas-based images for /rank, /levelup, and /top.
* **Role Rewards:** Auto-assign roles at specific levels (removes previous level roles).
* **Voice XP:** Tracks time spent in voice channels (requires 2+ people).

### 🎉 Giveaway System
* **Advanced Hosting:** Create giveaways with duration, winner count, and invite requirements.
* **Reroll & End:** Commands to end early or reroll winners.
* **Guaranteed Winner:** Ability for admins to pre-set a "forced" winner (e.g., for scripted events).
* **Requirements:** Can check if a user has invited enough people before letting them win.

### 🛡️ Moderation & Security
* **Invite Protection:** Auto-deletes Discord invite links and mutes the sender (30m for post, 60m for edit).
* **Webhook Monitor:** Auto-deletes webhooks created by unauthorized users.
* **Mute System:** Database-backed mutes (preserves mutes even after bot restart).
* **Anti-Nuke:** Prevents unauthorized administration permission changes on roles.

### 🎮 Fun & Utility
* **Status Monitor:** Auto-assigns a role if a user puts a specific link/text in their custom status.
* **CS2 Patch Notes:** Auto-posts Counter-Strike 2 updates via RSS.
* **Fun Commands:** /ping, and more.

---

## 🛠️ Key Commands

### Tickets
* /send_ticket_panel - Deploys the main ticket panel.
* /close_ticket - Closes the current ticket (moves to 'Closed' category).
* /add_to_ticket / /delete_from_ticket - Manage user access to a ticket.
* /delete_ticket - Permanently deletes a closed ticket.
* /set_category - Link a ticket type (e.g., 'general') to a Discord category ID.
* /set_role - Link an internal staff role name to a Discord role ID.

### Leveling
* /rank - Shows your current level, XP, and stats card.
* /toplvl - Displays the server leaderboard (Canvas image).
* /topvoice / /topmessages - Leaderboards for voice time and message count.
* /addxp / /setlevel - Admin commands to manage user XP.

### Giveaways
* /giveaway - Start a new giveaway (interactive wizard).
* /giveaway-end - End a giveaway immediately.
* /giveaway-reroll - Reroll a winner for an ended giveaway.
* /giveaway-setwinner - Pre-set a guaranteed winner (admin only).
* /giveaway-participants - View list of entrants.

### Moderation
* /mute / /unmute - Timed mutes (database backed).
* /invite-check - Check how many people a user has invited.
* /list_webhooks - Scan server for webhooks.

---

## ⚙️ Configuration

1. Rename config.example.py to config.py.
2. Fill in your bot token, guild ID, and channel/role IDs.
3. Customize LEVEL_REWARDS in config.py to set up role rewards.

### Database
The bot automatically creates SQLite databases (levels.db, mutes.db, giveaways.db) and JSON config files (ticket_config.json, cs2_last_patch.json) on the first run.

---

## 🚀 Installation

1. Install Python 3.10+
2. Install dependencies:
   pip install -r requirements.txt
   (Note: You also need Node.js installed for the Canvas rendering modules in render/ folder).
3. Install Node dependencies:
   cd render
   npm install
   cd ..
4. Run the bot:
   python main.py