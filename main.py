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
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid

# Initialize bot and MongoDB
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["forward_bot"]
users = db["users"]

cancel_flags = {}
pause_flags = {}

def control_buttons(user_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause", callback_data=f"pause:{user_id}"),
            InlineKeyboardButton("▶️ Resume", callback_data=f"resume:{user_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{user_id}")
        ]
    ])

# SETTINGS HANDLER
@app.on_message(filters.command("settings") & filters.private)
async def settings_handler(client, message):
    user_id = message.from_user.id
    user_settings = users.find_one({"user_id": user_id}) or {}

    buttons = [
        [InlineKeyboardButton(f"Caption ✏️", callback_data="open_caption_settings")],
        [InlineKeyboardButton(f"Filters 🎛️", callback_data="open_filters")],
        [InlineKeyboardButton(f"Reset Settings ♻️", callback_data="reset_settings")]
    ]

    await message.reply("\ud83d\udd27 **Settings Menu**", reply_markup=InlineKeyboardMarkup(buttons))

# CALLBACK QUERY HANDLER
@app.on_callback_query()
async def callback_query_handler(client, cq):
    user_id = cq.from_user.id
    data = cq.data
    user_settings = users.find_one({"user_id": user_id}) or {}

    if data == "open_caption_settings":
        buttons = [
            [InlineKeyboardButton(f"Replace Words: {'✅' if user_settings.get('replace_words') else '❌'}", callback_data="toggle_replace_words")],
            [InlineKeyboardButton(f"Delete Words: {'✅' if user_settings.get('delete_words') else '❌'}", callback_data="toggle_delete_words")],
            [InlineKeyboardButton(f"Remove Links: {'✅' if user_settings.get('remove_links') else '❌'}", callback_data="toggle_remove_links")],
            [InlineKeyboardButton(f"Replace Links: {'✅' if user_settings.get('replace_links') else '❌'}", callback_data="toggle_replace_links")],
            [InlineKeyboardButton(f"Remove Usernames: {'✅' if user_settings.get('remove_usernames') else '❌'}", callback_data="toggle_remove_usernames")],
            [InlineKeyboardButton(f"Replace Usernames: {'✅' if user_settings.get('replace_usernames') else '❌'}", callback_data="toggle_replace_usernames")],
            [InlineKeyboardButton(f"Auto Pin: {'✅' if user_settings.get('auto_pin') else '❌'}", callback_data="toggle_auto_pin")],
            [InlineKeyboardButton("Back ◀️", callback_data="back_to_settings")]
        ]
        await cq.message.edit("✏️ **Caption Settings**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "open_filters":
        filters_dict = user_settings.get("filters", {})
        filters_buttons = [
            [InlineKeyboardButton(f"Text: {'✅' if filters_dict.get('text', True) else '❌'}", callback_data="filter_text"),
             InlineKeyboardButton(f"Photo: {'✅' if filters_dict.get('photo', True) else '❌'}", callback_data="filter_photo")],
            [InlineKeyboardButton(f"Video: {'✅' if filters_dict.get('video', True) else '❌'}", callback_data="filter_video"),
             InlineKeyboardButton(f"Audio: {'✅' if filters_dict.get('audio', True) else '❌'}", callback_data="filter_audio")],
            [InlineKeyboardButton(f"Document: {'✅' if filters_dict.get('document', True) else '❌'}", callback_data="filter_document"),
             InlineKeyboardButton(f"Animation: {'✅' if filters_dict.get('animation', True) else '❌'}", callback_data="filter_animation")],
            [InlineKeyboardButton(f"Sticker: {'✅' if filters_dict.get('sticker', True) else '❌'}", callback_data="filter_sticker"),
             InlineKeyboardButton(f"Poll: {'✅' if filters_dict.get('poll', True) else '❌'}", callback_data="filter_poll")],
            [InlineKeyboardButton(f"Skip Duplicates: {'✅' if filters_dict.get('skip_duplicates', True) else '❌'}", callback_data="filter_skip_duplicates")],
            [InlineKeyboardButton(f"Forward Tag: {'✅' if filters_dict.get('forward_tag', True) else '❌'}", callback_data="filter_forward_tag")],
            [InlineKeyboardButton(f"Secure Messages: {'✅' if filters_dict.get('secure_messages', True) else '❌'}", callback_data="filter_secure_messages")],
            [InlineKeyboardButton("Back ◀️", callback_data="back_to_settings")]
        ]
        await cq.message.edit("🎛️ **Filter Settings**", reply_markup=InlineKeyboardMarkup(filters_buttons))

    elif data.startswith("filter_"):
        field = data.split("_")[1]
        filters_dict = user_settings.get("filters", {})
        filters_dict[field] = not filters_dict.get(field, True)
        users.update_one({"user_id": user_id}, {"$set": {"filters": filters_dict}}, upsert=True)
        await cq.answer(f"{field.replace('_', ' ').title()} filter set to {'✅' if filters_dict[field] else '❌'}")
        await callback_query_handler(client, cq)  # refresh current menu

    elif data.startswith("toggle_"):
        field = data.split("toggle_")[1]
        current = user_settings.get(field)
        users.update_one({"user_id": user_id}, {"$set": {field: not current}}, upsert=True)
        await cq.answer(f"{field.replace('_', ' ').title()} set to {'✅' if not current else '❌'}")
        await callback_query_handler(client, cq)  # refresh current menu

    elif data == "reset_settings":
        users.delete_one({"user_id": user_id})
        await cq.answer("Settings reset.")
        await settings_handler(client, cq.message)

    elif data == "back_to_settings":
        await settings_handler(client, cq.message)


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
        "Initializing forward bot... 🤖\n\n"
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
        "<blockquote>👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐅𝐎𝐑𝐖𝐀𝐑𝐃 𝐁𝐎𝐓 👋</blockquote>\n\n"
        "📚 **Available Commands  :**\n\n"
        "• /target – Set target via message link\n"
        "• /forward – Forward messages via message links\n"
        "• /cancel – Cancel ongoing forwarding\n\n"
        "🚀 *Use the bot to forward messages fast and easily!* 🌟\n",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⚙️ Settings", callback_data="open_main_settings")]]
        )
    )

