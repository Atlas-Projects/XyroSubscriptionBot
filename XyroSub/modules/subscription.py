import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Union

from dateutil import relativedelta
from pyrogram import filters, types
from pyrogram.client import Client
from pyrogram.errors import PeerIdInvalid, UserNotParticipant
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message, PreCheckoutQuery)
from uuid_extensions import uuid7

from XyroSub import (BASIC_PLAN_DAYS, BASIC_PLAN_PRICE, GROUP_ID, OWNER_ID,
                     PREMIUM_CHANNEL, PREMIUM_PLAN_DAYS, PREMIUM_PLAN_PRICE,
                     STANDARD_PLAN_DAYS, STANDARD_PLAN_PRICE, SUPPORT_BOT,
                     TOPIC_ID, SUDO_USERS, logger)
from XyroSub.database.affiliate import (get_affiliate_settings, get_affiliate_user,
                                        add_referral, delete_affiliate_user,
                                        get_commission_info, modify_earnings,
                                        get_referral_by_short_id)
from XyroSub.database.discount import (get_active_discount, get_discount_by_id,
                                       get_discount_usage, save_discount_usage,
                                       update_discount_usage)
from XyroSub.database.subscription import (Subscriptions, delete_transaction,
                                           get_all_subscriptions,
                                           get_transaction,
                                           get_transaction_by_short_id,
                                           has_active_subscription,
                                           mark_for_cancellation,
                                           save_transaction,
                                           update_cancel_on_next_invoice,
                                           update_next_invoice_date,
                                           update_transaction)
from XyroSub.database.users import (check_refund_eligibility,
                                    create_invite_link, delete_invite_link,
                                    get_invite_link, mark_refund_used)
from XyroSub.helpers.decorators import check_blacklist, sudo_users

__module_name__ = [
    "subscription", "premium", "payment", "donate"
]
__help_msg__ = """<b>Module Overview:</b>
This module facilitates the management of subscriptions for users who wish to upgrade to premium status in the support bot.
Users can subscribe to premium plans, manage their active subscriptions, and handle payment processes.

<b>Available Commands:</b>
• <code>/subscribe</code>: Display subscription options for users to choose between "One Chat" and "Unlimited Chats".
• <code>/my_subscriptions</code>: Check all your active subscriptions.
• <code>/cancel_subscription Token</code>: Cancel a subscription using its token.
• <code>/refund_policy</code>: Check the refund policy details.

<b>Important notes:</b>
- Users may only request a refund within 3 days from their payment date.

For further details or specific inquiries, you can use the following ways to get help:
• <code>/help subscription</code>
• <code>/help premium</code>
"""

premium_message = """
✨ <b>Hey {0}!</b> Thinking about going Premium? You\'ll unlock a treasure trove of amazing features!: ✨

🚀 <b>Premium Plans</b> come in three awesome flavors:
1. <b>Basic</b>: Bills Monthly - <b>{1} XTR ⭐️ (${2} USD)</b>
2. <b>Standard</b>: Bills Quarterly - <b>{3} XTR ⭐️ (${4} USD)</b>
3. <b>Premium</b>: Bills Half-Yearly - <b>{5} XTR ⭐️ (${6} USD)</b>

And guess what? All Premium Plans come with a **no-questions-asked** 3-day refund policy. 💸  

<b>For any subscription or bot-related queries, you can contact us at @{7}</b>.

{8}
"""

def convert_xtr_to_usd(xtr_price: int) -> int:
    usd_price = xtr_price * 0.013
    return round(usd_price)


BASIC_USD_PRICE = convert_xtr_to_usd(BASIC_PLAN_PRICE)
STANDARD_USD_PRICE = convert_xtr_to_usd(STANDARD_PLAN_PRICE)
PREMIUM_USD_PRICE = convert_xtr_to_usd(PREMIUM_PLAN_PRICE)


def is_uuid7(transaction_id: str) -> bool:
    return bool(
        re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            transaction_id))


async def validate_transaction(transaction: Subscriptions, user_id: int):
    if transaction.user_id != user_id:
        return False
    return True

async def process_refund_confirmation(messageable: Union[Message,
                                                         CallbackQuery],
                                      short_id: str):
    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        if isinstance(messageable, Message):
            await messageable.reply_text("Transaction ID not found.")
        else:
            await messageable.answer("Transaction ID not found.")
        return

    confirm_button = InlineKeyboardButton(
        "Confirm", callback_data=f"confirm_refund_{short_id}")
    back_button = InlineKeyboardButton("Back",
                                       callback_data=f"back_{short_id}")
    keyboard = InlineKeyboardMarkup([[confirm_button, back_button]])

    if isinstance(messageable, Message):
        await messageable.reply_text(
            "Are you sure you want to refund this transaction?",
            reply_markup=keyboard)
    else:
        await messageable.message.edit_text(
            "Are you sure you want to refund this transaction?",
            reply_markup=keyboard)


async def get_discount_message(user_id: int) -> str:
    """Generate the discount message for a user if applicable."""
    discount_message = ""
    available_discounts = await get_active_discount(user_id)
    for discount in available_discounts:
        used_discount = await get_discount_usage(discount.id,
                                                 user_id) if discount else None
        if discount and discount.active and not used_discount:
            if discount.discount_type == 'percentage':
                discount_message += f"<b>A discount of {discount.discount_value}% is being applied on {discount.discount_plan_type} {'tiers' if discount.discount_plan_type == 'all' else 'tier'}!</b>\n"
            else:
                discount_message += f"<b>A discount of {discount.discount_value} XTR is being applied on {discount.discount_plan_type} {'tiers' if discount.discount_plan_type == 'all' else 'tier'}!</b>\n"
    if discount_message:
        discount_message += "<u>Note:</u> The discount will be visible once you press any of the buttons.\n\
The discount would be a <b>recurring discount</b>."

    return discount_message


