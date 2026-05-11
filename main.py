import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from playwright.async_api import async_playwright

# Setup Logging to see errors in Railway
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 1. Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Zealy Sniper is online! Send /claim to test.")

# 2. Test Claim (To check if Playwright works)
async def test_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Testing browser...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://zealy.io")
            title = await page.title()
            await update.message.reply_text(f"🌐 Success! Reached Zealy. Page title: {title}")
            await browser.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Browser Error: {str(e)}")
    # This helps Railway know the bot is alive
    port = int(os.environ.get("PORT", 8443))

if __name__ == '__main__':
    # Grab the token from Railway Variables
    TOKEN = os.getenv('TOKEN')
    
    if not TOKEN:
        print("❌ ERROR: No TOKEN found in Railway Variables!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("claim", test_claim))
        
        print("🚀 Bot is starting...")
        app.run_polling()
