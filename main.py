import os
import asyncio
import httpx
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- THE VAULT (Local Storage) ---
VAULT_FILE = "vault.json"

def load_vault():
    if os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "r") as f: return json.load(f)
    return {"token": "", "tasks": []}

def save_vault(data):
    with open(VAULT_FILE, "w") as f: json.dump(data, f)

# --- THE SNIPER ENGINE ---
async def fire_sniper():
    vault = load_vault()
    if not vault["token"]: return "❌ No token set! Use /token"
    
    results = []
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {vault['token']}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        for task in vault["tasks"]:
            url = f"https://api.zealy.io/communities/{task['project']}/quests/{task['id']}/claim"
            payload = {"submission": task['proof']}
            
            try:
                # Direct API hit - bypasses all buttons/wait times
                resp = await client.post(url, json=payload, headers=headers)
                results.append(f"🎯 {task['project']}: {resp.status_code}")
            except Exception as e:
                results.append(f"⚠️ {task['project']} Error: {str(e)}")
    
    return "\n".join(results)

# --- TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **Zealy Sniper v1.0 Online**\n\n1. `/token [paste]`\n2. `/load [project] [id] [proof]`\n3. `/fire` (to test now)", parse_mode="Markdown")

async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vault = load_vault()
    vault["token"] = context.args[0]
    save_vault(vault)
    await update.message.reply_text("✅ Token Saved. Identity Verified.")

async def load_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Use: `/load project quest_id proof`")
        return
    
    vault = load_vault()
    vault["tasks"].append({
        "project": context.args[0],
        "id": context.args[1],
        "proof": context.args[2]
    })
    save_vault(vault)
    await update.message.reply_text(f"📝 Task added to Vault for 1 AM reset.")

async def manual_fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔫 Sniping now...")
    res = await fire_sniper()
    await msg.edit_text(res)

# --- THE 1 AM SCHEDULER ---
async def scheduler_loop(app):
    while True:
        now = datetime.utcnow()
        # Trigger at exactly 12:00:01 AM UTC (1:00:01 AM Nigeria)
        if now.hour == 0 and now.minute == 0 and now.second == 1:
            print("⏰ 12 AM UTC Detected! Firing Sniper...")
            await fire_sniper()
            await asyncio.sleep(60) # Don't fire twice
        await asyncio.sleep(1)

# --- MAIN RUNNER ---
async def main():
    token = os.getenv("TOKEN")
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("token", set_token))
    application.add_handler(CommandHandler("load", load_task))
    application.add_handler(CommandHandler("fire", manual_fire))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    await scheduler_loop(application)

if __name__ == "__main__":
    asyncio.run(main())
