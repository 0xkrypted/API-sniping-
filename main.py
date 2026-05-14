import asyncio
import json
import os
from datetime import datetime, time
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIGURATION ---
# The bot saves data here so it doesn't get lost when the server restarts
VAULT_FILE = "vault.json"

def load_vault():
    if os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "r") as f:
            return json.load(f)
    return {"token": "", "tasks": []}

def save_vault(data):
    with open(VAULT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- ZEALY SNIPER LOGIC ---
async def fire_sniper():
    vault = load_vault()
    if not vault["token"] or not vault["tasks"]:
        print("❌ Sniper aborted: No token or tasks found in vault.")
        return

    headers = {
        "Authorization": f"Bearer {vault['token']}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for task in vault["tasks"]:
            project = task["project"]
            quest_id = task["quest_id"]
            proof = task["proof"]
            
            url = f"https://api.zealy.io/communities/{project}/quests/{quest_id}/claim"
            payload = {"proof": proof}

            # RETRY LOOP: Tries 3 times if there is a network error
            for attempt in range(3):
                try:
                    print(f"🚀 [Attempt {attempt+1}] Sniping {project}...")
                    response = await client.post(url, headers=headers, json=payload)
                    print(f"🎯 {project} Status: {response.status_code}")
                    
                    if response.status_code == 200 or response.status_code == 400:
                        break # Success or already claimed, stop retrying
                except Exception as e:
                    print(f"⚠️ Connection error on attempt {attempt+1}: {e}")
                    await asyncio.sleep(2) # Wait 2 seconds before trying again

# --- BACKGROUND SCHEDULER ---
async def run_scheduler():
    print("⏰ Scheduler active. Monitoring for 12 AM UTC...")
    while True:
        now = datetime.utcnow().time()
        # Checks if it is exactly 12:00 AM UTC (1:00 AM Nigeria)
        if now.hour == 0 and now.minute == 0 and now.second == 0:
            print("🚨 12 AM UTC Detected! Firing Sniper...")
            await fire_sniper()
            await asyncio.sleep(60) # Don't fire twice in the same minute
        
        # Heartbeat: Keeps the server from idling
        await asyncio.sleep(1)

# --- TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Jeff's Sniper Bot is online. Use /token and /load to set up.")

async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = " ".join(context.args)
    if not token:
        await update.message.reply_text("❌ Usage: /token [your_ey_code]")
        return
    vault = load_vault()
    vault["token"] = token
    save_vault(vault)
    await update.message.reply_text("✅ Token saved to vault.")

async def load_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: /load [project] [quest_id] [proof]")
        return
    
    project, quest_id, proof = context.args[0], context.args[1], context.args[2]
    vault = load_vault()
    vault["tasks"].append({"project": project, "quest_id": quest_id, "proof": proof})
    save_vault(vault)
    await update.message.reply_text(f"📥 Task for {project} added to Vault.")

async def manual_fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔫 Manual trigger pulled. Sniping now...")
    await fire_sniper()
    await update.message.reply_text("🏁 Manual check complete. Check Railway logs for status.")

# --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    # Get your Token from Railway Environment Variables
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("token", set_token))
    app.add_handler(CommandHandler("load", load_task))
    app.add_handler(CommandHandler("fire", manual_fire))

    print("⚡ Bot starting...")
    
    # Start the 1 AM scheduler in the background
    loop = asyncio.get_event_loop()
    loop.create_task(run_scheduler())
    
    app.run_polling()
