from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message

from XyroSub import (AFFILIATE_ALLOWED, GROUP_ID, MINIMUM_COMMISSION_WITHDRAW,
                     TOPIC_ID, WITHDRAWAL_ALLOWED)
from XyroSub.database.affiliate import (fetch_affiliate_settings_by_code,
                                        get_affiliate_settings,
                                        get_commission_info, modify_earnings,
                                        set_affiliate_settings)
from XyroSub.helpers.decorators import sudo_users
from XyroSub.helpers.misc import get_bot_object
from XyroSub.helpers.string_utils import generate_secure_random_characters

__module_name__ = ["affiliate", "commission"]
__help_msg__ = """
💸 **Become an Affiliate and Earn with Us!** 💸

Our Affiliate Program makes it easy to earn commissions by referring new customers. Here\'s how it works:

**🔗 How You Earn:**  
- Earn **10-15%% of the purchase amount** each month, for up to 12-18 months, or for as long as the customer keeps paying—whichever comes first.  
- For top-performing affiliates with multiple referrals, this payout can extend even longer, matching your customers\' ongoing subscriptions!  

**💰 Your Earnings:**  
- If you have an active subscription, your subscription price will automatically reduce by the amount you\'ve earned in affiliate commissions.  
- If you don\'t have an active subscription, or if your earnings exceed your subscription price, we\'ll pay you out via **TON** or **USDT** after 21 days (in line with Telegram\'s Stars Terms), provided the total is above the minimum payout threshold.

**🔗 How to Get Started:**  
- Use our affiliate link system—each referral is tracked via a unique deep-link URL provided by our bot.  
- When someone joins through your link, you\'re automatically tagged as their referrer. If they\'ve been referred more than once, the **latest affiliate** gets the credit.

**💬 Affiliate Updates:**  
- Affiliates are instantly alerted each time a new subscription is purchased through their referral link.  
- In the case of a refund, you\'ll also receive a notification.  
- While cancellation alerts won\'t be sent, you can always check your **earnings** and **active clients** with a dedicated command.

**🔒 Redemption & Payouts:**  
- Commissions are manually approved, with no cap on earnings!  
- Earnings are rounded up to the nearest whole number upon redemption, ensuring you get every bit you\'ve earned.

Ready to start earning?
Tap on /affiliate
Share your affiliate link, track your success, and watch your rewards grow! 🚀
"""


@Client.on_message(filters.command('affiliate') & filters.private)
async def handle_affiliate_command(client: Client, message: Message) -> None:
    if not AFFILIATE_ALLOWED:
        await message.reply_text("The affiliate program is currently disabled. Please check back later.")
        return
    
    affiliate_message = """
👋 **Hey, {0}!**

Thinking about sharing our bot, **{1}**, and earning some extra cash along the way? It\'s easy! Just share your unique link: **{2}** 📲

When someone clicks your link and makes a qualifying subscription purchase, you\'ll get an instant alert and a **commission** on their purchase. Exciting, right? 🎉

But that\'s not all! The more customers you refer, the more your commission grows, thanks to our **tiered affiliate levels**. So your earnings can keep building as your referrals add up. 📈

Here\'s how it works:  
- Once your commission reaches a minimum of **{3} XTR**, you can withdraw it, or even put it towards your own subscription!  
- If you do decide to subscribe, you\'ll see your commission automatically reduce the subscription price—keeping more in your pocket. 💸

Want to check on your commissions or see your active clients? Just use **`/commission`** at any time to stay updated on your progress.

Ready to get started? Share your link and let the rewards roll in! 🚀
"""
    user_id = message.from_user.id
    user_first_name = message.from_user.first_name or 'NoFirstName'
    bot_user = await get_bot_object(client=client)
    aff_settings = await get_affiliate_settings(affiliate_user=user_id)

    if not aff_settings:
        affiliate_generated_code = generate_secure_random_characters(ctr=6)

        while True:
            aff_set = await fetch_affiliate_settings_by_code(
                affiliate_code=affiliate_generated_code)
            if aff_set:
                affiliate_generated_code = generate_secure_random_characters(
                    ctr=6)
            else:
                break
    else:
        affiliate_generated_code = aff_settings.affiliate_code

    affiliate_link = f'https://t.me/{bot_user.username}?start={affiliate_generated_code}'
    await set_affiliate_settings(affiliate_user=user_id,
                                 affiliate_code=affiliate_generated_code,
                                 earnings=0.0)
    await message.reply_text(
        affiliate_message.format(
            user_first_name,
            bot_user.full_name,
            affiliate_link,
            MINIMUM_COMMISSION_WITHDRAW,
        ),
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("commission") & filters.private)
async def handle_commission_command(_: Client, message: Message) -> None:
    user_id = message.from_user.id
    user_first_name = message.from_user.first_name or 'NoFirstName'
    earnings, referred_user, total_users = await get_commission_info(
        affiliate_user=user_id)
    if (not earnings and not referred_user
            and not total_users) or (earnings == 0.0 and referred_user == 0
                                     and total_users == 0):
        await message.reply_text(
            "You do not have any active referred users currently.\n\
Please refer some user with: <code>/affiliate</code> and when they have made a qualifying subscription purchase, you will receive a **commission** on their purchase.\n\n\
<i>Note:</i> An active referral is a referral who has one or more subscriptions.",
            reply_to_message_id=message.id,
        )
        return
    await message.reply_text(
        f"Hi, <b>{user_first_name}</b>!\n\
Your (<code>{user_id}</code>) commission is as follows:\n\
<b>Active Referrals:</b> {referred_user}\n\
<b>Total Referrals:</b> {total_users}\n\
<b>Earnings:</b> {earnings} XTR\n\n\
<i>Note: An active referral is a referral who has one or more subscriptions.</i>",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("commission") & filters.group)
@sudo_users()
async def handle_sudo_commission_command(_: Client, message: Message) -> None:
    user_first_name = message.from_user.first_name or 'NoFirstName'
    if len(message.command) != 2:
        await message.reply_text(
            "Usage: <code>/commission user_id</code>",
            reply_to_message_id=message.id,
        )
        return
    try:
        user_id = message.command[1]
        user_id = int(user_id)
    except ValueError:
        await message.reply_text(
            f"<code>{user_id}</code> is not a valid User ID",
            reply_to_message_id=message.id,
        )
        return
    earnings, referred_user, total_users = await get_commission_info(
        affiliate_user=user_id)
    await message.reply_text(
        f"Hi, <b>{user_first_name}</b>!\n\
The commission info for <code>{user_id}</code> is as follows:\n\
<b>Active Referrals:</b> {referred_user}\n\
<b>Total Referrals:</b> {total_users}\n\
<b>Earnings:</b> {earnings} XTR\n\n\
<i>Note: An active referral is a referral who has one or more subscriptions.</i>",
        reply_to_message_id=message.id,
    )