@Client.on_callback_query(filters.regex("open_main_settings"))
async def open_main_settings_menu(client, callback_query):
    await callback_query.message.edit_text(
        "⚙️ **Settings Menu**:\nChoose an option to configure the bot.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Caption", callback_data="open_caption_settings")],
            [InlineKeyboardButton("🎛️ Filters", callback_data="open_filters")],
            [InlineKeyboardButton("♻️ Reset Settings", callback_data="reset_settings")],
            [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
        ])
    )

@Client.on_callback_query(filters.regex("start_back"))
async def go_back_to_start(client, callback_query):
    await callback_query.message.edit_text(
        Data.START.format(callback_query.from_user.mention) +
        "<blockquote>👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐅𝐎𝐑𝐖𝐀𝐑𝐃 𝐁𝐎𝐓 👋</blockquote>\n\n"
        "📚 **Available Commands  :**\n\n"
        "• /target – Set target via message link\n"
        "• /forward – Forward messages via message links\n"
        "• /settings – Customize filters, captions & options ⚙️\n"
        "• /cancel – Cancel ongoing forwarding\n\n"
        "🚀 *Use the bot to forward messages fast and easily!* 🌟\n",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⚙️ Settings", callback_data="open_main_settings")]]
        )
    )
    await callback_query.answer()


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

