# XyroSubscriptionBot

**XyroSubscriptionBot** is a powerful Telegram bot designed to manage subscriptions, affiliate programs, and payments. Users can subscribe to various plans, manage their subscriptions, earn affiliate commissions, and receive discounts. The bot includes advanced administrative features for managing user access and settings.

## Key Features

- **Subscription Management**: Users can subscribe to different plans (Basic, Standard, Premium) and manage their active subscriptions.
- **Affiliate Program**: Users earn commissions by referring others, with instant notifications for earned commissions.
- **Discount Management**: Admins can create, activate, and deactivate discount codes, allowing users to benefit from discounts based on specific conditions.
- **Administrative Tools**: Admin commands for user management and configuration.
- **User Support**: Built-in commands for user assistance.

## Requirements

- **Python**: Version 3.10 or higher.
- **Dependencies**: Required packages specified in `pyproject.toml`.

---

## Setup Instructions

### Step 1: Clone the Repository

Clone this repository to your local machine:
```bash
git clone <repository-url>
cd XyroSubscriptionBot
```

### Step 2: Set Up Environment

- **For Nix users**: Install the project using:
  ```bash
  nix profile install .
  ```

- **For non-Nix users**: Use Poetry to install dependencies:
  ```bash
  poetry install
  ```

### Step 3: Configuration

Create a `config.yml` file in the root directory based on the following template, filling in the respective values:

```yaml
telegram:
  api_id: <your_api_id>                     # Your Telegram API ID
  api_hash: <your_api_hash>                 # Your Telegram API Hash
  group_id: <your_group_id>                 # The ID of your Telegram group
  topic_id: <your_topic_id>                 # The topic ID for group discussions (if applicable)
  bot_token: <your_bot_token>               # Your Telegram bot token
  owner_id: <your_owner_id>                 # Your Telegram user ID
  sudo_users:                               # List of user IDs with admin privileges
    - <user_id_1>
    - <user_id_2>
  support_bot: <support_bot_username>       # Username of the support bot
  announce_channel: <announce_channel_id>   # Channel ID for announcements
  drop_updates: true                        # Enable or disable dropping updates
  premium_channel_id: <premium_channel_id>  # ID for premium users’ channel

database:
  schema: <your_database_schema>            # Your database schema

misc:
  disable:                                  # List of plugins to disable
    - <plugin_name>

pricing:
  basic_plan_price: <basic_plan_price>      # Price for Basic plan
  basic_plan_days: <number_of_days>         # Duration of Basic plan in days
  standard_plan_price: <standard_plan_price> # Price for Standard plan
  standard_plan_days: <number_of_days>      # Duration of Standard plan in days
  premium_plan_price: <premium_plan_price>  # Price for Premium plan
  premium_plan_days: <number_of_days>       # Duration of Premium plan in days

affiliate:
  minimum_commission_withdraw: <min_withdraw_amount> # Minimum commission amount for withdrawal
  affiliate_allowed: true                  # Enable or disable the affiliate program
  withdrawal_allowed: true                 # Allow users to withdraw their earnings
```

### Step 4: Running the Bot

Once the configuration is complete, start the bot:
```bash
poetry run XyroSub
```

or if using Nix:
```bash
XyroSub
```
---

## Usage

### Available Commands

- `/start` - Start the bot and get a welcome message.
- `/help` - Get help information and available commands.
- `/premium` - Display subscription options.
- `/my_subscriptions` - List all active subscriptions for the user.
- `/cancel_subscription <Token>` - Cancel a specified subscription.
- `/affiliate` - Information about the affiliate program.
- `/commission` - Display the user's affiliate earnings and status.
- `/withdraw <TON/USDT_Address> <Withdrawal_Type>` - Withdraw affiliate commissions.

### Administrative Commands

- `/ban <user_id>` - Ban a user from using the bot.
- `/unban <user_id>` - Unban a previously banned user.
- `/create_discount <discount_value>` - Create a discount.
- `/list_discounts` - List all active discounts.

---

## Affiliate Program

Users can earn commissions by referring others via unique links tracked by the bot, with settings allowing for easy management of earnings.

---

## Payments and Invoices

The bot handles payment processing, generates invoices for subscriptions, and manages refund requests through the interface.

---