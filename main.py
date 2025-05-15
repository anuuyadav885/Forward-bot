import re    
import os 
import sys
import time      
import pymongo
import asyncio
import tgcrypto
import requests
import datetime
import random
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

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📝 Caption", callback_data="caption_settings")],
    [InlineKeyboardButton("🧰 Filters", callback_data="filter_settings")],
    [InlineKeyboardButton("♻️ Reset Settings", callback_data="reset_settings")],
    [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
])

@app.on_message(filters.command("settings") & filters.private)
async def settings_handler(client, message):
    await message.reply("⚙️ Choose a setting to configure:", reply_markup=keyboard)

@app.on_callback_query()
async def handle_callbacks(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "caption_settings":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Replace Word", callback_data="add_replace_word"),
             InlineKeyboardButton("➖ Delete Word", callback_data="add_delete_word")],
            [InlineKeyboardButton("🧹 Remove Links", callback_data="toggle_remove_links"),
             InlineKeyboardButton("🔗 Replace Links", callback_data="toggle_replace_links")],
            [InlineKeyboardButton("🙅 Remove Username", callback_data="toggle_remove_username"),
             InlineKeyboardButton("👤 Replace Username", callback_data="toggle_replace_username")],
            [InlineKeyboardButton("📌 Auto Pin", callback_data="toggle_auto_pin")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ])
        await callback_query.message.edit_text("📝 Caption Settings", reply_markup=keyboard)

    elif data == "filter_settings":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Text", callback_data="toggle_text"),
             InlineKeyboardButton("📹 Video", callback_data="toggle_video")],
            [InlineKeyboardButton("🖼 Photo", callback_data="toggle_photo"),
             InlineKeyboardButton("🎧 Audio", callback_data="toggle_audio")],
            [InlineKeyboardButton("📄 Document", callback_data="toggle_document"),
             InlineKeyboardButton("🎞 Animation", callback_data="toggle_animation")],
            [InlineKeyboardButton("📊 Poll", callback_data="toggle_poll"),
             InlineKeyboardButton("🚫 Skip Duplicate", callback_data="toggle_skip_duplicate")],
            [InlineKeyboardButton("🔖 Forward Tag", callback_data="toggle_forward_tag"),
             InlineKeyboardButton("🔒 Secure Msgs", callback_data="toggle_secure")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ])
        await callback_query.message.edit_text("🧰 Filter Settings", reply_markup=keyboard)

    elif data == "reset_settings":
        users.update_one({"user_id": user_id}, {"$unset": {
            "caption_settings": "",
            "filter_settings": "",
            "target_chat": ""
        }})
        await callback_query.message.edit_text("✅ Settings reset!")

    elif data == "back_to_start":
        await start(client, callback_query.message)


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
        "<blockquote>𝑾𝑬𝑳𝑪𝑶𝑴𝑬 !  {0}</blockquote>\n\n"
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
        "📚 **Available Commands  :**\n\n"
        "• /target – Set target via message link\n"
        "• /forward – Forward messages via message links\n"
        "• /cancel – Cancel ongoing forwarding\n\n"
        "🚀 *Use the bot to forward messages fast and easily!* 🌟\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ])
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

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@app.on_message(filters.command("forward") & filters.private)
async def forward_command(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = False  # False means running; "paused" means paused

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
    except Exception:
        return await message.reply("<blockquote>❌ Bot doesn't have access. Add it to both source and target</blockquote>")

    status = await message.reply(
        f"╔════ 𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝙄𝙉𝙄𝙏𝙄𝘼𝙏𝙀𝘿 ════╗\n"
        f"┃\n"
        f"┃ 🗂 Source : `{source_chat.title}`\n"
        f"┃ 📤 Target : `{target.title}`\n"
        f"╚═════════════════════════╝",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏸ Pause", callback_data="pause_forward"),
             InlineKeyboardButton("▶️ Resume", callback_data="resume_forward")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_forward")]
        ])
    )


    for msg_id in range(start_id, end_id + 1):
        if cancel_flags.get(user_id) == True:
            await status.edit(
                f"╔═══ 𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝘾𝘼𝙉𝘾𝙀𝙇𝙇𝙀𝘿 ═══╗\n"
                f"┃\n"
                f"┃ 📌 Stopped at Message ID: `{msg_id}`\n"
                f"┃ 📤 Messages Forwarded: `{count}` out of `{total}`\n"
                f"╚═════════════════════════╝\n\n"
            )
            cancel_flags[user_id] = False
            return

        while cancel_flags.get(user_id) == "paused":
            await asyncio.sleep(1)  # Pause loop

        try:
            msg = await client.get_messages(start_chat, msg_id)
            if not msg or getattr(msg, "empty", False) or getattr(msg, "protected_content", False):
                failed += 1
                continue

            # Check filter settings
            filters_enabled = user.get("filter_settings", {})
            media_type = msg.media.value if msg.media else "text"
            if not filters_enabled.get(media_type, True):
                continue  # skip this message

            # Caption/text modification logic
            settings = user.get("caption_settings", {})
            kwargs = {}
            if msg.caption or msg.text:
                text = msg.caption or msg.text
                for k, v in settings.get("replace_words", {}).items():
                    text = text.replace(k, v)
                for word in settings.get("delete_words", []):
                    text = text.replace(word, "")
                if settings.get("remove_links"):
                    text = re.sub(r'https?://\S+', '', text)
                if settings.get("replace_links"):
                    text = re.sub(r'https?://\S+', '🔗 Link removed', text)
                if settings.get("remove_username"):
                    text = re.sub(r"@\w+", '', text)
                if settings.get("replace_username"):
                    text = re.sub(r"@\w+", settings["replace_username"], text)
                kwargs = {"caption": text}

            # Forward message with auto pin logic
            if settings.get("auto_pin"):
                if msg.pinned:
                    sent_msg = await msg.copy(target_chat, **kwargs)
                    try:
                        await client.pin_chat_message(target_chat, sent_msg.id, disable_notification=True)
                        await client.unpin_chat_message(target_chat)  # remove previous banner
                    except Exception:
                        pass
                else:
                    await msg.copy(target_chat, **kwargs)
            else:
                await msg.copy(target_chat, **kwargs)

            count += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception:
            failed += 1
            continue

        # Progress update
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
        progress_bar = f"{'█' * int(percent // 5)}{'░' * (20 - int(percent // 5))}"
        elapsed_text = format_eta(int(elapsed))

        try:
            await status.edit(
                f"╔══ 🎯 𝙎𝙊𝙐𝙍𝘾𝙀 / 𝙏𝘼𝙍𝙂𝙀𝙏 𝙄𝙉𝙁𝙊 🎯 ══╗\n"
                f"┃\n"
                f"┃ 📤 From  : `{source_chat.title}`\n"
                f"┃ 🎯 To  :  `{target.title}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═  📦 𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝙋𝙍𝙊𝙂𝙍𝙀𝙎𝙎 📦  ═╗\n"
                f"┃\n"
                f"┃ 📊 Progress  : `{count + failed}/{total}` ({percent:.2f}%)\n"
                f"┃ 📌 Remaining  : `{remaining}`\n"
                f"┃ ▓ {progress_bar}\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═  📈 𝙋𝙀𝙍𝙁𝙊𝙍𝙈𝘼𝙉𝘾𝙀 𝙈𝙀𝙏𝙍𝙄𝘾𝙎  📈  ═╗\n"
                f"┃\n"
                f"┃ ✅ Success  : `{count}`\n"
                f"┃ ❌ Deleted  :  `{failed}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔════ ⏱️ 𝙏𝙄𝙈𝙄𝙉𝙂 𝘿𝙀𝙏𝘼𝙄𝙇𝙎 ⏱️ ═════╗\n"
                f"┃\n"
                f"┃ ⌛ Elapsed  : `{elapsed_text}`\n"
                f"┃ ⏳ ETA  :  `{eta}`\n"
                f"╚═════════════════════════╝\n\n"
            )
        except Exception as e:
            print(f"Progress update error: {e}")

        await asyncio.sleep(0.5)

    time_taken = format_eta(time.time() - start_time)
    await status.edit(
        f"╔═  ✅ 𝙁𝙊𝙍𝙒𝘼𝙍𝘿𝙄𝙉𝙂 𝘾𝙊𝙈𝙋𝙇𝙀𝙏𝙀 ✅  ═╗\n"
        f"┃\n"
        f"┃ 📤 From  : `{source_chat.title}`\n"
        f"┃ 🎯 To  : `{target.title}`\n"
        f"┃ ✅ Success  : `{count}`\n"
        f"┃ ❌ Deleted  : `{failed}`\n"
        f"┃ 📊 Total  : `{total}`\n"
        f"┃ ⏱️ Time  : `{time_taken}`\n"
        f"╚═════════════════════════╝"
    )


@app.on_callback_query()
async def forward_controls(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "pause_forward":
        cancel_flags[user_id] = "paused"
        await callback_query.answer("⏸ Forwarding paused.")

    elif data == "resume_forward":
        cancel_flags[user_id] = False
        await callback_query.answer("▶️ Forwarding resumed.")

    elif data == "cancel_forward":
        cancel_flags[user_id] = True
        await callback_query.answer("❌ Forwarding cancelled.")

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    cancel_flags[message.from_user.id] = True
    await message.reply(
        f"╔═══ 🛑 𝘾𝘼𝙉𝘾𝙀𝙇 𝙍𝙀𝙌𝙐𝙀𝙎𝙏𝙀𝘿 🛑 ═══╗\n"
        f"┃\n"
        f"┃ ⚙️ Attempting to halt forwarding...\n"
        f"┃ ⏳ Please wait a moment.\n"
        f"╚═════════════════════════╝"
    )


app.run()