@Client.on_message(filters.command("withdraw") & filters.private)
async def handle_withdraw_command(client: Client, message: Message) -> None:
    if not WITHDRAWAL_ALLOWED:
        await message.reply_text("The withdrawal program is currently disabled. You can use commissions against invoices.")
        return
    
    user_first_name = message.from_user.first_name or 'NoFirstName'
    user_id = message.from_user.id
    if len(message.command) < 3:
        await message.reply_text(
            text=f"Hey, <b>{user_first_name}</b>\n\
Do you want to withdraw your hard-earned affiliate commission?\n\
Look no further.\n\
Just send a withdraw command with: <code>/withdraw TON/USDT(TRC20)_Address Withdrawal_Type</code>\n\
We will verify the request and send the payment to your provided wallet address appropriately.\n\n\
<i>Note: You are responsible for providing the correct withdrawal address and the correct withdrawal token type (TON/USDT)</i>\n\
<i>Standard fees by the blockchain will be deducted from the withdrawal amount</i>",
            reply_to_message_id=message.id,
        )
        return
    _, wallet_addr, wallet_type = message.command
    if wallet_type.lower() not in ['ton', 'usdt']:
        await message.reply_text(
            text=
            "The Withdrawal_Type <b>must be</b> <code>TON</code> or <code>USDT</code>",
            reply_to_message_id=message.id,
        )
        return
    aff_settings = await get_affiliate_settings(affiliate_user=user_id)
    if aff_settings.earnings < MINIMUM_COMMISSION_WITHDRAW:
        await message.reply_text(
            text=
            f"You need to have a minimum of {MINIMUM_COMMISSION_WITHDRAW} XTR to withdraw",
            reply_to_message_id=message.id,
        )
        return

    await client.send_message(
        chat_id=GROUP_ID,
        text=
        f"A user: <code>{user_id}</code> has requested a withdrawal of {aff_settings.earnings} XTR.\n\
Wallet Address: <code>{wallet_addr}</code>\n\
Wallet Type: <code>{wallet_type}</code>\n\n\
You can accept the withdrawal with: <code>/accept_withdraw user_id message</code>, or reject it with: <code>/reject_withdraw user_id message</code>",
        message_thread_id=TOPIC_ID,
    )
    await message.reply_text(
        text="A withdrawal request was sent to the administrative team.\n\
Once they verify and process, or reject the withdrawal, you will be alerted about it.",
        reply_to_message_id=message.id,
    )


@Client.on_message(
    filters.command(["accept_withdraw", "reject_withdraw"]) & filters.group)
@sudo_users()
async def handle_sudo_withdrawal_command(client: Client,
                                         message: Message) -> None:
    if len(message.command) < 3:
        await message.reply_text(
            text=f'Usage: <code>/{message.command[0]} user_id message</code>',
            reply_to_message_id=message.id,
        )
        return
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text(
            text=f'The User ID: {user_id} is not a valid User ID',
            reply_to_message_id=message.id,
        )
        return
    withdraw_message = message.text.split(sep=None, maxsplit=2)[2]
    actual_command = message.command[0]
    aff_settings = await get_affiliate_settings(affiliate_user=user_id)

    if actual_command == 'accept_withdraw':
        if aff_settings.earnings < MINIMUM_COMMISSION_WITHDRAW:
            await client.send_message(
                chat_id=user_id,
                text=
                f'Withdrawal rejected since your affiliate commission: {aff_settings.earnings} is less than the minimum withdrawal amount'
            )
        else:
            await modify_earnings(
                affiliate_user=user_id,
                earnings=-aff_settings.earnings,
            )
            await client.send_message(
                chat_id=user_id,
                text=
                f'A withdrawal of {round(aff_settings.earnings)} was successfully processed.\n\
Message from administrators: {withdraw_message}\n\n\
<i>Please be on the lookout for the payment to reflect in your wallet.</i>')
            
            await client.send_message(
                chat_id=GROUP_ID,
                text=f'A withdrawal of {round(aff_settings.earnings)} XTR has been accepted for user <code>{user_id}</code>.'
            )

    elif actual_command == 'reject_withdraw':
        await client.send_message(
            chat_id=user_id,
            text=f'Your withdrawal of {aff_settings.earnings} was rejected.\n\
Message from administrators: {withdraw_message}')