async def affiliate_commission_helper(client: Client,
                                      user_id: int,
                                      previous_datetime: float,
                                      amount: float,
                                      short_id: str,
                                      recurring: bool = False) -> None:
    affiliate_user = await get_affiliate_user(referred_user=user_id)
    
    if affiliate_user and affiliate_user.affiliate_user != user_id:
        current_datetime = datetime.now(timezone.utc).timestamp()
        current_datetime = datetime.fromtimestamp(current_datetime)
        previous_datetime = datetime.fromtimestamp(previous_datetime)

        affiliate_amount = 0.0
        _, referred_users, _ = await get_commission_info(
            affiliate_user=affiliate_user.affiliate_user)
        relative_months = relativedelta.relativedelta(current_datetime,
                                                      previous_datetime).months
        if referred_users >= 1 and referred_users <= 4 and relative_months <= 12:
            affiliate_amount = amount * 0.1
        elif referred_users >= 5 and referred_users <= 9 and relative_months <= 18:
            affiliate_amount = amount * 0.15
        elif referred_users >= 10:
            affiliate_amount = amount * 0.15

        existing_referral = await add_referral(affiliate_user.affiliate_user, user_id, affiliate_amount, short_id)

        if recurring:
            await modify_earnings(
                affiliate_user=affiliate_user.affiliate_user,
                earnings=affiliate_amount,
            )
            await client.send_message(
                chat_id=affiliate_user.affiliate_user,
                text=f"A user you have referred: <code>{user_id}</code> renewed their subscription.\nYou have earned a commission of {affiliate_amount} XTR!"
            )
        else:
            if existing_referral:
                await modify_earnings(
                    affiliate_user=affiliate_user.affiliate_user,
                    earnings=affiliate_amount,
                )
                await client.send_message(
                    chat_id=affiliate_user.affiliate_user,
                    text=f"A user you have referred: <code>{user_id}</code> bought a new subscription.\nYou have earned a commission of {affiliate_amount} XTR!"
                )
            else:
                await client.send_message(
                    chat_id=affiliate_user.affiliate_user,
                    text=f"A user you have referred: <code>{user_id}</code> tried to reuse your referral link for a new subscription.\nNo bonus is applied as this is a repeat subscription."
                )


@Client.on_message(filters.command(["premium", "subscribe"]))
@check_blacklist()
async def subscribe_handler(_: Client, message: Message):
    from_user = message.from_user

    if await has_active_subscription(from_user.id):
        await message.reply_text("You already have an active subscription. Please cancel your current subscription before purchasing a new one.")
        return
    
    discount_message = await get_discount_message(from_user.id)

    buttons = []

    if BASIC_PLAN_PRICE is not None and BASIC_PLAN_PRICE > 0:
        basic_button = InlineKeyboardButton(
            f"Basic - {BASIC_PLAN_PRICE} XTR ⭐️ (billed monthly)",
            callback_data=f"subscribe:basic:{from_user.id}"
        )
        buttons.append([basic_button])
    
    if STANDARD_PLAN_PRICE is not None and STANDARD_PLAN_PRICE > 0:
        standard_button = InlineKeyboardButton(
            f"Standard - {STANDARD_PLAN_PRICE} XTR ⭐️ (billed quarterly)",
            callback_data=f"subscribe:standard:{from_user.id}"
        )
        buttons.append([standard_button])
    
    if PREMIUM_PLAN_PRICE is not None and PREMIUM_PLAN_PRICE > 0:
        premium_button = InlineKeyboardButton(
            f"Premium - {PREMIUM_PLAN_PRICE} XTR ⭐️ (billed half yearly)",
            callback_data=f"subscribe:premium:{from_user.id}"
        )
        buttons.append([premium_button])

    keyboard = InlineKeyboardMarkup(buttons)
    
    premium_message_txt = premium_message.format(
        from_user.first_name or 'NoFirstName', BASIC_PLAN_PRICE,
        BASIC_USD_PRICE, STANDARD_PLAN_PRICE, STANDARD_USD_PRICE,
        PREMIUM_PLAN_PRICE, PREMIUM_USD_PRICE, SUPPORT_BOT, discount_message)

    await message.reply_text(
        premium_message_txt,
        reply_markup=keyboard,
        reply_to_message_id=message.id,
    )


@Client.on_callback_query(
    filters.regex(r"^subscribe:(basic|standard|premium):(\d+)$"))
async def plan_selection_handler(client: Client,
                                 callback_query: CallbackQuery):
    try:
        plan_type, user_id = callback_query.data.split(":")[1:]
        user_id = int(user_id)
        if user_id != callback_query.from_user.id:
            await callback_query.answer("This button is not meant for you")
            return

        if await has_active_subscription(user_id):
            await callback_query.answer("You already have an active subscription. Please cancel your current subscription before purchasing a new one.")
            return
        
        recurring_interval = 0
        if plan_type == "basic":
            recurring_interval = BASIC_PLAN_DAYS
            title = "Basic Subscription - 1 Month"
            price = BASIC_PLAN_PRICE
        elif plan_type == "standard":
            recurring_interval = STANDARD_PLAN_DAYS
            title = "Standard Subscription - 3 Months"
            price = STANDARD_PLAN_PRICE
        elif plan_type == "premium":
            recurring_interval = PREMIUM_PLAN_DAYS
            title = "Premium Subscription - 6 Months"
            price = PREMIUM_PLAN_PRICE

        active_discounts = await get_active_discount(user_id)
        discount_amount = 0
        __used_discount = None

        for active_discount in active_discounts:
            if active_discount.max_uses and active_discount.usage_count >= active_discount.max_uses:
                discount_amount = 0
                continue

            if active_discount and active_discount.active:
                used_discount = await get_discount_usage(
                    discount_id=active_discount.id, user_id=user_id)
                if used_discount:
                    discount_amount = 0
                    continue
                elif not used_discount and active_discount.discount_plan_type == 'all':
                    if active_discount.discount_type == 'percentage':
                        discount_amount = round(
                            (price * active_discount.discount_value) / 100)
                    else:
                        discount_amount = active_discount.discount_value
                    __used_discount = active_discount
                    break
                elif not used_discount:
                    if active_discount.discount_plan_type == plan_type:
                        if active_discount.discount_type == 'percentage':
                            discount_amount = round(
                                (price * active_discount.discount_value) / 100)
                        else:
                            discount_amount = active_discount.discount_value
                        __used_discount = active_discount
                        break

        __affiliate_discount = 0.0
        aff_settings = await get_affiliate_settings(affiliate_user=user_id)
        if aff_settings and aff_settings.earnings and aff_settings.earnings > 0.0:
            __affiliate_discount = aff_settings.earnings

        __initial_price = round(price - discount_amount)
        if (int(round(__affiliate_discount))) < round(price - discount_amount):
            price = max(
                0,
                round(price - discount_amount -
                      int(round(__affiliate_discount))))
        else:
            price = max(
                0,
                round(price - discount_amount -
                      round(price - discount_amount - 1)))

        description = f"{title} for Support Bot Premium"
        prices = [types.LabeledPrice(label=title, amount=price)]

        if __affiliate_discount > 0.0:
            if (int(round(__affiliate_discount))) < __initial_price:
                description += f'. Using affiliate commission of {int(round(__affiliate_discount))} XTR'
            else:
                description += f'. Using affiliate commission of {__initial_price - 1} XTR'
                __affiliate_discount = __initial_price - 1

        invoice_msg = await client.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=
            f"New Subscription {plan_type}|discount_used:{discount_amount > 0}|discount_id:{__used_discount.id if __used_discount else None}|aff_discount:{round(__affiliate_discount)}",
            currency="XTR",
            prices=prices,
            start_parameter="start",
        )

        await callback_query.answer()
        await callback_query.message.edit_text(
            f"Invoice for {price} XTR ({title}) has been sent to you.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Go Back ⬅️",
                    callback_data=f'back:subs:{user_id}:{invoice_msg.id}')
            ]]),
        )
    except Exception as e:
        await callback_query.answer(f"Error: {e}", show_alert=True)
        print(f"Error handling callback query: {e}")


