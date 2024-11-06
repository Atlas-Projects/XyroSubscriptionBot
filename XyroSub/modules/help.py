from typing import Dict, List

from pyrogram import Client, filters
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message)

from XyroSub.helpers.misc import get_bot_object, load_modules

PER_PAGE = 6


@Client.on_message(filters.command("help"))
async def help_command(client: Client, message: Message) -> None:
    modules = await load_modules()
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) > 1:
        requested_module = command_parts[1].lower()
        for module in modules:
            if requested_module in [name.lower() for name in module['name']]:
                await message.reply_text(module['help_msg'],
                reply_to_message_id=message.id,
            )
                return

    user_id = message.from_user.id
    await handle_help(client=client,
                      message=message,
                      callback_query=None,
                      modules=modules,
                      page=0,
                      user_id=user_id)


async def handle_help(client: Client,
                      message: Message = None,
                      callback_query: CallbackQuery = None,
                      modules: List[Dict[List[str], str]] = None,
                      page: int = 0,
                      user_id: int = None) -> None:
    bot_username = (await get_bot_object(client=client)).full_name
    start = page * PER_PAGE
    end = start + PER_PAGE
    paginated_modules = modules[start:end]

    buttons = []
    for i, mod in enumerate(paginated_modules):
        if i % 3 == 0:
            buttons.append([])
        buttons[-1].append(
            InlineKeyboardButton(mod["name"][0].capitalize(),
                                 callback_data=f"help_{i + start}_{user_id}"))

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"help_page_{page - 1}_{user_id}"))
    if end < len(modules):
        navigation_buttons.append(
            InlineKeyboardButton(
                "Next ➡️", callback_data=f"help_page_{page + 1}_{user_id}"))

    if navigation_buttons:
        buttons.append(navigation_buttons)

    markup = InlineKeyboardMarkup(buttons)
    if message:
        await message.reply_text(f"Here's the help for {bot_username}",
                                 reply_markup=markup,
                                 reply_to_message_id=message.id,
            )
    elif callback_query:
        await callback_query.answer()
        await callback_query.message.edit_text(
            f"Here's the help for {bot_username}", reply_markup=markup)


@Client.on_callback_query(filters.regex(r"help_page_(\d+)_(\d+)"))
async def paginate_help(client: Client, callback_query: CallbackQuery) -> None:
    page, user_id = int(callback_query.data.split("_")[2]), int(
        callback_query.data.split("_")[3])

    if callback_query.from_user.id != user_id:
        await callback_query.answer("You cannot interact with this help menu.",
                                    show_alert=True)
        return

    modules = await load_modules()
    await callback_query.answer()
    await handle_help(client=client,
                      callback_query=callback_query,
                      modules=modules,
                      user_id=user_id,
                      page=page)


@Client.on_callback_query(filters.regex(r"help_(\d+)_(\d+)"))
async def show_help_detail(_: Client, callback_query: CallbackQuery) -> None:
    module_idx, user_id = int(callback_query.data.split("_")[1]), int(
        callback_query.data.split("_")[2])

    if callback_query.from_user.id != user_id:
        await callback_query.answer(
            "You cannot interact with this help message.", show_alert=True)
        return

    modules = await load_modules()
    await callback_query.answer()
    help_msg = modules[module_idx]["help_msg"]
    module_idx = module_idx // PER_PAGE

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Go Back ⬅️",
                             callback_data=f"help_page_{module_idx}_{user_id}")
    ]])

    await callback_query.message.edit_text(help_msg, reply_markup=markup)
