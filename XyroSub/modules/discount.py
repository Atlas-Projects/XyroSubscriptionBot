import random
import string
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message)

from XyroSub.database.discount import (change_discount_status, create_discount,
                                       delete_discount, get_act_discount,
                                       get_all_discounts, get_discount)
from XyroSub.helpers.decorators import sudo_users


def generate_discount_code(length=8):
    return ''.join(
        random.choices(string.ascii_uppercase + string.digits, k=length))


@Client.on_message(filters.command("create_discount"))
@sudo_users()
async def create_discount_start(client: Client, message: Message):
    args = message.text.split()
    if len(args) != 2:
        await message.reply_text(
            "Usage: /create_discount discount_value",
            reply_to_message_id=message.id,
        )
        return

    discount_value = int(args[1])

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Fixed",
                             callback_data=f"type-fixed-{discount_value}"),
        InlineKeyboardButton("Percentage",
                             callback_data=f"type-percentage-{discount_value}")
    ], [InlineKeyboardButton("Cancel", callback_data="cancel-process")]])

    await message.reply_text(
        "Select discount type:",
        reply_markup=keyboard,
        reply_to_message_id=message.id,
    )


@Client.on_callback_query(filters.regex(r"type-(fixed|percentage)-(\d+)"))
async def select_scope(client: Client, query: CallbackQuery):
    discount_type = query.data.split("-")[1]
    discount_value = query.data.split("-")[2]

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "User-based",
            callback_data=f"scope-user-{discount_type}-{discount_value}"),
        InlineKeyboardButton(
            "Time-based",
            callback_data=f"scope-time-{discount_type}-{discount_value}")
    ], [InlineKeyboardButton("Cancel", callback_data="cancel-process")]])

    await query.message.edit_text("Select discount scope:",
                                  reply_markup=keyboard)


@Client.on_callback_query(
    filters.regex(r"scope-(user|time)-(fixed|percentage)-(\d+)"))
async def adjust_values(client: Client, query: CallbackQuery):
    scope, discount_type, discount_value = query.data.split("-")[1:]

    if scope == "user":
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "-10",
                    callback_data=
                    f"user-dec-10-{discount_type}-{discount_value}"),
                InlineKeyboardButton(
                    "+10",
                    callback_data=
                    f"user-inc-10-{discount_type}-{discount_value}")
            ],
             [
                 InlineKeyboardButton(
                     "Done",
                     callback_data=
                     f"done-user-10-{discount_type}-{discount_value}")
             ],
             [InlineKeyboardButton("Cancel", callback_data="cancel-process")]])
        await query.message.edit_text("Set number of users (default 10):",
                                      reply_markup=keyboard)

    elif scope == "time":
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "-1hr",
                    callback_data=
                    f"time-dec-24-{discount_type}-{discount_value}"),
                InlineKeyboardButton(
                    "+1hr",
                    callback_data=
                    f"time-inc-24-{discount_type}-{discount_value}")
            ],
             [
                 InlineKeyboardButton(
                     "Done",
                     callback_data=
                     f"done-time-24-{discount_type}-{discount_value}")
             ],
             [InlineKeyboardButton("Cancel", callback_data="cancel-process")]])
        await query.message.edit_text("Set duration in hours (default 24):",
                                      reply_markup=keyboard)


@Client.on_callback_query(
    filters.regex(r"(user|time)-(inc|dec)-(\d+)-(.+)-(\d+)"))
async def adjust_value(client: Client, query: CallbackQuery):
    scope, action, value, discount_type, discount_value = query.data.split("-")
    value = int(value)

    if action == "inc":
        value += 10 if scope == "user" else 1
    elif action == "dec" and value > 0:
        value -= 10 if scope == "user" else 1

    done_callback = f"done-{scope}-{value}-{discount_type}-{discount_value}"
    if scope == "user":
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "-10",
                    callback_data=
                    f"user-dec-{value}-{discount_type}-{discount_value}"),
                InlineKeyboardButton(
                    "+10",
                    callback_data=
                    f"user-inc-{value}-{discount_type}-{discount_value}")
            ], [InlineKeyboardButton("Done", callback_data=done_callback)],
             [InlineKeyboardButton("Cancel", callback_data="cancel-process")]])
        await query.message.edit_text(f"Set number of users: {value}",
                                      reply_markup=keyboard)

    else:
        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "-1hr",
                    callback_data=
                    f"time-dec-{value}-{discount_type}-{discount_value}"),
                InlineKeyboardButton(
                    "+1hr",
                    callback_data=
                    f"time-inc-{value}-{discount_type}-{discount_value}")
            ], [InlineKeyboardButton("Done", callback_data=done_callback)],
             [InlineKeyboardButton("Cancel", callback_data="cancel-process")]])
        await query.message.edit_text(f"Set duration in hours: {value}",
                                      reply_markup=keyboard)