@Client.on_callback_query(filters.regex(r'^back:subs:(\d+):(\d+)$'))
async def handle_subscribe_back_btn(client: Client,
                                    query: CallbackQuery) -> None:
    _, _, user_id, invoice_msg_id = query.data.split(":")
    if int(user_id) != query.from_user.id:
        await query.answer("This button is not meant for you")
        return
    await client.delete_messages(chat_id=int(user_id),
                                 message_ids=int(invoice_msg_id))
    await query.answer()

    discount_message = await get_discount_message(query.from_user.id)

    premium_msg_txt = premium_message.format(
        query.from_user.first_name or 'NoFirstName', BASIC_PLAN_PRICE,
        BASIC_USD_PRICE, STANDARD_PLAN_PRICE, STANDARD_USD_PRICE,
        PREMIUM_PLAN_PRICE, PREMIUM_USD_PRICE, SUPPORT_BOT, discount_message)

    basic_button = InlineKeyboardButton(
        f"Basic - {BASIC_PLAN_PRICE} XTR ⭐️ (billed monthly)",
        callback_data=f"subscribe:basic:{query.from_user.id}")
    standard_button = InlineKeyboardButton(
        f"Standard - {STANDARD_PLAN_PRICE} XTR ⭐️ (billed quarterly)",
        callback_data=f"subscribe:standard:{query.from_user.id}")
    premium_button = InlineKeyboardButton(
        f"Premium - {PREMIUM_PLAN_PRICE} XTR ⭐️ (billed half-yearly)",
        callback_data=f"subscribe:premium:{query.from_user.id}")

    keyboard = InlineKeyboardMarkup([
        [basic_button],
        [standard_button],
        [premium_button],
    ])

    await query.edit_message_text(text=premium_msg_txt, reply_markup=keyboard)

@Client.on_pre_checkout_query()
async def pre_checkout_query_handler(_: Client,
                                     pre_checkout_query: PreCheckoutQuery):
    from_user = pre_checkout_query.from_user
    invoice_payload = pre_checkout_query.invoice_payload

    if invoice_payload.startswith("donation_"):
        await pre_checkout_query.answer(ok=True)
        return
    
    if not invoice_payload.startswith('recurring_invoice_'):
        invoice_payload_split = invoice_payload.split('|')

        aff_earnings = 0
        aff_settings = await get_affiliate_settings(affiliate_user=from_user.id
                                                    )
        if aff_settings and aff_settings.earnings:
            aff_earnings = aff_settings.earnings
        if round(aff_earnings) < round(
                float(invoice_payload_split[-1].split(':')[1])):
            await pre_checkout_query.answer(
                ok=False,
                error_message=
                "Your affiliate commission is less than the invoice discount.\n\
    Please generate a new invoice.")
            return

        discount_id = invoice_payload_split[-2].split(':')[1]
        if discount_id != 'None':
            __discount_obj = await get_discount_by_id(
                discount_id=int(discount_id))
            datetime_now = datetime.now(timezone.utc).timestamp()
            if __discount_obj.active == False or (
                    __discount_obj.expiry_time is not None
                    and __discount_obj.expiry_time < datetime_now
            ) or (__discount_obj.max_uses is not None
                  and __discount_obj.usage_count == __discount_obj.max_uses):
                await pre_checkout_query.answer(
                    ok=False,
                    error_message=
                    "An applied discount in the invoice is no longer active.\n\
    Please generate a new invoice.")
                return
    else:
        invoice_payload_split = invoice_payload.split('_')

        if len(invoice_payload_split) >= 5:
            invoice_creation_time = float(invoice_payload_split[-1])

        if invoice_creation_time:
            time_elapsed = datetime.now(timezone.utc).timestamp() - invoice_creation_time
            if time_elapsed > 86400:
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="This invoice has expired. Please generate a new one."
                )
                return
            
        aff_earnings = 0
        aff_settings = await get_affiliate_settings(affiliate_user=from_user.id
                                                    )
        if aff_settings and aff_settings.earnings:
            aff_earnings = aff_settings.earnings
        if round(aff_earnings) < round(float(invoice_payload_split[-2])):
            await pre_checkout_query.answer(
                ok=False,
                error_message=
                "Your affiliate commission is less than the invoice discount.\n\
    Please generate a new invoice.")
            return

    await pre_checkout_query.answer(ok=True)


