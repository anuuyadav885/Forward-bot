import re    
import os 
import sys
import time      
import pymongo
import asyncio
import tgcrypto
import requests
import datetime
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

image_list = [
    "https://www.pixelstalk.net/wp-content/uploads/2025/03/A-breathtaking-image-of-a-lion-roaring-proudly-atop-a-rocky-outcrop-with-dramatic-clouds-and-rays-of-sunlight-breaking-through-2.webp"
    ]
class Data:
    START = (
        "<blockquote>🌟 𝑾𝑬𝑳𝑪𝑶𝑴𝑬  {0}! 🌟</blockquote>\n\n"
    )
# Define the start command handler
@app.on_message(filters.command("start"))
async def start(client: Client, msg: Message):
    user = await client.get_me()
    mention = user.mention
    random_image = random.choice(image_list)
    start_message = await client.send_photo(
         chat_id=msg.chat.id,
         photo=random_image,
         caption=Data.START.format(msg.from_user.mention)
    )
    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Initializing Uploader bot... 🤖\n\n"
        "Progress: [⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%\n\n"
    )
    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Checking status Ok... Bot started successfully🔍\n\n"
        "Progress:[🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%\n\n"
    )
    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "<blockquote>👋 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙏𝙊 𝙁𝙊𝙍𝙒𝘼𝙍𝘿 𝘽𝙊𝙏 👋</blockquote>\n\n"
        "📚 *Available Commands:*\n"
        "• /target – Set target via message link\n"
        "• /forward – Forward messages via message links\n"
        "• /cancel – Cancel ongoing forwarding\n\n"
        "🚀 *Use the bot to forward messages fast and easily!* 🌟\n"
    )

@app.on_message(filters.command("target") & filters.private)
async def set_target(client, message):
    await message.reply("<blockquote>📩 Send a **message link** from the **target channel**</blockquote>")
    try:
        link_msg = await client.listen(message.chat.id, timeout=120)
        link = link_msg.text.strip()
        chat_id, _ = extract_ids_from_link(link)
        if not chat_id:
            return await message.reply("<blockquote>❌ Invalid link</blockquote>")
        users.update_one({"user_id": message.from_user.id}, {"$set": {"target_chat": chat_id}}, upsert=True)
        await message.reply(f"✅ Target set to `{chat_id}`")
    except asyncio.TimeoutError:
        await message.reply("<blockquote>⏰ Timed out. Please try again</blockquote>")

