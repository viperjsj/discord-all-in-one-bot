import discord
from config import ALLOWED_WEBHOOK_ROLES


async def can_user_create_webhook(user: discord.Member) -> bool:
    """Check if a member has a role that allows creating webhooks."""
    if not user:
        return False
    user_roles = [role.id for role in user.roles]
    return any(role_id in ALLOWED_WEBHOOK_ROLES for role_id in user_roles)


async def is_webhook_allowed(webhook: discord.Webhook, guild: discord.Guild) -> bool:
    """Check if a webhook was created by someone with an allowed role."""
    try:
        if webhook.user is None:
            print(f"[WEBHOOK] Webhook without owner: {webhook.name}")
            return False

        member = guild.get_member(webhook.user.id)
        if member is None:
            try:
                member = await guild.fetch_member(webhook.user.id)
            except Exception:
                print(f"[WEBHOOK] Can't fetch owner: {webhook.user.id}")
                return False

        allowed = await can_user_create_webhook(member)
        if allowed:
            print(f"[WEBHOOK] Webhook allowed by {member.name} (ID: {member.id})")
        return allowed

    except Exception as e:
        print(f"[WEBHOOK ERROR] Error checking webhook: {e}")
        return False