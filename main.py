import requests
import os
import telebot # Assuming you use telebot/pyTelegramBotAPI

# 1. THE SNIPER ENGINE
# This handles the Zealy handshake and S3 upload
def zealy_snipe_upload(api_token, file_path):
    headers = {
        'x-api-key': api_token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    try:
        # A. Handshake: Get the S3 slot
        payload = {"fileName": "proof.png"}
        res = requests.post("https://api-v1.zealy.io/files", headers=headers, json=payload, timeout=10)
        
        if res.status_code != 200:
            return None, f"Handshake Failed ({res.status_code})"

        data = res.json()
        upload_url = data['uploadUrl'] # Temporary S3 link
        permanent_url = data['fileUrl'] # The URL we submit

        # B. The Upload: Sending the image
        with open(file_path, 'rb') as f:
            upload_res = requests.put(
                upload_url, 
                data=f, 
                headers={'Content-Type': 'image/png'},
                timeout=15
            )
        
        if upload_res.status_code in [200, 201]:
            return permanent_url, "Success"
        else:
            return None, f"Upload Failed ({upload_res.status_code})"
            
    except Exception as e:
        return None, str(e)

# 2. THE TELEGRAM COMMAND
# Replace your existing /load command with this
bot = telebot.TeleBot("5492294313:AAFgr1XxjID0WWtaUTgccYy_eTSrRSQT1Yk")

@bot.message_handler(commands=['load'])
def load_task(message):
    # Split the command (e.g., /load TASK_ID photo)
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ Use: /load [TASK_ID] [type]")
        return

    task_id = args[1]
    task_type = args[2].lower()
    
    # You should have your token saved in Railway environment variables
    # or replace this string with your actual token
    zealy_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJiNTg5MDA0ZS1hY2YzLTRmMWMtOTQ2OC02M
WJhYmUwZWZkN2IiLCJhY2NvdW50VHIwZSI6ImVtYWlsIiwiaW1haWwiOiJjnlwdGVkNDA0QGdtYWlsLmN
vbSIsImxhc3RFbWFpbENoZWNrljoxNzc4NjE4MjIxOTE5LCIpYXQiOjE3Nzg2MTgyMjEsImV4cCI6MTc4MTIx
MDIyMX0.dsTMCV_v3-nTf8ivkFJIdQcP2VX9pfixzRxTaPRm3nk" 

    bot.send_message(message.chat.id, f"🚀 Sniping Task: `{task_id}`...")

    if task_type == "photo":
        # Make sure 'proof.png' is uploaded to your GitHub folder!
        img_url, status = zealy_snipe_upload(zealy_token, "proof.png")
        
        if img_url:
            # Final step: Submitting the claim to Zealy
            claim_headers = {'x-api-key': zealy_token}
            claim_payload = {
                "questId": task_id,
                "type": "upload",
                "value": img_url
            }
            
            # Sending the actual claim request
            claim_res = requests.post(
                f"https://api-v1.zealy.io/communities/YOUR_COMMUNITY_ID/quests/{task_id}/claim",
                headers=claim_headers,
                json=claim_payload
            )
            
            if claim_res.status_code == 200:
                bot.reply_to(message, "✅ Photo Uploaded & Claimed successfully!")
            else:
                bot.reply_to(message, f"❌ Upload worked, but Claim failed: {claim_res.status_code}")
        else:
            bot.reply_to(message, f"❌ Sniper Error: {status}")
    else:
        # Standard text claim logic
        bot.reply_to(message, "✅ Text task logic triggered (add your text claim code here).")

bot.polling()