# Updated /forward command with settings applied
@app.on_message(filters.command("forward") & filters.private)
async def forward_command(client, message):
    user_id = message.from_user.id
    cancel_flags[user_id] = False

    user = users.find_one({"user_id": user_id})
    if not user or "target_chat" not in user:
        return await message.reply("<blockquote>❗ Please set target first using /settarget</blockquote>")

    settings = user
    filters_dict = settings.get("filters", {})
    target_chat = settings["target_chat"]

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

    pause_flags[user_id] = False
    cancel_flags[user_id] = False
    
    status = await message.reply(
        f"╔════ 𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐈𝐍𝐈𝐓𝐈𝐀𝐓𝐄𝐃 ════╗\n"
        f"┃\n"
        f"┃ 🗂 Source : `{source_chat.title}`\n"
        f"┃ 📤 Target : `{target.title}`\n"
        f"╚═════════════════════════╝",
        reply_markup=control_buttons(user_id)
    )


    for msg_id in range(start_id, end_id + 1):
        # Cancel check
        if cancel_flags.get(user_id):
            await status.edit_text(
                f"╔═══  𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐂𝐀𝐍𝐂𝐄𝐋𝐋𝐄𝐃  ═══╗\n"
                f"║\n"
                f"║ 📌 Stopped at Message ID: `{msg_id}`\n"
                f"║ 📤 Messages Forwarded: `{count}` out of `{total}`\n"
                f"╚═════════════════════╝"
            )
            break
        # Pause check
        while pause_flags.get(user_id, False):
            await status.edit_text("⏸ Forwarding paused...")
            await asyncio.sleep(1)

        try:
            msg = await client.get_messages(start_chat, msg_id)
            if not msg or getattr(msg, "empty", False) or getattr(msg, "protected_content", False):
                failed += 1
                continue

            # FILTER CHECKS
            type_check = (
                (msg.text and not filters_dict.get("text", True)) or
                (msg.photo and not filters_dict.get("photo", True)) or
                (msg.video and not filters_dict.get("video", True)) or
                (msg.audio and not filters_dict.get("audio", True)) or
                (msg.document and not filters_dict.get("document", True)) or
                (msg.animation and not filters_dict.get("animation", True)) or
                (msg.sticker and not filters_dict.get("sticker", True)) or
                (msg.poll and not filters_dict.get("poll", True))
            )
            if type_check:
                continue

            caption = msg.caption or msg.text or ""
            new_caption = caption

            # APPLY CAPTION SETTINGS
            if settings.get("replace_words"):
                for pair in settings.get("replace_word_pairs", []):
                    new_caption = new_caption.replace(pair[0], pair[1])

            if settings.get("delete_words"):
                for word in settings.get("delete_words_list", []):
                    new_caption = new_caption.replace(word, "")

            if settings.get("remove_links"):
                new_caption = re.sub(r"https?://\S+", "", new_caption)

            if settings.get("replace_links"):
                new_caption = re.sub(r"https?://\S+", settings.get("replace_link_text", "[link]"), new_caption)

            if settings.get("remove_usernames"):
                new_caption = re.sub(r"@\w+", "", new_caption)

            if settings.get("replace_usernames"):
                new_caption = re.sub(r"@\w+", settings.get("replace_username_text", "@user"), new_caption)

            if new_caption != caption:
                await client.copy_message(target_chat, start_chat, msg_id, caption=new_caption)
            else:
                await msg.copy(target_chat)

            # Auto pin if enabled
            if settings.get("auto_pin") and msg.is_pinned:
                sent = await msg.copy(target_chat)
                await client.pin_chat_message(target_chat, sent.id)
                try:
                    await client.delete_messages(target_chat, sent.id + 1)
                except: pass

            count += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except RPCError:
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
        progress_bar = f"{'🟩' * int(percent // 10)}{'⬜' * (10 - int(percent // 10))}"
        elapsed_text = format_eta(int(elapsed))

        try:
            await status.edit(
                f"╔══ 🎯 𝐒𝐎𝐔𝐑𝐂𝐄 / 𝐓𝐀𝐑𝐆𝐄𝐓 𝐈𝐍𝐅𝐎 🎯 ══╗\n"
                f"┃\n"
                f"┃ 📤 From  : `{source_chat.title}`\n"
                f"┃ 🎯 To  :  `{target.title}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═  📦 𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 📦  ═╗\n"
                f"┃\n"
                f"┃ 📊 Progress  : `{count + failed}/{total}` ({percent:.2f}%)\n"
                f"┃ 📌 Remaining  : `{remaining}`\n"
                f"┃ ▓ {progress_bar}\n"
                f"╚═════════════════════════╝\n\n"
                f"╔═  📈 𝐏𝐄𝐑𝐅𝐎𝐑𝐌𝐀𝐍𝐂𝐄 𝐌𝐀𝐓𝐑𝐈𝐂𝐒  📈  ═╗\n"
                f"┃\n"
                f"┃ ✅ Success  : `{count}`\n"
                f"┃ ❌ Deleted  :  `{failed}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔════ ⏱️ 𝐓𝐈𝐌𝐈𝐍𝐆 𝐃𝐄𝐓𝐀𝐈𝐋𝐒 ⏱️ ═════╗\n"
                f"┃\n"
                f"┃ ⌛ Elapsed  : `{elapsed_text}`\n"
                f"┃ ⏳ ETA  :  `{eta}`\n"
                f"╚═════════════════════════╝\n\n",
                reply_markup=control_buttons(user_id)
            )
        except Exception as e:
            print(f"Progress update error: {e}")

        await asyncio.sleep(0.5)

    time_taken = format_eta(time.time() - start_time)
    await status.edit(
        f"╔═  ✅ 𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄𝐃 ✅  ═╗\n"
        f"┃\n"
        f"┃ 📤 From  : `{source_chat.title}`\n"
        f"┃ 🎯 To  : `{target.title}`\n"
        f"┃ ✅ Success  : `{count}`\n"
        f"┃ ❌ Deleted  : `{failed}`\n"
        f"┃ 📊 Total  : `{total}`\n"
        f"┃ ⏱️ Time  : `{time_taken}`\n"
        f"╚═════════════════════════╝"
    )


@app.on_callback_query(filters.regex(r"^(pause|resume|cancel):"))
async def handle_controls(client, query):
    action, uid = query.data.split(":")
    uid = int(uid)

    if query.from_user.id != uid:
        return await query.answer("⚠️ Not your session", show_alert=True)

    if action == "pause":
        pause_flags[uid] = True
        await query.answer("⏸ Paused")
        await query.message.edit_reply_markup(control_buttons(uid))

    elif action == "resume":
        pause_flags[uid] = False
        await query.answer("▶️ Resumed")
        await query.message.edit_reply_markup(control_buttons(uid))

    elif action == "cancel":
        cancel_flags[uid] = True
        pause_flags[uid] = False
        await query.answer("❌ Cancelled")
        await query.message.edit_reply_markup(None)


@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    cancel_flags[message.from_user.id] = True
    await message.reply(
        f"╔═══ 🛑 𝐂𝐀𝐍𝐂𝐄𝐋 𝐑𝐄𝐐𝐔𝐄𝐒𝐓𝐄𝐃 🛑 ═══╗\n"
        f"┃\n"
        f"┃ ⚙️ Attempting to halt forwarding...\n"
        f"┃ ⏳ Please wait a moment.\n"
        f"╚═════════════════════════╝"
    )


app.run()