@Client.on_message(filters.successful_payment)
async def successful_payment_handler(client: Client, message: Message):
    transaction_id = message.successful_payment.telegram_payment_charge_id
    user_id = message.from_user.id
    chat_id = message.chat.id
    amount = message.successful_payment.total_amount
    payment_date = datetime.now(timezone.utc)

    payload_data = message.successful_payment.invoice_payload.split("|")
    plan_type = payload_data[0].split()[-1]

    if payload_data[0].startswith("donation_"):
        donation_amount = int(payload_data[0].split("_")[1])
        await client.send_message(
            user_id,
            f"Thank you for your generous donation of {donation_amount} XTR! Your contribution helps us to maintain and improve our services."
        )
        await client.send_message(
            GROUP_ID,
            f"💰 <b>New Donation Received</b>: \n\n"
            f"• User ID: {user_id}\n"
            f"• Amount: {donation_amount} XTR"
        )
        return
    
    plan_type_cleaned = plan_type.split('|')[0]

    recurring_interval = 0
    if plan_type_cleaned == "basic":
        recurring_interval = BASIC_PLAN_DAYS
    elif plan_type_cleaned == "standard":
        recurring_interval = STANDARD_PLAN_DAYS
    elif plan_type_cleaned == "premium":
        recurring_interval = PREMIUM_PLAN_DAYS

    next_invoice_date = payment_date + timedelta(days=recurring_interval)

    discount_used = "discount_used:True" in payload_data
    try:
        commission_used = "aff_discount:" in payload_data[3]
    except IndexError:
        commission_used = False

    if discount_used:
        discount_id = int(payload_data[2].split(':')[1])
        active_discounts = await get_active_discount(user_id)
        for active_discount in active_discounts:
            if active_discount.id == discount_id:
                await update_discount_usage(active_discount.code)
                await save_discount_usage(active_discount.id, user_id)
                break

    if commission_used:
        commission_amount = round(float(payload_data[3].split(':')[1]))
        if commission_amount > 0:
            await modify_earnings(affiliate_user=user_id,
                                  earnings=-commission_amount)
            amount = amount + commission_amount
  
    if message.successful_payment.invoice_payload.startswith(
            "recurring_invoice_"):
        payment_payload = message.successful_payment.invoice_payload
        short_id = payment_payload.split("_")[2]
        affiliate_discount = round(float(payment_payload.split("_")[4]))
        existing_transaction = await get_transaction_by_short_id(short_id)
        recurring_interval = existing_transaction.recurring_interval
        next_invoice_date = payment_date + timedelta(days=recurring_interval)

        if existing_transaction:
            await update_transaction(existing_transaction.transaction_id,
                                     transaction_id,
                                     (amount + affiliate_discount),
                                     payment_date.timestamp(),
                                     next_invoice_date.timestamp())
            if affiliate_discount > 0.0:
                await modify_earnings(
                    affiliate_user=user_id,
                    earnings=-affiliate_discount,
                )
            await affiliate_commission_helper(
                client=client,
                user_id=user_id,
                previous_datetime=existing_transaction.first_time_payment,
                amount=amount,
                short_id=short_id,
                recurring=True,
            )

            await client.send_message(
                chat_id, f"Thank you for your payment!\n\n"
                f"Next invoice date: {next_invoice_date.strftime('%Y-%m-%d')}")

            try:
                await client.get_chat_member(PREMIUM_CHANNEL, user_id)
                pass
            except UserNotParticipant:
                invite_link = await client.create_chat_invite_link(
                    chat_id=PREMIUM_CHANNEL,
                    expire_date=datetime.now(timezone.utc) + timedelta(days=1),
                    member_limit=1
                )
                await client.send_message(
                    user_id,
                    f"Here is your invite link to the Premium Channel: {invite_link.invite_link}"
                )

                await create_invite_link(user_id, invite_link.invite_link)

            refund_button = InlineKeyboardButton(
                "Refund", callback_data=f"refund_{short_id}")
            keyboard = InlineKeyboardMarkup([[refund_button]])

            await client.send_message(
                GROUP_ID, f"🔄 <b>Subscription Renewal Notification</b>: \n\n"
                f"• Action: Subscription Renewed\n"
                f"• User ID: {user_id}\n"
                f"• Subscription Token: {short_id}\n"
                f"• Next Invoice Date: {next_invoice_date.strftime('%Y-%m-%d')}\n"
                f"• Renewed On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• Amount Charged: {amount} XTR\n"
                f"• Plan Type: {existing_transaction.plan_type.capitalize()}",
                reply_to_message_id=TOPIC_ID)

            return
    else:
        short_id = str(uuid7())

    plan_type_cleaned = plan_type.split('|')[0]

    await save_transaction(transaction_id, short_id, user_id, amount,
                           payment_date.timestamp(),
                           next_invoice_date.timestamp(), plan_type_cleaned,
                           recurring_interval)
    await affiliate_commission_helper(
        client=client,
        user_id=user_id,
        previous_datetime=payment_date.timestamp(),
        amount=amount,
        short_id=short_id,
        recurring=False,
    )

    refund_button = InlineKeyboardButton("Refund",
                                         callback_data=f"refund_{short_id}")
    keyboard = InlineKeyboardMarkup([[refund_button]])

    await client.send_message(
        GROUP_ID, f"🆕 <b>New Subscription Notification</b>: \n\n"
        f"• Action: New Subscription Created\n"
        f"• User ID: {user_id}\n"
        f"• Plan Type: {plan_type.capitalize()}\n"
        f"• Subscription Token: {short_id}\n"
        f"• Created On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=keyboard,
        reply_to_message_id=TOPIC_ID)

    await client.send_message(
        chat_id, f"Thank you for your payment!\n\n"
        f"**Next Invoice Date:** {next_invoice_date.strftime('%Y-%m-%d')}\n\n")

    try:
        await client.get_chat_member(PREMIUM_CHANNEL, user_id)
        await client.send_message(user_id,
                                    "You are already a member of the Premium Channel.")
    except UserNotParticipant:
        invite_link = await client.create_chat_invite_link(
            chat_id=PREMIUM_CHANNEL,
            expire_date=datetime.now(timezone.utc) + timedelta(days=1),
            member_limit=1
        )
        await client.send_message(
            user_id,
            f"Here is your invite link to the Premium Channel: {invite_link.invite_link}"
        )
        await create_invite_link(user_id, invite_link.invite_link)

