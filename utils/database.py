import aiosqlite
from config import DB_FILE, DB_FILE_MUTE, DB_FILE_GIVEAWAY


class Database:
    def __init__(self):
        self.db = None
        self.mute_db = None
        self.giveaway_db = None

    async def setup(self):
        self.db = await aiosqlite.connect(DB_FILE)
        self.db.row_factory = aiosqlite.Row

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                userId TEXT NOT NULL,
                guildId TEXT NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                totalXp INTEGER DEFAULT 0,
                voiceMinutes INTEGER DEFAULT 0,
                PRIMARY KEY (userId, guildId)
            )
        """)
        await self.db.commit()

        self.mute_db = await aiosqlite.connect(DB_FILE_MUTE)
        self.mute_db.row_factory = aiosqlite.Row

        await self.mute_db.execute("""
            CREATE TABLE IF NOT EXISTS mutes (
                userId TEXT NOT NULL,
                guildId TEXT NOT NULL,
                roles TEXT DEFAULT '',
                mutedBy TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                mutedAt REAL DEFAULT 0,
                expiresAt REAL DEFAULT 0,
                PRIMARY KEY (userId, guildId)
            )
        """)
        await self.mute_db.commit()

        self.giveaway_db = await aiosqlite.connect(DB_FILE_GIVEAWAY)
        self.giveaway_db.row_factory = aiosqlite.Row

        await self.giveaway_db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publicId TEXT NOT NULL UNIQUE,
                guildId TEXT NOT NULL,
                channelId TEXT NOT NULL,
                messageId TEXT NOT NULL,
                hostId TEXT NOT NULL,
                hostedById TEXT NOT NULL,
                creatorId TEXT NOT NULL,
                prize TEXT NOT NULL,
                winnerCount INTEGER DEFAULT 1,
                requiredInvites INTEGER DEFAULT 0,
                endsAt REAL NOT NULL,
                ended INTEGER DEFAULT 0,
                winners TEXT DEFAULT ''
            )
        """)

        await self.giveaway_db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveawayId INTEGER NOT NULL,
                userId TEXT NOT NULL,
                PRIMARY KEY (giveawayId, userId),
                FOREIGN KEY (giveawayId) REFERENCES giveaways(id)
            )
        """)

        await self.giveaway_db.commit()

    # ========== LEVELS ==========

    async def get_user(self, user_id, guild_id):
        cursor = await self.db.execute(
            "SELECT * FROM levels WHERE userId = ? AND guildId = ?",
            (str(user_id), str(guild_id))
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def add_message_xp(self, user_id, guild_id, xp_amount):
        await self.db.execute("""
            INSERT INTO levels (userId, guildId, xp, totalXp, messages, level, voiceMinutes)
            VALUES (?, ?, ?, ?, 1, 1, 0)
            ON CONFLICT(userId, guildId) DO UPDATE SET
                xp = xp + ?, totalXp = totalXp + ?, messages = messages + 1
        """, (str(user_id), str(guild_id), xp_amount, xp_amount, xp_amount, xp_amount))
        await self.db.commit()
        return await self.get_user(user_id, guild_id)

    async def add_voice_xp(self, user_id, guild_id, xp_amount):
        await self.db.execute("""
            INSERT INTO levels (userId, guildId, xp, totalXp, voiceMinutes, level, messages)
            VALUES (?, ?, ?, ?, 1, 1, 0)
            ON CONFLICT(userId, guildId) DO UPDATE SET
                xp = xp + ?, totalXp = totalXp + ?, voiceMinutes = voiceMinutes + 1
        """, (str(user_id), str(guild_id), xp_amount, xp_amount, xp_amount, xp_amount))
        await self.db.commit()
        return await self.get_user(user_id, guild_id)

    async def level_up(self, user_id, guild_id, new_level, remaining_xp):
        await self.db.execute(
            "UPDATE levels SET level = ?, xp = ? WHERE userId = ? AND guildId = ?",
            (new_level, remaining_xp, str(user_id), str(guild_id))
        )
        await self.db.commit()

    async def set_level(self, user_id, guild_id, level):
        await self.db.execute("""
            INSERT INTO levels (userId, guildId, level, xp, totalXp, messages, voiceMinutes)
            VALUES (?, ?, ?, 0, 0, 0, 0)
            ON CONFLICT(userId, guildId) DO UPDATE SET
                level = ?, xp = 0
        """, (str(user_id), str(guild_id), level, level))
        await self.db.commit()

    async def set_xp(self, user_id, guild_id, xp):
        await self.db.execute(
            "UPDATE levels SET xp = ? WHERE userId = ? AND guildId = ?",
            (xp, str(user_id), str(guild_id))
        )
        await self.db.commit()

    async def add_xp(self, user_id, guild_id, amount):
        await self.db.execute("""
            INSERT INTO levels (userId, guildId, xp, totalXp, messages, level, voiceMinutes)
            VALUES (?, ?, ?, ?, 0, 1, 0)
            ON CONFLICT(userId, guildId) DO UPDATE SET
                xp = xp + ?, totalXp = totalXp + ?
        """, (str(user_id), str(guild_id), amount, amount, amount, amount))
        await self.db.commit()
        return await self.get_user(user_id, guild_id)

    async def get_leaderboard(self, guild_id, sort_by="level", limit=10):
        order_map = {
            "level": "level DESC, xp DESC",
            "messages": "messages DESC",
            "voiceMinutes": "voiceMinutes DESC"
        }
        order = order_map.get(sort_by, "level DESC")
        cursor = await self.db.execute(
            f"SELECT * FROM levels WHERE guildId = ? ORDER BY {order} LIMIT ?",
            (str(guild_id), limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_rank(self, user_id, guild_id):
        cursor = await self.db.execute(
            "SELECT userId FROM levels WHERE guildId = ? ORDER BY level DESC, xp DESC",
            (str(guild_id),)
        )
        rows = await cursor.fetchall()
        for i, row in enumerate(rows):
            if row["userId"] == str(user_id):
                return i + 1
        return 0

    # ========== MUTES ==========

    async def save_mute(self, user_id, guild_id, role_ids, muted_by, reason, muted_at, expires_at):
        roles_str = ",".join(str(r) for r in role_ids)
        await self.mute_db.execute("""
            INSERT INTO mutes (userId, guildId, roles, mutedBy, reason, mutedAt, expiresAt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(userId, guildId) DO UPDATE SET
                roles = ?, mutedBy = ?, reason = ?, mutedAt = ?, expiresAt = ?
        """, (
            str(user_id), str(guild_id), roles_str, str(muted_by), reason, muted_at, expires_at,
            roles_str, str(muted_by), reason, muted_at, expires_at
        ))
        await self.mute_db.commit()

    async def get_mute(self, user_id, guild_id):
        cursor = await self.mute_db.execute(
            "SELECT * FROM mutes WHERE userId = ? AND guildId = ?",
            (str(user_id), str(guild_id))
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_active_mutes(self, guild_id):
        cursor = await self.mute_db.execute(
            "SELECT * FROM mutes WHERE guildId = ?",
            (str(guild_id),)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_mute(self, user_id, guild_id):
        await self.mute_db.execute(
            "DELETE FROM mutes WHERE userId = ? AND guildId = ?",
            (str(user_id), str(guild_id))
        )
        await self.mute_db.commit()

    # ========== GIVEAWAYS ==========

    async def get_next_giveaway_number(self, guild_id):
        cursor = await self.giveaway_db.execute(
            "SELECT COUNT(*) as cnt FROM giveaways WHERE guildId = ?",
            (str(guild_id),)
        )
        row = await cursor.fetchone()
        return (row["cnt"] if row else 0) + 1

    async def create_giveaway(self, public_id, guild_id, channel_id, message_id, host_id, hosted_by_id, creator_id, prize, winner_count, required_invites, ends_at):
        cursor = await self.giveaway_db.execute("""
            INSERT INTO giveaways (publicId, guildId, channelId, messageId, hostId, hostedById, creatorId, prize, winnerCount, requiredInvites, endsAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (public_id, str(guild_id), str(channel_id), str(message_id), str(host_id), str(hosted_by_id), str(creator_id), prize, winner_count, required_invites, ends_at))
        await self.giveaway_db.commit()
        return cursor.lastrowid

    async def get_giveaway_by_message(self, message_id):
        cursor = await self.giveaway_db.execute(
            "SELECT * FROM giveaways WHERE messageId = ?",
            (str(message_id),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_giveaway_by_id(self, giveaway_id):
        cursor = await self.giveaway_db.execute(
            "SELECT * FROM giveaways WHERE id = ?",
            (giveaway_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_giveaway_by_public_id(self, public_id):
        cursor = await self.giveaway_db.execute(
            "SELECT * FROM giveaways WHERE publicId = ? COLLATE NOCASE",
            (public_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_active_giveaways(self):
        cursor = await self.giveaway_db.execute(
            "SELECT * FROM giveaways WHERE ended = 0"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def end_giveaway(self, giveaway_id, winners_str):
        await self.giveaway_db.execute(
            "UPDATE giveaways SET ended = 1, winners = ? WHERE id = ?",
            (winners_str, giveaway_id)
        )
        await self.giveaway_db.commit()

    async def add_giveaway_entry(self, giveaway_id, user_id):
        try:
            await self.giveaway_db.execute(
                "INSERT OR IGNORE INTO giveaway_entries (giveawayId, userId) VALUES (?, ?)",
                (giveaway_id, str(user_id))
            )
            await self.giveaway_db.commit()
            return True
        except Exception:
            return False

    async def remove_giveaway_entry(self, giveaway_id, user_id):
        await self.giveaway_db.execute(
            "DELETE FROM giveaway_entries WHERE giveawayId = ? AND userId = ?",
            (giveaway_id, str(user_id))
        )
        await self.giveaway_db.commit()

    async def get_giveaway_entries(self, giveaway_id):
        cursor = await self.giveaway_db.execute(
            "SELECT userId FROM giveaway_entries WHERE giveawayId = ?",
            (giveaway_id,)
        )
        rows = await cursor.fetchall()
        return [row["userId"] for row in rows]

    async def get_giveaway_entry_count(self, giveaway_id):
        cursor = await self.giveaway_db.execute(
            "SELECT COUNT(*) as cnt FROM giveaway_entries WHERE giveawayId = ?",
            (giveaway_id,)
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def update_giveaway_message_id(self, giveaway_id, message_id):
        await self.giveaway_db.execute(
            "UPDATE giveaways SET messageId = ? WHERE id = ?",
            (str(message_id), giveaway_id)
        )
        await self.giveaway_db.commit()