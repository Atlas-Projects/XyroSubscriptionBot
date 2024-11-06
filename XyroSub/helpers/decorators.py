from pyrogram.client import Client
from pyrogram.types import CallbackQuery, Message

from XyroSub import OWNER_ID, SUDO_USERS
from XyroSub.database.users import is_user_blacklisted


def sudo_users():

    def decorator(func):

        async def wrapper(client: Client, *args):
            if isinstance(args[0], Message):
                user = args[0].from_user
                user_id = args[0].from_user.id
                chat_id = args[0].chat.id
            elif isinstance(args[0], CallbackQuery):
                user = args[0].from_user
                user_id = args[0].from_user.id
                chat_id = args[0].message.chat.id
            else:
                return

            if user.is_self:
                return

            if user_id != OWNER_ID and user_id not in SUDO_USERS:
                return
            return await func(client, *args)

        return wrapper

    return decorator


def check_blacklist():

    def decorator(func):

        async def wrapper(client: Client, message: Message):
            user_id = message.from_user.id
            if await is_user_blacklisted(user_id):
                await message.reply_text(
                    "You are blacklisted from using this bot.",
                    reply_to_message_id=message.id,
                )
                return
            return await func(client, message)

        return wrapper

    return decorator