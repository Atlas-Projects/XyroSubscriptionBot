import asyncio

from pyrogram import Client, filters
from pyrogram.types import (BotCommand, BotCommandScopeAllGroupChats,
                            BotCommandScopeAllPrivateChats,
                            InlineKeyboardButton, InlineKeyboardMarkup,
                            Message)

from XyroSub import ANNOUNCE_CHANNEL, SUPPORT_BOT
from XyroSub.database.affiliate import (fetch_affiliate_settings_by_code,
                                        save_affiliate_user)
from XyroSub.database.subscription import get_all_transactions_user
from XyroSub.database.users import create_user
from XyroSub.helpers.misc import get_bot_object

PM_COMMANDS = [
    BotCommand(command='help', description='Get the help message'),
    BotCommand(command='donate', description='Feeling Generous'),
    BotCommand(command='affiliate',
               description='Get information about your affiliate settings'),
    BotCommand(command='cancel_subscription',
               description='Cancel a subscription'),
    BotCommand(command='commission',
               description='Get your affiliate commission info'),
    BotCommand(command='my_subscriptions',
               description='Get information about purchased subscriptions'),
    BotCommand(command='premium',
               description='Get information about the Premium Subscriptions'),
    BotCommand(command='refund_policy',
               description='Get the current refund policy'),
    BotCommand(command='start', description='Start the bot'),
    BotCommand(
        command='support',
        description='Get instructions to avail support from bot administrators'
    ),
    BotCommand(command='withdraw',
               description='Withdraw affiliate commission'),
]
GROUP_COMMANDS = [
    BotCommand(command='help', description='Get help with using the bot'),
    BotCommand(command='ban', description='Ban a user from using bot'),
    BotCommand(command='premium',
               description='Get information about the Premium Subscriptions'),
    BotCommand(command='unban', description='Unban a user'),
]


async def set_all_bot_commands(client: Client) -> None:
    await asyncio.sleep(10)
    await client.set_bot_commands(commands=PM_COMMANDS,
                                  scope=BotCommandScopeAllPrivateChats())
    await client.set_bot_commands(commands=GROUP_COMMANDS,
                                  scope=BotCommandScopeAllGroupChats())

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    from_user = message.from_user
    bot = await get_bot_object(client=client)
    await create_user(user_id=from_user.id)

    welcome_message = f"""
✨ <b>Hey {from_user.first_name or 'NoFirstName'}!</b> Welcome to the wonderful world of <b>{bot.full_name}</b>! ✨  
Your go-to bot for managing subscription! 🚀

"""

    if len(message.command) > 1:
        # Command has a payload
        command_payload = message.command[1]
        if len(command_payload) == 6:
            inline_keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(
                        'Bot Updates Channel',
                        url=f'https://t.me/{ANNOUNCE_CHANNEL}')
                ]])
            aff_settings = await fetch_affiliate_settings_by_code(
                affiliate_code=command_payload)
            if aff_settings:
                if aff_settings.affiliate_user == from_user.id:
                    await client.send_message(
                        chat_id=aff_settings.affiliate_user,
                        text="You cannot refer yourself!",
                    )
                else:
                    # Logic for referring another user
                    subs_user = await get_all_transactions_user(user_id=from_user.id)
                    if not subs_user:
                        await save_affiliate_user(
                            affiliate_user=aff_settings.affiliate_user,
                            referred_user=from_user.id)
            await message.reply_text(
                welcome_message,
                reply_markup=inline_keyboard,
                reply_to_message_id=message.id,
            )
            return

    await message.reply_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    'Bot Updates Channel',
                    url=f'https://t.me/{ANNOUNCE_CHANNEL}')
            ]]),
        reply_to_message_id=message.id,
    )

@Client.on_message(filters.command("start") & filters.group)
async def start(client, message: Message):
    await message.reply_text(
        "I am Alive!",
        reply_to_message_id=message.id,
    )


support_message = f"""
Hello! 

Thank you for reaching out for support. If you have any inquiries or need assistance, please feel free to communicate with us directly. 

You can reach our support team by messaging @{SUPPORT_BOT}. We are here to help you with any questions or concerns you may have. 

Best Regards,
The Support Team
"""


@Client.on_message(filters.command(["support", "paysupport"]))
async def support_handler(client: Client, message):
    await message.reply_text(
        support_message,
        reply_to_message_id=message.id,
    )
