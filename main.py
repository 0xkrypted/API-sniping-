import asyncio
import json
import os
from datetime import datetime
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIGURATION ---
VAULT_FILE = "vault.json"

# --- PROXY CONFIGURATION ---
PROXY_URL = "http://lecopvxg:pku368jcdirl@38.154.203.95:5863"

def load_vault():
    if os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {"cookie": "", "tasks": []}
    return {"cookie": "", "tasks": []}

def save_vault(data):
    with open(VAULT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- EXTRACT JWT TOKEN FROM COOKIE STRING ---
def extract_jwt(cookie_string):
    for part in cookie_string.split(";"):
        part = part.strip()
        if part.startswith("access_token="):
            return part[len("access_token="):]
    return None

# --- BUILD HEADERS (uses full cookie + Authorization Bearer) ---
def build_headers(cookie_string, subdomain=None):
    # Send only access_token as cookie (confirmed working method)
    jwt = extract_jwt(cookie_string)
    cookie_value = f"access_token={jwt}" if jwt else cookie_string

    headers = {
        "Cookie": cookie_value,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-NG,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://zealy.io",
        "Referer": "https://zealy.io/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Chromium";v="139", "Not;A=Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    jwt = extract_jwt(cookie_string)
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    return headers

# --- BUILD PAYLOAD based on task type ---
def build_payload(task_type, task_id, value=None):
    """
    task_type options:
      visitLink    - just visit a link, no value needed
      url          - submit a link (Twitter reply, website link, etc.)
      text         - submit a word or sentence
      file         - submit a photo (value = s3 image url — uses fileUrls array)
      discordServer - discord join verification, no value needed
    """
    entry = {"taskId": task_id, "type": task_type}

    if task_type == "file":
        # Zealy expects fileUrls as an ARRAY, not a single value field
        entry["fileUrls"] = [value] if value else []

    elif task_type in ["url", "text"]:
        if value:
            entry["value"] = value

    # visitLink and discordServer need no extra fields
    return {"taskValues": [entry]}

# --- S3 PHOTO UPLOAD ---
async def upload_photo(cookie_string, file_path):
    headers = build_headers(cookie_string)
    try:
        async with httpx.AsyncClient(timeout=15.0, proxy=PROXY_URL) as client:
            payload = {"fileName": "proof.png"}
            res = await client.post("https://api-v1.zealy.io/files", headers=headers, json=payload)

            if res.status_code != 200:
                return None, f"Upload handshake failed (Status {res.status_code}): {res.text}"

            data = res.json()
            upload_url = data.get('uploadUrl')
            permanent_url = data.get('fileUrl')

            if not upload_url or not permanent_url:
                return None, f"Missing upload URLs in response: {data}"

            if not os.path.exists(file_path):
                return None, f"Photo file not found at path: {file_path}"

            with open(file_path, 'rb') as f:
                upload_res = await client.put(
                    upload_url,
                    content=f.read(),
                    headers={'Content-Type': 'image/png'}
                )

            if upload_res.status_code in [200, 201]:
                return permanent_url, "Success"
            else:
                return None, f"S3 upload failed (Status {upload_res.status_code})"

    except Exception as e:
        return None, f"Photo upload error: {str(e)}"

# --- MAIN SNIPER LOGIC ---
async def fire_sniper(update: Update = None):
    vault = load_vault()

    if not vault.get("cookie"):
        msg = "❌ No cookie set. Use /setcookie to add your session cookie."
        print(msg)
        if update:
            await update.message.reply_text(msg)
        return

    if not vault.get("tasks"):
        msg = "❌ No tasks in vault. Use /add to load tasks."
        print(msg)
        if update:
            await update.message.reply_text(msg)
        return

    cookie = vault["cookie"]
    # headers built per-task with subdomain
    base_cookie = cookie

    async with httpx.AsyncClient(timeout=15.0, proxy=PROXY_URL) as client:
        for task in vault["tasks"]:
            project   = task["project"]     # e.g. granawin
            quest_id  = task["quest_id"]    # quest UUID
            task_id   = task["task_id"]     # subtask UUID inside the quest
            task_type = task["task_type"]   # visitLink / url / text / file / discord
            value     = task.get("value")   # optional value

            url = f"https://api-v1.zealy.io/communities/{project}/quests/v2/{quest_id}/claim"
            headers = build_headers(base_cookie, subdomain=project)

            # Handle photo upload separately
            if task_type == "file":
                photo_path = value if value else "proof.png"
                if update:
                    await update.message.reply_text(f"📸 Uploading photo for {project}...")
                img_url, status = await upload_photo(cookie, photo_path)
                if img_url:
                    payload = build_payload("file", task_id, img_url)
                else:
                    msg = f"❌ Photo upload failed for {project}: {status}"
                    print(msg)
                    if update:
                        await update.message.reply_text(msg)
                    continue
            else:
                payload = build_payload(task_type, task_id, value)

            # Fire up to 3 attempts
            for attempt in range(3):
                try:
                    print(f"🚀 [Attempt {attempt+1}] Firing {project}...")
                    response = await client.post(url, headers=headers, json=payload)
                    status_code = response.status_code

                    try:
                        resp_json = response.json()
                    except:
                        resp_json = {"raw": response.text}

                    print(f"📡 {project} → Status {status_code} | Response: {resp_json}")

                    # Interpret result
                    resp_status = resp_json.get("status", "")
                    if status_code == 200 and resp_status == "success":
                        msg = f"✅ {project} claimed successfully!"
                    elif status_code == 200 and resp_status == "inReview":
                        msg = f"📋 {project} submitted and is in review. A moderator will approve your photo shortly."
                    elif status_code == 400:
                        msg = f"⚠️ {project}: Already claimed or invalid request.\nDetails: {resp_json}"
                    elif status_code == 401:
                        msg = f"🔒 {project}: Cookie expired or invalid. Use /setcookie to refresh."
                    elif status_code == 403:
                        msg = f"🚫 {project}: Access denied. You may not qualify for this task."
                    elif status_code == 404:
                        msg = f"❓ {project}: Quest or task ID not found. Check your IDs."
                    else:
                        msg = f"📡 {project}: Status {status_code}\n{resp_json}"

                    print(msg)
                    if update:
                        await update.message.reply_text(msg)

                    # Stop retrying on definitive responses
                    if status_code in [200, 400, 401, 403, 404]:
                        break

                except Exception as e:
                    print(f"⚠️ Connection error on attempt {attempt+1}: {e}")
                    if update:
                        await update.message.reply_text(f"⚠️ Connection error (attempt {attempt+1}): {e}")
                    await asyncio.sleep(2)

# --- SCHEDULER (fires at 12:00 AM UTC daily) ---
async def run_scheduler():
    print("⏰ Scheduler active. Waiting for 12:00 AM UTC...")
    fired_today = False
    while True:
        now = datetime.utcnow()
        if now.hour == 0 and now.minute == 0:
            if not fired_today:
                print("🚨 12:00 AM UTC! Firing sniper...")
                await fire_sniper()
                fired_today = True
        else:
            fired_today = False
        await asyncio.sleep(30)  # Check every 30 seconds (more reliable than every 1s)

# =============================================================
# TELEGRAM COMMANDS
# =============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Zealy Sniper Bot* is online!\n\n"
        "*Setup commands:*\n"
        "/setcookie — Save your Zealy session cookie\n"
        "/add — Add a task to the sniper list\n\n"
        "*Action commands:*\n"
        "/fire — Manually trigger the sniper now\n"
        "/list — View all tasks in your vault\n"
        "/remove — Remove a task by project name\n"
        "/clear — Remove ALL tasks\n\n"
        "*Info commands:*\n"
        "/status — Check cookie and task count\n"
        "/help — Show task type guide\n"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- SET COOKIE ---
async def set_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cookie = " ".join(context.args).strip()
    if not cookie:
        await update.message.reply_text(
            "❌ Usage: /setcookie [your full cookie string]\n\n"
            "How to get it:\n"
            "1. Login to zealy.io on browser\n"
            "2. Open DevTools (F12) → Network tab\n"
            "3. Claim any task manually\n"
            "4. Click the 'claim' request\n"
            "5. Go to Headers → scroll to Cookie\n"
            "6. Long press and copy the ENTIRE cookie value\n"
            "7. Paste it here after /setcookie"
        )
        return
    vault = load_vault()
    vault["cookie"] = cookie
    save_vault(vault)
    await update.message.reply_text("✅ Cookie saved successfully!")

# --- ADD TASK ---
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if len(args) < 3:
        await update.message.reply_text(
            "❌ Usage: /add [project] [quest_id] [task_id] [task_type] [value]\n\n"
            "• value is only needed for url, text, and file types\n\n"
            "Examples:\n"
            "/add granawin abc-123 def-456 visitLink\n"
            "/add granawin abc-123 def-456 url https://twitter.com/yourtweet\n"
            "/add granawin abc-123 def-456 text WAGMI\n"
            "/add granawin abc-123 def-456 discordServer\n"
            "/add granawin abc-123 def-456 file proof.png\n\n"
            "Use /help to learn all task types."
        )
        return

    project   = args[0]
    quest_id  = args[1]
    task_id   = args[2]
    task_type = args[3] if len(args) > 3 else "visitLink"
    value     = args[4] if len(args) > 4 else None

    valid_types = ["visitLink", "url", "text", "file", "discordServer"]
    if task_type not in valid_types:
        await update.message.reply_text(
            f"❌ Invalid task type: {task_type}\n"
            f"Valid types: {', '.join(valid_types)}"
        )
        return

    vault = load_vault()
    vault["tasks"].append({
        "project": project,
        "quest_id": quest_id,
        "task_id": task_id,
        "task_type": task_type,
        "value": value
    })
    save_vault(vault)

    value_display = f" | Value: {value}" if value else ""
    await update.message.reply_text(
        f"📥 Task added!\n"
        f"Project: {project}\n"
        f"Type: {task_type}{value_display}"
    )

# --- MANUAL FIRE ---
async def manual_fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔫 Firing sniper now...")
    try:
        await fire_sniper(update)
        await update.message.reply_text("🏁 Sniper run complete.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

# --- LIST TASKS ---
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vault = load_vault()
    if not vault["tasks"]:
        await update.message.reply_text("📭 No tasks in vault.")
        return

    msg = "🎯 *Active Tasks:*\n\n"
    for i, t in enumerate(vault["tasks"], 1):
        value_line = f"\n   Value: {t['value']}" if t.get('value') else ""
        msg += (
            f"{i}. *{t['project']}*\n"
            f"   Quest ID: `{t['quest_id']}`\n"
            f"   Task ID: `{t['task_id']}`\n"
            f"   Type: {t['task_type']}{value_line}\n\n"
        )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- REMOVE TASK ---
async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /remove [project_name]")
        return

    target = context.args[0]
    vault = load_vault()
    before = len(vault["tasks"])
    vault["tasks"] = [t for t in vault["tasks"] if t["project"] != target]

    if len(vault["tasks"]) < before:
        save_vault(vault)
        await update.message.reply_text(f"🗑️ Removed all tasks for: {target}")
    else:
        await update.message.reply_text(f"❓ No tasks found for project: {target}")

# --- CLEAR ALL TASKS ---
async def clear_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vault = load_vault()
    vault["tasks"] = []
    save_vault(vault)
    await update.message.reply_text("🧹 All tasks cleared from vault.")

# --- STATUS ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vault = load_vault()
    cookie_status = "✅ Cookie is set" if vault.get("cookie") else "❌ No cookie saved"
    task_count = len(vault.get("tasks", []))
    await update.message.reply_text(
        f"📊 *Bot Status*\n\n"
        f"{cookie_status}\n"
        f"Tasks loaded: {task_count}\n"
        f"Scheduler: Active (fires at 12:00 AM UTC daily)",
        parse_mode='Markdown'
    )

# --- HELP ---
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *Task Type Guide*\n\n"
        "*visitLink* — Task where you visit a website\n"
        "No value needed\n"
        "`/add projectname questid taskid visitLink`\n\n"
        "*url* — Task where you submit a link (Twitter, etc.)\n"
        "Value = the link you're submitting\n"
        "`/add projectname questid taskid url https://yourlink.com`\n\n"
        "*text* — Task where you type a word or phrase\n"
        "Value = the word or answer\n"
        "`/add projectname questid taskid text WAGMI`\n\n"
        "*discordServer* — Task verified by your connected Discord\n"
        "No value needed\n"
        "`/add projectname questid taskid discordServer`\n\n"
        "*file* — Task where you submit a photo as proof\n"
        "Value = filename (e.g. proof.png)\n"
        "`/add projectname questid taskid file proof.png`\n\n"
        "📌 *How to find Quest ID and Task ID:*\n"
        "Open DevTools → Network → claim request\n"
        "Check the URL path for quest ID\n"
        "Check the Payload tab for task ID"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- MAIN ---
if __name__ == "__main__":
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable not set!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setcookie", set_cookie))
        app.add_handler(CommandHandler("add", add_task))
        app.add_handler(CommandHandler("fire", manual_fire))
        app.add_handler(CommandHandler("list", list_tasks))
        app.add_handler(CommandHandler("remove", remove_task))
        app.add_handler(CommandHandler("clear", clear_tasks))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("help", help_cmd))

        print("⚡ Zealy Sniper Bot starting...")

        loop = asyncio.get_event_loop()
        loop.create_task(run_scheduler())

        app.run_polling()
