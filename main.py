import re    
import os 
import sys
import time      
import pymongo
import asyncio
import tgcrypto
import requests
from pyromod import listen
from pyrogram import enums 
from Crypto.Cipher import AES
from pymongo import MongoClient
from aiohttp import ClientSession    
from pyrogram.types import Message   
from pyrogram import Client, filters
from base64 import b64encode, b64decode
from pyrogram.errors import FloodWait, PeerIdInvalid, RPCError
from pyrogram.types import User, Message        
from pyrogram.types.messages_and_media import message
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URI
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid

# Initialize bot and MongoDB
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["forward_bot"]
users = db["users"]

cancel_flags = {}

# Utility to extract chat_id and message_id from a message link
def extract_ids_from_link(link):
    match = re.search(r"https://t.me/(c/)?([\w_]+)/?(\d+)?", link)
    if not match:
        return None, None
    if match.group(1):  # private group/channel
        chat_id = int(f"-100{match.group(2)}")
    else:
        username = match.group(2)
        chat_id = username if not username.isdigit() else int(username)
    msg_id = int(match.group(3)) if match.group(3) else None
    return chat_id, msg_id

@app.on_message(filters.command("start"))
async def start_cmd(_, msg: Message):
    await msg.reply(
        """
<blockquote>👋 Welcome to Advanced Telegram Forward Bot!</blockquote>

Use:
/settarget – set target via message link
/forward – forward messages via message links
/cancel – cancel ongoing forwarding
        """
    )

@app.on_message(filters.command("settarget") & filters.private)
async def set_target(client, message):
    await message.reply("📩 Send a **message link** from the **target channel**:")
    try:
        link_msg = await client.listen(message.chat.id, timeout=120)
        link = link_msg.text.strip()
        chat_id, _ = extract_ids_from_link(link)
        if not chat_id:
            return await message.reply("❌ Invalid link.")
        users.update_one({"user_id": message.from_user.id}, {"$set": {"target_chat": chat_id}}, upsert=True)
        await message.reply(f"✅ Target set to `{chat_id}`")
    except asyncio.TimeoutError:
        await message.reply("⏰ Timed out. Please try again.")

@app.on_message(filters.command("forward") & filters.private)
async def forward_command(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = False

    user = users.find_one({"user_id": user_id})
    if not user or "target_chat" not in user:
        return await message.reply("❗ Please set target first using /settarget")

    target_chat = user["target_chat"]

    await message.reply("📩 Send the **start message link** from the source channel:")
    try:
        start_msg = await client.listen(message.chat.id, timeout=120)
        start_chat, start_id = extract_ids_from_link(start_msg.text.strip())
        if not start_chat or not start_id:
            return await message.reply("❌ Invalid start message link.")

        await message.reply("📩 Send the **end message link**:")
        end_msg = await client.listen(message.chat.id, timeout=120)
        _, end_id = extract_ids_from_link(end_msg.text.strip())
        if not end_id:
            return await message.reply("❌ Invalid end message link.")

    except asyncio.TimeoutError:
        return await message.reply("⏰ Timed out. Please try again.")

    total = end_id - start_id + 1
    count = 0
    failed = 0
    start_time = time.time()

    try:
        source_chat = await client.get_chat(start_chat)
        target = await client.get_chat(target_chat)
    except PeerIdInvalid:
        return await message.reply("❌ Bot doesn't have access. Add it to both source and target.")

    status = await message.reply(f"🔄 Starting forward from `{source_chat.title}` to `{target.title}`...")

    for msg_id in range(start_id, end_id + 1):
        if cancel_flags.get(user_id):
            await status.edit(f"🚫 Cancelled at message {msg_id}. Forwarded {count}/{total}.")
            cancel_flags[user_id] = False
            return

        try:
            msg = await client.get_messages(start_chat, msg_id)
            if msg and not getattr(msg, "empty", False) and not getattr(msg, "protected_content", False):
                await msg.copy(target_chat)
                count += 1
            else:
                failed += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except RPCError:
            failed += 1
            continue

        elapsed = time.time() - start_time
        percent = (count + failed) / total * 100
        eta = (elapsed / (count + failed)) * (total - count - failed) if (count + failed) else 0
        progress = f"{'█' * int(percent // 5)}{'░' * (20 - int(percent // 5))}"

        try:
            await status.edit(
                f"**Forwarding...**\n"
                f"From: `{source_chat.title}`\nTo: `{target.title}`\n"
                f"{progress} {percent:.1f}%\n"
                f"✅ Success: {count} | ❌ Failed: {failed}\n"
                f"⏱ ETA: {int(eta)}s | Total: {total}"
            )
        except:
            pass

        await asyncio.sleep(0.5)

    await status.edit(
        f"✅ Forwarding complete.\nFrom `{source_chat.title}` to `{target.title}`\n"
        f"✅ Success: {count} | ❌ Failed: {failed} | Total: {total}"
    )

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    cancel_flags[message.from_user.id] = True
    await message.reply("🛑 Cancelling... Please wait.")

app.run()
