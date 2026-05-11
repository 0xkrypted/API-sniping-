from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is online 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.run_polling()
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# 1. This is how you write functions now (must have 'async' and 'await')
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Zealy Sniper Bot is active! Use /set_proof to add links."
    )

if __name__ == '__main__':
    # 2. This is the new way to build the bot
    application = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()
    
    # 3. Add your commands
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    # 4. Start the bot
    application.run_polling()