async def send_invoice(client: Client, user_id: int, amount: int,
                       short_id: str, plan_type: str,
                       affiliate_discount: float):
    title = "Recurring Invoice"
    descriptions = {
        'basic':
        "Basic Plan - Billed monthly.",
        'standard':
        "Standard Plan - Billed quarterly.",
        'premium':
        "Premium Plan - Billed half-yearly."
    }

    description = descriptions.get(plan_type.lower(),
                                   "Default description for plan type.")

    if affiliate_discount > 0.0:
        affiliate_discount = round(affiliate_discount)
        if affiliate_discount < amount:
            amount = amount - affiliate_discount
        else:
            affiliate_discount = amount - 1
            amount = 1
        description += f'. Using affiliate commission of {affiliate_discount} XTR'

    prices = [types.LabeledPrice(label=title, amount=amount)]

    invoice_creation_time = datetime.now(timezone.utc).timestamp()

    await client.send_invoice(
        chat_id=user_id,
        title=title,
        description=description,
        payload=
        f"recurring_invoice_{short_id}_{plan_type}_{affiliate_discount}_{invoice_creation_time}",
        currency="XTR",
        prices=prices,
        start_parameter="start")


@Client.on_callback_query(filters.regex(r"^refund_(\S+)"))
async def refund_confirmation_handler(client: Client, callback_query: CallbackQuery):
    short_id = callback_query.data.split("_")[1]
    transaction = await get_transaction_by_short_id(short_id)

    if not transaction:
        await callback_query.answer("Transaction ID not found.")
        return
    
    user_id = callback_query.from_user.id

    if transaction.user_id != user_id and user_id != OWNER_ID and user_id not in SUDO_USERS:
        await callback_query.answer("You do not have permission to refund this subscription.")
        return

    await process_refund_confirmation(callback_query, short_id)


