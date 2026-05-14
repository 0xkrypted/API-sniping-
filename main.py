import asyncio
import json
import os
from datetime import datetime
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIGURATION ---
VAULT_FILE = "vault.json"

def load_vault():
    if os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {"token": "", "tasks": []}
    return {"token": "", "tasks": []}

def save_vault(data):
    with open(VAULT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- ZEALY SNIPER LOGIC ---
async def fire_sniper(update: Update = None):
    vault = load_vault()
    if not vault["token"] or not vault["tasks"]:
        msg = "❌ Sniper aborted: No token or tasks found in vault."
        print(msg)
        if update:
            await update.message.reply_text(msg)
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

            for attempt in range(3):
                try:
                    print(f"🚀 [Attempt {attempt+1}] Sniping {project}...")
                    response = await client.post(url, headers=headers, json=payload)
                    status = response.status_code
                    print(f"🎯 {project} Status: {status}")
                    
                    if update:
                        await update.message.reply_text(f"📡 {project} Result: Status {status}")

                    if status == 200 or status == 400:
                        break 
                except Exception as e:
                    print(f"⚠️ Connection error on attempt {attempt+1}: {e}")
                    await asyncio.sleep(2)

# --- BACKGROUND SCHEDULER ---
async def run_scheduler():
    print("⏰ Scheduler active. Monitoring for 12 AM UTC...")
    while True:
        now = datetime.utcnow().time()
        # 12:00 AM UTC is 1:00 AM Nigeria Time
        if now.hour == 0 and now.minute == 0 and now.second == 0:
            print("🚨 12 AM UTC Detected! Firing Sniper...")
            await fire_sniper()
            await asyncio.sleep(60) 
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
    try:
        # We pass 'update' here so the function can talk back to you
        await fire_sniper(update)
        await update.message.reply_text("🏁 Manual check complete.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Crash Error: {e}")

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /remove [project_name]")
        return
    
    target_project = context.args[0]
    vault = load_vault()
    
    # Filter the list: Keep everything EXCEPT the project we want to delete
    original_count = len(vault["tasks"])
    vault["tasks"] = [t for t in vault["tasks"] if t["project"] != target_project]
    
    if len(vault["tasks"]) < original_count:
        save_vault(vault)
        await update.message.reply_text(f"🗑️ Removed {target_project} from the sniper list.")
    else:
        await update.message.reply_text(f"❓ Could not find project: {target_project}")

# --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable not found!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Existing Handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("token", set_token))
        app.add_handler(CommandHandler("load", load_task))
        app.add_handler(CommandHandler("fire", manual_fire))

        # --- NEW HANDLERS START HERE ---
        app.add_handler(CommandHandler("remove", remove_task))
        app.add_handler(CommandHandler("list", list_tasks))
        # --- NEW HANDLERS END HERE ---

        print("⚡ Bot starting...")
        
        loop = asyncio.get_event_loop()
        loop.create_task(run_scheduler())
        
        app.run_polling()