def generate_discount_keyboard(scope, value, discount_type, discount_value,
                               plan_scope):
    plan_scopes = ['all', 'basic', 'standard', 'premium']
    next_scope = plan_scopes[(plan_scopes.index(plan_scope) + 1) %
                             len(plan_scopes)]
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f'Discount Plan Scope: {plan_scope.capitalize()}',
                callback_data=
                f'done-{scope}-{value}-{discount_type}-{discount_value}-{next_scope}-notdone'
            )
        ],
        [
            InlineKeyboardButton(
                'Done',
                callback_data=
                f'done-{scope}-{value}-{discount_type}-{discount_value}-{plan_scope}-done'
            )
        ], [InlineKeyboardButton('Cancel', callback_data='cancel-process')]
    ])


def generate_discount_text():
    return (
        "Let\'s set the Premium Plan for which this discount would be applicable.\n"
        "• <code>All</code>: Discount would be applied to all plans.\n"
        "• <code>Basic</code>: Discount would be applied to the Basic Plan only.\n"
        "• <code>Standard</code>: Discount would be applied to the Standard Plan only.\n"
        "• <code>Premium</code>: Discount would be applicable to the Premium Plan only.\n\n"
        "Please select one from the button below.\n"
        "Once you are done, press the Done button to create the discount code."
    )


@Client.on_callback_query(
    filters.regex(
        r"^done-(user|time)-(\d+)-(fixed|percentage)-(\d+)(?:-(all|basic|standard|premium)(?:-(done|notdone)))?$"
    ))
async def finalize_discount(_: Client, query: CallbackQuery):
    data_parts = query.data.split('-')
    await query.answer()

    if len(data_parts) == 5:
        _, scope, value, discount_type, discount_value = data_parts
        await query.edit_message_text(text=generate_discount_text(),
                                      reply_markup=generate_discount_keyboard(
                                          scope, value, discount_type,
                                          discount_value, 'all'))
    else:
        _, scope, value, discount_type, discount_value, plan_scope, done_type = data_parts
        if done_type == 'done':
            max_uses = int(value) if scope == "user" else None
            expiry_time = datetime.now(timezone.utc) + timedelta(
                hours=int(value)) if scope == "time" else None
            code = generate_discount_code()

            new_discount = await create_discount(
                code=code,
                discount_type=discount_type,
                discount_value=int(discount_value),
                discount_scope=scope,
                max_uses=max_uses,
                expiry_time=expiry_time.timestamp() if expiry_time else None,
                discount_plan_type=plan_scope,
            )

            if new_discount:
                await query.message.edit_text(
                    f"Discount code '<code>{code}</code>' created successfully!"
                )
            else:
                await query.message.edit_text("Failed to create discount.")
            return
        await query.edit_message_text(text=generate_discount_text(),
                                      reply_markup=generate_discount_keyboard(
                                          scope, value, discount_type,
                                          discount_value, plan_scope))


@Client.on_callback_query(filters.regex("cancel-process"))
async def cancel_process(client: Client, query: CallbackQuery):
    await query.message.edit_text(
        "Discount creation process has been canceled.")