@Client.on_callback_query(filters.regex(r"^confirm_refund_(\S+)"))
async def confirm_refund_handler(client: Client,
                                 callback_query: CallbackQuery):
    short_id = callback_query.data.split("_")[2]
    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await callback_query.answer("Transaction ID not found.")
        return

    user_id = transaction.user_id

    eligible_for_refund = await check_refund_eligibility(user_id)
    if not eligible_for_refund:
        await callback_query.answer(
            "You have already issued refund once before, we allow refund only once. For further details contact Bot Support."
        )
        return

    current_date = datetime.now(timezone.utc).timestamp()
    first_time_payment_date = transaction.first_time_payment
    time_since_first_payment = current_date - first_time_payment_date

    if timedelta(seconds=time_since_first_payment) > timedelta(days=3):
        await callback_query.answer(
            "Refund period has expired. You can only request a refund within 3 days of the first payment."
        )
        return

    refund_success = await client.refund_star_payment(
        user_id=user_id, telegram_payment_charge_id=transaction.transaction_id)

    if refund_success:
        referral_info = await get_referral_by_short_id(short_id)
        if referral_info:
            affiliate_user_id = referral_info.affiliate_user_id
            amount_earned = referral_info.amount_earned

            await modify_earnings(affiliate_user_id, -amount_earned)

            await client.send_message(
                affiliate_user_id,
                f"A refund has been processed for user ID <code>{user_id}</code>. "
                f"You have lost {amount_earned} XTR from your earnings."
            )

        await delete_transaction(transaction.transaction_id)
        await delete_affiliate_user(user_id)

        if not await mark_refund_used(user_id):
            logger.error(
                f"Failed to mark refund as used for user {user_id} and transaction {transaction.transaction_id}."
            )

    invite_link_entry = await get_invite_link(user_id)

    if invite_link_entry:
        await client.ban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=user_id)
        await asyncio.sleep(1)
        await client.unban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=user_id)

        await client.revoke_chat_invite_link(
            chat_id=PREMIUM_CHANNEL,
            invite_link=invite_link_entry.invite_link
        )

        await delete_invite_link(user_id)
                
        await callback_query.message.edit_text(
            "Transaction refunded successfully.")
        await client.send_message(
            chat_id=user_id,
            text=
            f"Your transaction {transaction.transaction_id} has been refunded successfully."
        )

        await client.send_message(
            GROUP_ID, f"💰 <b>Refund Notification</b>: \n\n"
            f"• Action: Refund Processed\n"
            f"• User ID: {user_id}\n"
            f"• Transaction ID: {transaction.transaction_id}\n"
            f"• Amount Refunded: {transaction.amount} XTR\n"
            f"• Refund Processed On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            reply_to_message_id=TOPIC_ID)

    else:
        await callback_query.message.edit_text("Failed to refund transaction.")


@Client.on_callback_query(filters.regex(r"^back_(\S+)"))
async def back_refund_handler(_: Client, callback_query: CallbackQuery):
    short_id = callback_query.data.split("_")[1]
    refund_button = InlineKeyboardButton("Refund",
                                         callback_data=f"refund_{short_id}")
    keyboard = InlineKeyboardMarkup([[refund_button]])

    transaction = await get_transaction_by_short_id(short_id)
    if transaction:
        await callback_query.message.edit_text(
            f"🆕 <b>New Subscription Notification</b>: \n\n"
            f"• Action: New Subscription Created\n"
            f"• User ID: {transaction.user_id}\n"
            f"• Plan Type: {transaction.plan_type.capitalize()}\n"
            f"• Subscription Token: {short_id}\n"
            f"• Created On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=keyboard)

    else:
        await callback_query.message.edit_text("Transaction not found.")


@Client.on_message(filters.command("refund"))
@sudo_users()
async def refund_handler(_: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "Please provide the transaction ID.",
            reply_to_message_id=message.id,
        )
        return

    transaction_id = message.command[1]

    if not await get_transaction(transaction_id):
        await message.reply_text(
            "Invalid transaction ID.",
            reply_to_message_id=message.id,
        )
        return

    if is_uuid7(transaction_id):
        await message.reply_text(
            "Refund cannot be processed for manual subscriptions.",
            reply_to_message_id=message.id,
        )
        return

    short_id = (await get_transaction(transaction_id=transaction_id)).short_id
    await process_refund_confirmation(message, short_id)


@Client.on_message(filters.command("my_subscriptions"))
async def my_subscriptions_handler(client, message):
    user_id = message.from_user.id
    subscriptions = await get_all_subscriptions()
    user_subscriptions = [
        sub for sub in subscriptions if sub.user_id == user_id
    ]

    if not user_subscriptions:
        await message.reply_text(
            "You have no active subscriptions.",
            reply_to_message_id=message.id,
        )
        return

    keyboard = []
    for sub in user_subscriptions:
        button = InlineKeyboardButton(
            f"Token: {sub.short_id}",
            callback_data=f"subscription_info:{sub.short_id}")
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "Your active subscriptions:",
        reply_markup=reply_markup,
        reply_to_message_id=message.id,
    )


@Client.on_callback_query(filters.regex(r"^subscription_info:(\S+)$"))
async def subscription_info_handler(client, callback_query):
    short_id = callback_query.data.split(":")[1]
    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await callback_query.answer("Subscription not found.")
        return

    current_date = datetime.now(timezone.utc).timestamp()
    first_time_payment_date = transaction.first_time_payment
    time_since_first_payment = current_date - first_time_payment_date

    response = (
        f"**Subscription Info:**\n"
        f"Token: {transaction.short_id}\n"
        f"Next Invoice Date: {datetime.fromtimestamp(transaction.next_invoice_date, tz=timezone.utc).strftime('%Y-%m-%d')}\n"
        f"Amount: {transaction.amount} XTR\n")

    buttons = []
    if is_uuid7(transaction.transaction_id):
        pass
    else:
        if timedelta(seconds=time_since_first_payment) <= timedelta(days=3):
            refund_button = InlineKeyboardButton(
                "Refund", callback_data=f"refund_{transaction.short_id}")
            buttons.append([refund_button])

    if transaction.cancel_on_next_invoice == 1:
        cancel_cancel_button = InlineKeyboardButton(
            "Cancel Cancellation",
            callback_data=f"cancel_cancellation:{transaction.short_id}")
        buttons.append([cancel_cancel_button])
    else:
        cancel_button = InlineKeyboardButton(
            "Cancel Subscription",
            callback_data=f"cancel_subscription:{transaction.short_id}")
        buttons.append([cancel_button])

    back_button = InlineKeyboardButton("Back",
                                       callback_data="to_subscriptions")
    buttons.append([back_button])

    keyboard = InlineKeyboardMarkup(buttons)
    await callback_query.message.edit_text(response, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^cancel_subscription:(\S+)$"))
async def cancel_subscription_handler_callback(client, callback_query):
    short_id = callback_query.data.split(":")[1]
    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await callback_query.answer("Subscription not found.")
        return

    user_id = callback_query.from_user.id
    if transaction.user_id != user_id:
        await callback_query.answer(
            "You are not authorized to cancel this subscription.")
        return

    current_date = datetime.now(timezone.utc).timestamp()
    payment_date = transaction.payment_date
    time_since_payment = current_date - payment_date

    if timedelta(seconds=time_since_payment) > timedelta(days=3):
        await callback_query.answer(
            "You can only cancel the subscription within 3 days of payment.")
        return

    await mark_for_cancellation(transaction.transaction_id)
    await callback_query.message.edit_text(
        "Subscription marked for cancellation on the next invoice date.")

    await client.send_message(
        GROUP_ID, f"📭 <b>Subscription Cancellation Notification</b>: \n\n"
        f"• Action: Subscription Cancellation\n"
        f"• User ID: {user_id}\n"
        f"• Subscription Token: {short_id}\n"
        f"• Cancellation On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        reply_to_message_id=TOPIC_ID)


@Client.on_callback_query(filters.regex(r"^cancel_cancellation:(\S+)$"))
async def cancel_cancellation_handler_callback(client, callback_query):
    short_id = callback_query.data.split(":")[1]
    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await callback_query.answer("Subscription not found.")
        return

    user_id = callback_query.from_user.id
    if transaction.user_id != user_id:
        await callback_query.answer(
            "You are not authorized to cancel this subscription.")
        return

    await update_cancel_on_next_invoice(transaction.transaction_id, 0)
    await callback_query.message.edit_text(
        "Subscription cancellation has been cancelled.")


@Client.on_callback_query(filters.regex(r"^to_subscriptions$"))
async def back_to_subscriptions_handler(client, callback_query):
    user_id = callback_query.from_user.id
    subscriptions = await get_all_subscriptions()
    user_subscriptions = [
        sub for sub in subscriptions if sub.user_id == user_id
    ]

    if not user_subscriptions:
        await callback_query.message.edit_text(
            "You have no active subscriptions.")
        return

    keyboard = []
    for sub in user_subscriptions:
        button = InlineKeyboardButton(
            f"Token: {sub.short_id}",
            callback_data=f"subscription_info:{sub.short_id}")
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await callback_query.message.edit_text("Your active subscriptions:",
                                           reply_markup=reply_markup)


@Client.on_message(filters.command("refund_policy"))
async def refund_policy_handler(client, message):
    await message.reply_text(
        "Refund Policy: You can request a refund within 3 days of your payment. To request a refund, please contact support.",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("cancel_subscription"))
async def cancel_subscription_handler(client, message):
    try:
        _, short_id = message.text.split()
    except ValueError:
        await message.reply_text(
            "Usage: /cancel_subscription Token",
            reply_to_message_id=message.id,
        )
        return

    user_id = message.from_user.id
    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await message.reply_text(
            "Invalid Token.",
            reply_to_message_id=message.id,
        )
        return

    if transaction.user_id != user_id:
        await message.reply_text(
            "You are not authorized to cancel this subscription.",
            reply_to_message_id=message.id,
        )
        return

    next_invoice_date = transaction.next_invoice_date

    time_before_next_invoice = next_invoice_date - datetime.now(
        timezone.utc).timestamp()
    if timedelta(seconds=time_before_next_invoice) < timedelta(days=1):
        await message.reply_text(
            "You can only cancel the subscription up to 1 day before the next invoice date.",
            reply_to_message_id=message.id,
        )
        return

    await mark_for_cancellation(transaction.transaction_id)
    await message.reply_text(
        "Subscription marked for cancellation on the next invoice date.",
        reply_to_message_id=message.id,
    )

async def auto_send_invoices(client):
    await asyncio.sleep(10)

    while True:
        current_timestamp = datetime.now(timezone.utc).timestamp()
        subscriptions = await get_all_subscriptions()

        for sub in subscriptions:
            next_invoice_timestamp = sub.next_invoice_date

            if sub.cancel_on_next_invoice == 1:
                if next_invoice_timestamp <= current_timestamp:
                    await client.ban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=sub.user_id)
                    await asyncio.sleep(1)
                    await client.unban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=sub.user_id)
                    await delete_invite_link(user_id=sub.user_id)
                    await delete_transaction(sub.transaction_id)
                    await delete_affiliate_user(user_id=sub.user_id)

                    await client.send_message(
                        chat_id=sub.user_id,
                        text=f"Your subscription {sub.short_id} has been canceled."
                    )
                    
                    await client.send_message(
                        GROUP_ID,
                        f"🚫 <b>User Kicked from Premium Channel</b>: \n\n"
                        f"• User ID: {sub.user_id}\n"
                        f"• Reason: Subscription marked for cancellation."
                    )
                continue

            if next_invoice_timestamp <= current_timestamp + 86400 * 3:
               
                affiliate_discount = 0.0
                aff_settings = await get_affiliate_settings(affiliate_user=sub.user_id)
                if aff_settings and aff_settings.earnings and aff_settings.earnings > 0.0:
                    affiliate_discount = aff_settings.earnings

                await send_invoice(client, sub.user_id, sub.amount, sub.short_id, sub.plan_type, affiliate_discount)

                is_last_invoice = (next_invoice_timestamp <= current_timestamp + 86400)

                if is_last_invoice:
                    last_invoice_time = datetime.fromtimestamp(next_invoice_timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    await client.send_message(
                        sub.user_id,
                        f"⚠️ <b>Important:</b> This is your last invoice. "
                        f"If payment is not received by <b>{last_invoice_time} UTC</b>, "
                        f"you will be removed from the Premium Channel and will lose access to premium features."
                    )

                new_next_invoice_timestamp = next_invoice_timestamp + (sub.recurring_interval * 86400)

                await client.send_message(
                    GROUP_ID,
                    f"🔄 <b>Recurring Invoice Sent Notification</b>: \n\n"
                    f"• Action: Invoice Sent\n"
                    f"• User ID: {sub.user_id}\n"
                    f"• Subscription Token: {sub.short_id}\n"
                    f"• Amount Charged: {sub.amount} XTR\n"
                    f"• Next Invoice Date: {datetime.fromtimestamp(new_next_invoice_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')}\n"
                    f"• Invoice Sent On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                    reply_to_message_id=TOPIC_ID)

                sub.next_invoice_date = new_next_invoice_timestamp

            if next_invoice_timestamp < current_timestamp:
                await client.ban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=sub.user_id)
                await asyncio.sleep(1)
                await client.unban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=sub.user_id)
                await delete_invite_link(user_id=sub.user_id)
                await delete_transaction(sub.transaction_id)
                await delete_affiliate_user(user_id=sub.user_id)

                await client.send_message(
                    GROUP_ID,
                    f"🚫 <b>User Kicked from Premium Channel</b>: \n\n"
                    f"• User ID: {sub.user_id}\n"
                    f"• Reason: Invoice payment failed.",
                    reply_to_message_id=TOPIC_ID)

                await client.send_message(
                    sub.user_id,
                    f"You have been removed from the Premium Channel due to your inability to pay the invoice. You may purchase the subscription again if you want to join again."
                )

        await asyncio.sleep(86400)


@Client.on_message(filters.command("create_subscription"))
@sudo_users()
async def create_subscription_handler(client: Client, message: Message):
    try:
        user_id = int(message.text.split()[1])
    except (ValueError, IndexError):
        await message.reply_text(
            "Usage: /create_subscription <user_id>",
            reply_to_message_id=message.id,
        )
        return

    basic_button = InlineKeyboardButton(
        f"Basic - {BASIC_PLAN_PRICE} XTR ⭐️ (1 Month)",
        callback_data=f"create_subscription:basic:{user_id}")
    standard_button = InlineKeyboardButton(
        f"Standard - {STANDARD_PLAN_PRICE} XTR ⭐️ (3 Months)",
        callback_data=f"create_subscription:standard:{user_id}")
    premium_button = InlineKeyboardButton(
        f"Premium - {PREMIUM_PLAN_PRICE} XTR ⭐️ (6 Months)",
        callback_data=f"create_subscription:premium:{user_id}")
    keyboard = InlineKeyboardMarkup([[basic_button], [standard_button],
                                     [premium_button]])

    await message.reply_text(
        "Please select a subscription plan:",
        reply_markup=keyboard,
        reply_to_message_id=message.id,
    )


@Client.on_callback_query(
    filters.regex(r"^create_subscription:(basic|standard|premium):(\d+)$"))
async def handle_create_subscription_plan_selection(
        client: Client, callback_query: CallbackQuery):
    plan_type, user_id = callback_query.data.split(":")[1:]
    user_id = int(user_id)

    if plan_type == "basic":
        title = "Basic Subscription - 1 Month"
        price = BASIC_PLAN_PRICE
        plan_token = "basic"
    elif plan_type == "standard":
        title = "Standard Subscription - 3 Months"
        price = STANDARD_PLAN_PRICE
        plan_token = "standard"
    elif plan_type == "premium":
        title = "Premium Subscription - 6 Months"
        price = PREMIUM_PLAN_PRICE
        plan_token = "premium"

    short_id = str(uuid7())
    transaction_id = str(uuid7())
    payment_date = datetime.now(timezone.utc)
    next_invoice_date = payment_date + timedelta(days=BASIC_PLAN_DAYS)

    await save_transaction(transaction_id, short_id, user_id, price,
                           payment_date.timestamp(),
                           next_invoice_date.timestamp(), plan_token)

    await client.send_message(
        GROUP_ID, f"🆕 <b>New Subscription Notification</b>: \n\n"
        f"• Action: New Subscription Created\n"
        f"• User ID: {user_id}\n"
        f"• Plan Type: {plan_token.capitalize()}\n"
        f"• Subscription Token: {short_id}\n"
        f"• Created On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        reply_to_message_id=TOPIC_ID)

    confirmation_message = f"Subscription {title} created successfully for user {user_id}."

    await callback_query.message.edit_text(confirmation_message,
                                           reply_markup=None)

    try:
        await client.send_message(
            user_id, f"Thank you for subscribing!\n")
    except PeerIdInvalid:
        chat_id = callback_query.message.chat.id
        message_thread_id = callback_query.message.message_thread_id
        await client.send_message(chat_id,
                                  f"Failed to send message to user {user_id}.",
                                  message_thread_id=message_thread_id)


@Client.on_message(filters.command("cancel"))
@sudo_users()
async def cancel_subscription_manual(client: Client, message: Message):
    try:
        _, short_id = message.text.split()
    except ValueError:
        await message.reply_text(
            "Usage: /cancel token_id",
            reply_to_message_id=message.id,
        )
        return

    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await message.reply_text(
            "Invalid Token.",
            reply_to_message_id=message.id,
        )
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Cancel Immediately",
                             callback_data=f"cancel_immediate_{short_id}"),
        InlineKeyboardButton("Mark for Cancellation",
                             callback_data=f"mark_cancellation_{short_id}"),
    ]])

    await message.reply_text(
        "Choose an option:",
        reply_markup=keyboard,
        reply_to_message_id=message.id,
    )