@app.on_message(filters.command("forward") & filters.private)
async def forward_command(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = False

    user = users.find_one({"user_id": user_id})
    if not user or "target_chat" not in user:
        return await message.reply("<blockquote>❗ Please set target first using /settarget</blockquote>")

    target_chat = user["target_chat"]

    await message.reply("<blockquote>📩 Send the **start message link** from the source channel</blockquote>")
    try:
        start_msg = await client.listen(message.chat.id, timeout=120)
        start_chat, start_id = extract_ids_from_link(start_msg.text.strip())
        if not start_chat or not start_id:
            return await message.reply("<blockquote>❌ Invalid start message link</blockquote>")

        await message.reply("<blockquote>📩 Send the **end message link**</blockquote>")
        end_msg = await client.listen(message.chat.id, timeout=120)
        _, end_id = extract_ids_from_link(end_msg.text.strip())
        if not end_id:
            return await message.reply("<blockquote>❌ Invalid end message link</blockquote>")

    except asyncio.TimeoutError:
        return await message.reply("<blockquote>⏰ Timed out. Please try again</blockquote>")

    total = end_id - start_id + 1
    count = 0
    failed = 0
    start_time = time.time()

    try:
        source_chat = await client.get_chat(start_chat)
        target = await client.get_chat(target_chat)
    except PeerIdInvalid:
        return await message.reply("<blockquote>❌ Bot doesn't have access. Add it to both source and target</blockquote>")

    status = await message.reply(
        f"╔═════════════════════════╗"
        f"┃          𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝙄𝙉𝙄𝙏𝙄𝘼𝙏𝙀𝘿\n"
        f"┃ 🗂 Source : `{source_chat.title}`\n"
        f"┃ 📤 Target : `{target.title}`\n"
        f"╚═════════════════════════╝"
    )


    for msg_id in range(start_id, end_id + 1):
        if cancel_flags.get(user_id):
            await status.edit(
                f"╔═════════════════════════╗"
                f"┃          𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝘾𝘼𝙉𝘾𝙀𝙇𝙇𝙀𝘿\n"
                f"┃ 📌 Stopped at Message ID: `{msg_id}`\n"
                f"┃ 📤 Messages Forwarded: `{count}` out of `{total}`\n"
                f"╚═════════════════════════╝\n\n"
            )
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
        eta_seconds = (elapsed / (count + failed)) * (total - count - failed) if (count + failed) else 0
        
        def format_eta(seconds):
            delta = datetime.timedelta(seconds=int(seconds))
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            parts = []
            if days > 0: parts.append(f"{days}d")
            if hours > 0: parts.append(f"{hours}h")
            if minutes > 0: parts.append(f"{minutes}m")
            if secs > 0 or not parts: parts.append(f"{secs}s")
            return " ".join(parts)
        
        eta = format_eta(eta_seconds)
        remaining = total - (count + failed)
        progress_bar = f"{'⚫' * int(percent // 5)}{'⚪' * (10 - int(percent // 5))}"
        
        try:
            await status.edit(
                f"╔═════════════════════════╗"
                f"┃          🎯 𝙎𝙊𝙐𝙍𝘾𝙀 / 𝙏𝘼𝙍𝙂𝙀𝙏 𝙄𝙉𝙁𝙊 🎯\n"
                f"┃ 📤 From  : `{source_chat.title}`\n"
                f"┃ 📥 To  :  `{target.title}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═════════════════════════╗"
                f"┃          📦 𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝙋𝙍𝙊𝙂𝙍𝙀𝙎𝙎 📦\n"
                f"┃ 📊 Progress  : `{count + failed}/{total}` ({percent:.1f}%)\n"
                f"┃ 📌 Remaining  : `{remaining}`\n"
                f"┃ ▓ {progress_bar}\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═════════════════════════╗"
                f"┃          📈 𝙋𝙀𝙍𝙁𝙊𝙍𝙈𝘼𝙉𝘾𝙀 𝙈𝙀𝙏𝙍𝙄𝘾𝙎 📈\n"
                f"┃ ✅ Success  : `{count}`\n"
                f"┃ ❌ Deleted  :  `{failed}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═════════════════════════╗"
                f"┃          ⏱️ 𝙏𝙄𝙈𝙄𝙉𝙂 𝘿𝙀𝙏𝘼𝙄𝙇𝙎 ⏱️\n"
                f"┃ ⌛ Elapsed  : `{int(elapsed)}s`\n"
                f"┃ ⏳ ETA  :  `{eta}`\n"
                f"╚═════════════════════════╝\n\n"
            )
        except Exception as e:
            print(f"Progress update error: {e}")

        await asyncio.sleep(0.2)

    time_taken = format_eta(time.time() - start_time)
    await status.edit(
        f"╔═════════════════════════╗"
        f"┃          ✅ 𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝘾𝙊𝙈𝙋𝙇𝙀𝙏𝙀 ✅\n"
        f"┃ 📤 From  : `{source_chat.title}`\n"
        f"┃ 🎯 To  : `{target.title}`\n"
        f"┃ ✅ Success  : `{count}`\n"
        f"┃ ❌ Deleted  : `{failed}`\n"
        f"┃ 📊 Total  : `{total}`\n"
        f"┃ ⏱️ Time  : `{time_taken}`\n"
        f"╚═════════════════════════╝"
    )

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    cancel_flags[message.from_user.id] = True
    await message.reply(
        f"╔═════════════════════════╗"
        f"┃          🛑 𝘾𝘼𝙉𝘾𝙀𝙇 𝙍𝙀𝙌𝙐𝙀𝙎𝙏𝙀𝘿 🛑\n"
        f"┃ ⚙️ Attempting to halt forwarding...\n"
        f"┃ ⏳ Please wait a moment.\n"
        f"╚═════════════════════════╝"
    )


app.run()
