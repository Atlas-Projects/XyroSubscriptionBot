
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from XyroSub.database.users import set_blacklist_status
from XyroSub.helpers.decorators import sudo_users

__module_name__ = ["blacklist"]
__help_msg__ = """
<b>Module Overview:</b>
The <b>Admins Module</b> provides administrative functionalities for group chats, enabling admins to manage users, tickets, and group settings effectively.

<b>Commands for Administrators:</b>

• <code>/ban user_id</code>: Bans a user from using the bot.
• <code>/unban user_id</code>: Unbans a user from using the bot.
"""


@Client.on_message(filters.command("ban") & filters.group)
@sudo_users()
async def blacklist_user_command(client: Client, message: Message):
    try:
        user_id = int(message.text.split(' ')[1])
    except (IndexError, ValueError):
        await message.reply_text(
            "Please provide a valid user ID in the format /blacklist user_id.",
            reply_to_message_id=message.id,
        )
        return

    await set_blacklist_status(user_id, True)
    await message.reply_text(
        f"User {user_id} has been blacklisted!",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("unban") & filters.group)
@sudo_users()
async def unblacklist_user_command(client: Client, message: Message):
    try:
        user_id = int(message.text.split(' ')[1])
    except (IndexError, ValueError):
        await message.reply_text(
            "Please provide a valid user ID in the format /unblacklist user_id.",
            reply_to_message_id=message.id,
        )
        return

    await set_blacklist_status(user_id, False)
    await message.reply_text(
        f"User {user_id} has been unblacklisted!",
        reply_to_message_id=message.id,
    )