@Client.on_callback_query(
    filters.regex(r"cancel_immediate_|mark_cancellation_"))
async def handle_cancel_choice(client: Client, callback_query):
    data = callback_query.data
    short_id = data.split("_")[-1]

    transaction = await get_transaction_by_short_id(short_id)

    if not transaction:
        await callback_query.answer("Invalid Token.")
        return

    user_id = transaction.user_id

    if data.startswith("cancel_immediate_"):
        await delete_transaction(transaction.transaction_id)
        await delete_affiliate_user(user_id)

    invite_link_entry = await get_invite_link(user_id)

    if invite_link_entry:
        await client.ban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=user_id)
        await asyncio.sleep(1)
        await client.unban_chat_member(chat_id=PREMIUM_CHANNEL, user_id=user_id)

        await client.revoke_chat_invite_link(
            chat_id=PREMIUM_CHANNEL,
            invite_link=invite_link_entry.invite_link
        )

        await delete_invite_link(user_id)
        
        await callback_query.answer("Subscription cancelled immediately.")
    else:
        await mark_for_cancellation(transaction.transaction_id)
        await callback_query.answer("Subscription marked for cancellation.")

    await callback_query.message.edit_text("Action completed successfully!")


@Client.on_message(filters.command("extend"))
@sudo_users()
async def extend_subscription_handler(client: Client, message: Message):
    try:
        _, short_id, months_str = message.text.split()
        months = int(months_str)
    except (ValueError, IndexError):
        await message.reply_text(
            "Usage: /extend Token number_of_months",
            reply_to_message_id=message.id,
        )
        return

    transaction = await get_transaction_by_short_id(short_id)
    if not transaction:
        await message.reply_text(
            "Invalid Token.",
            reply_to_message_id=message.id,
        )
        return

    user_id = message.from_user.id
    if transaction.user_id != user_id:
        await message.reply_text(
            "You are not authorized to extend this subscription.",
            reply_to_message_id=message.id,
        )
        return

    new_next_invoice_date = datetime.fromtimestamp(
        transaction.next_invoice_date,
        tz=timezone.utc) + timedelta(days=BASIC_PLAN_DAYS * months)

    await update_next_invoice_date(transaction.transaction_id,
                                   new_next_invoice_date.timestamp())

    await message.reply_text(
        f"Subscription has been successfully extended by {months} month(s).",
        reply_to_message_id=message.id,
    )

    await client.send_message(
        GROUP_ID, f"⏳ <b>Subscription Extension Notification</b>: \n\n"
        f"• Action: Subscription Extended\n"
        f"• User ID: {user_id}\n"
        f"• Subscription Token: {short_id}\n"
        f"• Extended By: {months} month(s)\n"
        f"• New Next Invoice Date: {new_next_invoice_date.strftime('%Y-%m-%d')}\n"
        f"• Extension Processed On: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        reply_to_message_id=TOPIC_ID)


@Client.on_message(filters.command("income"))
@sudo_users()
async def stats_handler(client: Client, message: Message):
    subscriptions = await get_all_subscriptions()

    total_users = len(subscriptions)
    basic_users = sum(1 for sub in subscriptions if sub.plan_type == "basic")
    standard_users = sum(1 for sub in subscriptions if sub.plan_type == "standard")
    premium_users = sum(1 for sub in subscriptions if sub.plan_type == "premium")

    total_monthly_income = 0

    for sub in subscriptions:
        if sub.plan_type == "basic":
            total_monthly_income += sub.amount / (BASIC_PLAN_DAYS / 30.0)
        elif sub.plan_type == "standard":
            total_monthly_income += sub.amount / (STANDARD_PLAN_DAYS / 30.0)
        elif sub.plan_type == "premium":
            total_monthly_income += sub.amount / (PREMIUM_PLAN_DAYS / 30.0)

    response = (
        f"**Statistics:**\n"
        f"Total Paying Users: {total_users}\n"
        f" - Basic Plan Users: {basic_users}\n"
        f" - Standard Plan Users: {standard_users}\n"
        f" - Premium Plan Users: {premium_users}\n"
        f"**Monthly Income:** {round(total_monthly_income, 2)} XTR"
    )

    await message.reply_text(
        response,
        reply_to_message_id=message.id,
    )

@Client.on_message(filters.command("donate") & filters.private)
async def donate_handler(client: Client, message: Message):
    try:
        _, amount_str = message.text.split()
        amount = int(amount_str)
    except (ValueError, IndexError):
        await message.reply_text(
            "Usage: /donate amount",
            reply_to_message_id=message.id,
        )
        return

    title = "Donation"
    description = "Thank you for your generosity!"
    prices = [types.LabeledPrice(label=title, amount=amount)]

    payload = f"donation_{amount}"
    await client.send_invoice(chat_id=message.from_user.id,
                              title=title,
                              description=description,
                              payload=payload,
                              currency="XTR",
                              prices=prices,
                              start_parameter="donate")