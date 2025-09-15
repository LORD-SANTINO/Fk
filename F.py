from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States for conversation (withdrawal amount input)
WAITING_WITHDRAW_AMOUNT = 1

# Simulated database (replace with real database in production)
users_db = {}
withdrawal_requests = []

# Configuration - replace these
BOT_TOKEN = "7966261094:AAHRnnFOI4YlwNTjREqI5uOGZMs5iWXaQxY"
ADMIN_ID = 7243305432                 # Your Telegram user ID as admin
ADMIN_GROUP_ID = -1002371819861       # Telegram group ID for withdrawal requests
CHANNEL_USERNAME = "@dax_channel01"   # Channel user name that users must join

# Helper functions

def get_user_balance(user_id):
    return users_db.get(user_id, {}).get('balance', 0)

def save_withdrawal_request(user_id, amount):
    withdrawal_requests.append({'user_id': user_id, 'amount': amount, 'status': 'Pending'})

def get_all_users():
    return users_db.keys()

async def check_channel_membership(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # Status can be "member", "creator", or "administrator" for joined users
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logger.warning(f"Error checking membership for user {user_id}: {e}")
        return False

# Bot Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    bot = context.bot

    if not await check_channel_membership(bot, user_id):
        await update.message.reply_text(
            f"Please join our channel {CHANNEL_USERNAME} to use this bot.\n"
            "After joining, send /start again."
        )
        return

    if user_id not in users_db:
        users_db[user_id] = {'balance': 100}  # Starting balance example
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Referral Link", callback_data='referral')],
        [InlineKeyboardButton("Balance", callback_data='balance')],
        [InlineKeyboardButton("Leaderboard", callback_data='leaderboard')],
        [InlineKeyboardButton("Withdraw", callback_data='withdraw')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please choose an option:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == 'referral':
        referral_link = f"t.me/your_bot?start={user_id}"
        await query.edit_message_text(text=f"Your referral link: {referral_link}")

    elif data == 'balance':
        balance = get_user_balance(user_id)
        await query.edit_message_text(text=f"Your balance: {balance}")

    elif data == 'leaderboard':
        leaderboard_text = "Top referrers:\nUser 111: 20 refs\nUser 222: 15 refs"  # Example placeholder
        await query.edit_message_text(text=leaderboard_text)

    elif data == 'withdraw':
        await query.edit_message_text(text="Please send the withdrawal amount:")
        return WAITING_WITHDRAW_AMOUNT

async def withdrawal_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid amount. Please send a number.")
        return WAITING_WITHDRAW_AMOUNT

    balance = get_user_balance(user_id)
    if amount > balance:
        await update.message.reply_text("Insufficient balance for withdrawal.")
        return ConversationHandler.END
    
    save_withdrawal_request(user_id, amount)
    await update.message.reply_text("Withdrawal request sent to admin group. Waiting for approval.")
    await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"New withdrawal request from user {user_id} for amount {amount}."
    )
    return ConversationHandler.END

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text('You are not authorized to use this command.')
        return
    message = ' '.join(context.args)
    for uid in get_all_users():
        try:
            await context.bot.send_message(chat_id=uid, text=message)
        except Exception as e:
            logger.warning(f"Failed to send message to {uid}: {e}")
    await update.message.reply_text('Broadcast completed.')

async def owner_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text('You are not authorized to access the owner menu.')
        return
    keyboard = [
        [InlineKeyboardButton("Broadcast Message", callback_data='broadcast')],
        [InlineKeyboardButton("View Withdrawal Requests", callback_data='view_withdrawals')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Owner menu:', reply_markup=reply_markup)

async def owner_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text(text="Unauthorized.")
        return
    data = query.data

    if data == 'broadcast':
        await query.edit_message_text(text="Send the broadcast message using /broadcast command.")
    elif data == 'view_withdrawals':
        msg = "Pending withdrawal requests:\n"
        for req in withdrawal_requests:
            if req['status'] == 'Pending':
                msg += f"User {req['user_id']} - Amount: {req['amount']}\n"
        await query.edit_message_text(text=msg or "No pending withdrawal requests.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

def main():
    # Create Application instead of Updater
    application = Application.builder().token(BOT_TOKEN).build()

    # Create conversation handler for withdrawal
    conv_handler_withdraw = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^withdraw$')],
        states={
            WAITING_WITHDRAW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_amount_handler)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', show_main_menu))
    application.add_handler(CommandHandler('owner', owner_menu))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^(referral|balance|leaderboard)$'))
    application.add_handler(CallbackQueryHandler(owner_button_handler, pattern='^(broadcast|view_withdrawals)$'))
    application.add_handler(conv_handler_withdraw)

    # Start polling
    application.run_polling()

if __name__ == '__main__':
    main()