@Client.on_message(filters.command("activate_discount"))
@sudo_users()
async def activate_discount(client: Client, message: Message):
    args = message.text.split()

    if len(args) != 2:
        await message.reply_text(
            "Usage: /activate_discount discount_code",
            reply_to_message_id=message.id,
        )
        return

    code = args[1]
    __discount = await get_discount(discount_code=code)

    active_discount = await get_act_discount()
    active_discount_codes = []
    active_discount_plan_types = set()
    for act_discount in active_discount:
        if act_discount.discount_plan_type != 'all':
            active_discount_codes.append(act_discount.code)
            active_discount_plan_types.add(act_discount.discount_plan_type)

    if active_discount and active_discount[0] and active_discount[
            0].discount_plan_type == 'all':
        await message.reply_text(
            f"Currently, the discount '<code>{active_discount[0].code}</code>' is active.\n"
            "This discount code is valid for all Premium Tiers.\n"
            "Please deactivate it first using the command /deactivate_discount discount_code.",
            reply_to_message_id=message.id,
        )
        return

    if __discount.discount_plan_type in active_discount_plan_types:
        await message.reply_text(
            f"A discount code with scope: {__discount.discount_plan_type.capitalize()} is already active.\n\
Please deactivate it first to activate the current discount: '<code>{code}</code>'",
            reply_to_message_id=message.id,
        )
        return

    if active_discount_codes and __discount.discount_plan_type == 'all':
        await message.reply_text(
            f"You cannot activate a discount meant for all tiers when a narrower-scoped discount is activated.\n\
Currently, the discounts {'\n'.join(active_discount_codes)} are active.",
            reply_to_message_id=message.id,
        )
        return

    discount = await change_discount_status(code, True)

    if discount:
        await message.reply_text(
            f"Discount '<code>{code}</code>' has been activated.",
            reply_to_message_id=message.id,
        )
    else:
        await message.reply_text(
            f"Discount with code '<code>{code}</code>' does not exist.",
            reply_to_message_id=message.id,
        )


@Client.on_message(filters.command("deactivate_discount"))
@sudo_users()
async def deactivate_discount(client: Client, message: Message):
    args = message.text.split()

    if len(args) != 2:
        await message.reply_text(
            "Usage: /deactivate_discount discount_code",
            reply_to_message_id=message.id,
        )
        return

    code = args[1]

    discount = await change_discount_status(code, False)

    if discount:
        await message.reply_text(
            f"Discount '{code}' has been deactivated.",
            reply_to_message_id=message.id,
        )
    else:
        await message.reply_text(
            f"Discount with code '{code}' does not exist.",
            reply_to_message_id=message.id,
        )


@Client.on_message(filters.command("list_discounts"))
@sudo_users()
async def list_discounts(client: Client, message: Message):
    discounts = await get_all_discounts()

    if not discounts:
        await message.reply_text("No discounts found.",
                                 reply_to_message_id=message.id)
        return

    discount_details = []
    for idx, discount in enumerate(discounts):
        status = "Active" if discount.active else "Inactive"
        expiry = datetime.fromtimestamp(
            discount.expiry_time, tz=timezone.utc).strftime(
                '%Y-%m-%d %H:%M:%S') if discount.expiry_time else "No expiry"
        details = (
            f"{idx + 1}. Code: <code>{discount.code}</code>\n"
            f"Type: {discount.discount_type}\n"
            f"Value: {discount.discount_value}\n"
            f"Scope: {discount.discount_scope}\n"
            f"Premium Tier Scope: {discount.discount_plan_type}\n"
            f"Max Uses: {discount.max_uses if discount.max_uses else 'Unlimited'}\n"
            f"Expiry: {expiry}\n"
            f"Usage Count: {discount.usage_count}\n"
            f"Status: {status}\n"
            "-------------------------")
        discount_details.append(details)

    response = "\n\n".join(discount_details)
    await message.reply_text(response.strip(), reply_to_message_id=message.id)


@Client.on_message(filters.command("delete_discount"))
@sudo_users()
async def delete_discount_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Please provide a discount code to delete.",
                                 reply_to_message_id=message.id)
        return

    discount_code = message.command[1]

    success = await delete_discount(discount_code)

    if success:
        await message.reply_text(
            f"Discount with code '{discount_code}' has been deleted.",
            reply_to_message_id=message.id)
    else:
        await message.reply_text(
            f"No discount found with code '{discount_code}'.",
            reply_to_message_id=message.id)
