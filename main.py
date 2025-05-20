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
import math
from pyromod import listen
from pyrogram import enums 
from Crypto.Cipher import AES
from pymongo import MongoClient
from aiohttp import ClientSession    
from pyrogram.types import Message, BotCommand  
from pyrogram import Client, filters
from base64 import b64encode, b64decode
from pyrogram.errors import FloodWait, PeerIdInvalid, RPCError
from pyrogram.types import User, Message        
from pyrogram.types.messages_and_media import message
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URI, OWNER_ID
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid

#========================= Initaited bot ===========================
# Initialize bot and MongoDB
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["forward_bot"]
users = db["users"]
users_collection = db["busers"]
auth_col = db["auth_users"]
cancel_flags = {}

#======================= Set bot commands ========================
@app.on_message(filters.command("set") & filters.user(OWNER_ID))
async def set_bot_commands(client, message):
    commands = [
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("target", "🎯 Set target channel"),
        BotCommand("forward", "📤 Forward messages"),
        BotCommand("id", "🆔 Show your Telegram ID"),
        BotCommand("add", "➕ Add authorized user"),
        BotCommand("rem", "➖ Remove authorized user"),
        BotCommand("clear", "🗑️ Clear all authorized users"),
        BotCommand("users", "👥 List premium users"),
        BotCommand("filters", "🔍 Toggle media filters"),
        BotCommand("cancel", "🛑 Cancel forwarding"),
        BotCommand("targetinfo", "ℹ️ Show current target"),
        BotCommand("filtersinfo", "⚙️ Show current filters"),
        BotCommand("reset", "♻️ Reset filters & target"),
        BotCommand("broadcast", "📢 Broadcast a massege to users"),
    ]

    await client.set_bot_commands(commands)
    await message.reply("<blockquote>✅ Bot commands set successfully.</blockquote>")

#======================= Check premium users ====================
def is_authorized(user_id):
    return auth_col.find_one({"_id": user_id}) or user_id == OWNER_ID

#======================== Add user in premium =======================
@app.on_message(filters.command("add") & filters.user(OWNER_ID))
async def add_premium(_, m):
    if len(m.command) < 2:
        return await m.reply("<blockquote>⚠️ Usage: /add [user_id]</blockquote>")
    try:
        uid = int(m.command[1])
        if not auth_col.find_one({"_id": uid}):
            auth_col.insert_one({"_id": uid})
            await m.reply("<blockquote>✅ User Added Successsfully.</blockquote>")
        else:
            await m.reply("<blockquote>ℹ️ User Already Exists.</blockquote>")
    except:
        await m.reply("<blockquote>❌ Invalid ID format.</blockquote>")

#====================== Remove users from premium =========================
@app.on_message(filters.command("rem") & filters.user(OWNER_ID))
async def remove_user(_, m):
    if len(m.command) < 2:
        return await m.reply("<blockquote>⚠️ Usage: /rem [user_id]</blockquote>")
    try:
        uid = int(m.command[1])
        result = auth_col.delete_one({"_id": uid})
        await m.reply("<blockquote>✅ User Removed Successfully.</blockquote>" if result.deleted_count else "<blockquote>❌ User not found.</blockquote>")
    except:
        await m.reply("<blockquote>❌ Invalid ID format.</blockquote>")

#===================== Clear all Premium users =========================
@app.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_all_users(_, m):
    result = auth_col.delete_many({})
    await m.reply(f"<blockquote>✅ All users deleted.\nTotal removed: {result.deleted_count}</blockquote>")

#======================== Premium users info =====================
@app.on_message(filters.command("users") & filters.user(OWNER_ID))
async def show_users(_, m):
    users = list(auth_col.find())
    if not users:
        return await m.reply("<blockquote>🚫 No authorized users found.</blockquote>")
    user_list = "\n".join(str(u["_id"]) for u in users)
    await m.reply(f"<blockquote>👥 Authorized Users:</blockquote>\n\n{user_list}")

#========================== For broadcast ====================================
def add_user(user_id):
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

def remove_user(user_id):
    users_collection.delete_one({"_id": user_id})
    
def get_all_users():
    return [doc["_id"] for doc in users_collection.find()]

# Global store to keep track of broadcast requests
broadcast_requests = {}

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(bot, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast it.")

    # Save the message ID and user ID
    broadcast_requests[message.from_user.id] = {
        "chat_id": message.chat.id,
        "message_id": message.reply_to_message.id
    }

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_broadcast"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
        ]
    ])

    await message.reply_text(
        "Are you sure you want to broadcast this message?",
        reply_markup=buttons
    )


@app.on_callback_query(filters.regex("^(confirm_broadcast|cancel_broadcast)$"))
async def handle_broadcast_decision(bot, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data

    if user_id not in broadcast_requests:
        return await query.answer("No broadcast request found.", show_alert=True)

    data = broadcast_requests.pop(user_id)
    chat_id = data["chat_id"]
    message_id = data["message_id"]

    if action == "cancel_broadcast":
        await query.message.edit_text("❌ Broadcast canceled.")
        return

    await query.message.edit_text("📣 Broadcasting...")

    # Start broadcasting
    sent = 0
    failed = 0
    total = 0
    failed_users = []

    users = get_all_users()

    for uid in users:
        total += 1
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=chat_id,
                message_id=message_id
            )
            sent += 1
        except Exception as e:
            print(f"Failed to send to {uid}: {e}")
            failed += 1
            # Immediately delete the failed user from DB
            remove_user(uid)

    # Report
    report_text = (
        f"<blockquote>📢 <b>Broadcast Complete</b></blockquote>\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed to Send: {failed}\n"
        f"📊 Total Users: {total}"
    )
    await bot.send_message(chat_id, report_text)

#================= Reactiom & add users in database ======================
import random
VALID_EMOJIS = ["😂", "🔥", "🎉", "🥳", "💯", "😎", "😅", "🙏", "👏", "❤️",
                "🦁", "🐶", "🐼", "🐱", "👻", "🐻‍❄️", "☁️", "🐅", "⚡️", "🚀",
                "✨", "💥", "☠️", "🥂", "🍾", "🐠", "🦋"]

@app.on_message(filters.text, group=-1)
async def auto_react(bot, message):
    if message.edit_date or not message.from_user:
        return  # Skip edited messages or anonymous/channel messages
    add_user(message.from_user.id)  # ✅ Auto add user to DB
    for _ in range(5):  # Try up to 5 different emojis
        emoji = random.choice(VALID_EMOJIS)
        try:
            await message.react(emoji)
            break  # ✅ Success, exit loop
        except Exception as e:
            print(f"❌ Failed to react with {emoji}: {e}")
            continue  # Try another emoji

#=================== ID ============================
@app.on_message(filters.command("id"))
async def send_user_id(bot, message):
    user_id = message.from_user.id
    text = f"<blockquote>👤 Your Telegram ID is :</blockquote>\n\n{user_id}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Send to Owner", callback_data=f"send_id:{user_id}")]
    ])

    await message.reply_text(text, reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"send_id:(\d+)"))
async def handle_send_to_owner(bot, query):
    user_id = int(query.matches[0].group(1))

    await bot.send_message(
        OWNER_ID,
        f"📬 USER_ID : 👤 {user_id}\n\nCommand : `/add {user_id}`"
    )

    await query.answer("✅ Sent to owner!", show_alert=True)

#===================== Detect chat id from message link ===================
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

#================================ Start command to start bot ============================
image_list = [
    "https://www.pixelstalk.net/wp-content/uploads/2025/03/A-breathtaking-image-of-a-lion-roaring-proudly-atop-a-rocky-outcrop-with-dramatic-clouds-and-rays-of-sunlight-breaking-through-2.webp"
    ]
class Data:
    START = (
        "🌟 𝐇𝐞𝐲  {0} , 𝐖𝐄𝐋𝐂𝐎𝐌𝐄  !\n\n"
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
    user_id = msg.from_user.id
    if is_authorized(user_id):
        await start_message.edit_text(
            Data.START.format(msg.from_user.mention) +
            "<blockquote>👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐅𝐎𝐑𝐖𝐀𝐑𝐃 𝐁𝐎𝐓 👋</blockquote>\n\n"
            "Great! You are a premium member!\n\n"
            "<blockquote>📚 **Available Commands For This Bot**</blockquote>\n\n"
            "• /target – Set target via message link\n\n"
            "• /forward – Forward messages\n\n"
            "• /cancel – Cancel ongoing forwarding\n\n"
            "• /help – Check full working process\n\n"
            "<blockquote>🚀 **Use the bot to forward messages fast and easily!**</blockquote>\n",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/Dc5txt_bot")]
            ])
        )
    else:
        await asyncio.sleep(2)
        await start_message.edit_text(
           Data.START.format(msg.from_user.mention) +
            f"<blockquote>🛡️ Access Restricted</blockquote>\n\n"
            "This bot is restricted to premium users only.\n\n"
            "<blockquote>🔐 Features include:</blockquote>\n\n"
            "• Auto messages forwarding\n"
            "• Auto caption editing\n"
            "• Auto Pining & Media filters\n\n"
            "<blockquote>To request access, contact the admin below.</blockquote>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/Dc5txt_bot")]
            ])
        )
#================================ Set filters =============================
@app.on_message(filters.command("filters") & filters.private)
async def set_filters(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        return await message.reply("❌ You are not authorized.")

    users.update_one({"user_id": user_id}, {
        "$setOnInsert": {
            "filters": {
                "replace": {}, 
                "delete": [], 
                "types": {
                    "text": True,
                    "photo": True,
                    "video": True,
                    "document": True,
                    "audio": True,
                    "voice": True,
                    "sticker": True,
                    "poll": True,
                    "animation": True
                }
            },
            "auto_pin": False
        }
    }, upsert=True)

    user = users.find_one({"user_id": user_id})
    filters_data = user.get("filters", {})
    replace = filters_data.get("replace", {})
    delete = filters_data.get("delete", [])
    auto_pin = filters_data.get("auto_pin", False)
    types = filters_data.get("types", {})

    allowed_types = [
        "text", "photo", "video", "document", "audio",
        "voice", "sticker", "poll", "animation"
    ]
    type_status = "\n".join([
        f"▪️ {t.capitalize()}: {'✅' if types.get(t, False) else '❌'}"
        for t in allowed_types
    ])

    await message.reply(
        "<blockquote>**🔧 Current Filters :**</blockquote>\n\n"
        f"🔁 Replace: `{replace}`\n"
        f"❌ Delete: `{delete}`\n"
        f"📌 Auto Pin: `{auto_pin}`\n\n"
        f"<blockquote>Message Types:</blockquote>\n\n{type_status}\n\n"
        "<blockquote>**Send filters in one of these formats :**</blockquote>\n\n"
        "`type: <name> on/off` (e.g., `type: photo off`)\n"
        "`word1 => word2` to replace\n"
        "`delete: word` to delete word\n"
        "`auto_pin: true/false` to toggle auto pinning\n\n"
        "Type /done to finish.",
    )

    while True:
        try:
            response = await client.listen(message.chat.id, timeout=120)
        except asyncio.TimeoutError:
            return await message.reply("⏳ Timed out. Run /filters again.")

        text = response.text.strip()

        if text.lower() == "/done":
            return await message.reply("✅ Filters updated!")

        if text.lower().startswith("type:"):
            try:
                match = re.match(r"type:\s*(\w+)\s+(on|off|true|false|yes|no|1|0)", text.lower())
                if not match:
                    await message.reply("❌ Invalid format. Use: `type: photo on/off`")
                    continue
                type_name, value_raw = match.groups()
                allowed_types = [
                    "text", "photo", "video", "document", "audio", 
                    "voice", "sticker", "poll", "animation"
                ]
                if type_name not in allowed_types:
                    await message.reply(f"❌ Invalid type name: `{type_name}`\n✅ Allowed: {', '.join(allowed_types)}")
                    continue
                value = value_raw in ["on", "true", "yes", "1"]
                filters_data["types"][type_name] = value
                users.update_one({"user_id": user_id}, {"$set": {"filters.types": filters_data["types"]}})
                await message.reply(f"🔘 `{type_name}` set to `{value}`")
            except Exception as e:
                await message.reply(f"❌ Unexpected error occurred:\n`{e}`")

        elif "=>" in text:
            try:
                old, new = [t.strip() for t in text.split("=>", 1)]
                filters_data["replace"][old] = new
                users.update_one({"user_id": user_id}, {"$set": {"filters.replace": filters_data["replace"]}})
                await message.reply(f"🔁 Added replace: `{old}` => `{new}`")
            except Exception:
                await message.reply("❌ Invalid replace format.")

        elif text.lower().startswith("delete:"):
            word = text.split("delete:", 1)[1].strip()
            if word not in filters_data["delete"]:
                filters_data["delete"].append(word)
                users.update_one({"user_id": user_id}, {"$set": {"filters.delete": filters_data["delete"]}})
            await message.reply(f"❌ Will delete: `{word}`")

        elif text.lower().startswith("auto_pin:"):
            val_raw = text.split("auto_pin:", 1)[1].strip().lower()
            val = val_raw in ["true", "yes", "1"]
            users.update_one({"user_id": user_id}, {"$set": {"filters.auto_pin": val}})
            await message.reply(f"📌 Auto pin set to: `{val}`")

        else:
            await message.reply("❌ Invalid format. Try again or type /done to finish.")

#============================== Filter Information ==========================
@app.on_message(filters.command("filtersinfo") & filters.private)
async def filters_info(client, message):
    user_id = message.from_user.id
    user = users.find_one({"user_id": user_id})
    if not user:
        return await message.reply("❌ No filters found.")
    filters_data = user.get("filters", {})
    replace = filters_data.get("replace", {})
    delete = filters_data.get("delete", [])
    types = filters_data.get("types", {})
    auto_pin = filters_data.get("auto_pin", False)

    allowed_types = [
        "text", "photo", "video", "document", "audio",
        "voice", "sticker", "poll", "animation"
    ]
    type_status = "\n".join([
        f"▪️ {t.capitalize()}: {'✅' if types.get(t, False) else '❌'}"
        for t in allowed_types
    ])
    await message.reply(
        "<blockquote>🧰 Current Filter Settings:</blockquote>\n\n"
        f"🔁 Replace: {replace}\n"
        f"❌ Delete: {delete}\n"
        f"📌 Auto Pin: {auto_pin}\n\n"
        f"<blockquote>Message Types:</blockquote>\n{type_status}"
    )
#============================= Reset filters ====================================
@app.on_message(filters.command("reset") & filters.private)
async def reset_selected_settings(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "target_chat": None,
                "filters.replace": {},
                "filters.delete": [],
                "auto_pin": False
            }
        },
        upsert=True
    )

    await message.reply(
        "<blockquote>♻️ <b>Settings Reset Successfully:</b></blockquote>\n\n"
        "• 🎯 Target Channel  :  Cleared\n"
        "• 🔁 Replace Words  :  Cleared\n"
        "• ❌ Delete Words  :  Cleared\n"
        "• 📌 Auto Pin  :  Disabled"
    )
#=============================== Set target chat ==================================
@app.on_message(filters.command("target") & filters.private)
async def set_target(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
    await message.reply("<blockquote>📩 Send a **message link** from the **target channel**</blockquote>")
    try:
        link_msg = await client.listen(message.chat.id, timeout=120)
        link = link_msg.text.strip()
        chat_id, _ = extract_ids_from_link(link)
        if not chat_id:
            return await message.reply("<blockquote>❌ Invalid link</blockquote>")
        users.update_one({"user_id": message.from_user.id}, {"$set": {"target_chat": chat_id}}, upsert=True)
        await message.reply(f"<blockquote>✅ Target set to `{chat_id}`</blockquote>")
    except asyncio.TimeoutError:
        await message.reply("<blockquote>⏰ Timed out. Please try again</blockquote>")
        
#================================ Information of target chat =========================
@app.on_message(filters.command("targetinfo") & filters.private)
async def target_info(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
    user = users.find_one({"user_id": user_id})
    target_chat_id = user.get("target_chat") if user else None

    if not target_chat_id:
        return await message.reply("<blockquote>❌ No target is currently set. Use /target to set one.</blockquote>")

    try:
        chat = await client.get_chat(target_chat_id)
        await message.reply(
            f"<blockquote>🎯 Current Target :</blockquote>\n\n"
            f"• Title : <b>{chat.title}</b>\n"
            f"• ID : <code>{target_chat_id}</code>"
        )
    except Exception:
        await message.reply(
            f"🎯 Current Target ID : <code>{target_chat_id}</code>\n\n"
            f"(⚠️ Bot may not have access to retrieve the title)"
        )
#========================= Start forward ==============================
@app.on_message(filters.command("forward") & filters.private)
async def forward_command(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
    cancel_flags[user_id] = False

    user = users.find_one({"user_id": user_id})
    target_chat = user.get("target_chat") if user else None
    if not target_chat:
        return await message.reply("<blockquote>❌ No target is set. Use /target to set one.</blockquote>")

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
        f"╔════ 𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐈𝐍𝐈𝐓𝐈𝐀𝐓𝐄𝐃 ════╗\n"
        f"┃\n"
        f"┃ 🗂 Source : `{source_chat.title}`\n"
        f"┃ 📤 Target : `{target.title}`\n"
        f"╚══════════════════════════╝"
    )


    for msg_id in range(start_id, end_id + 1):
        if cancel_flags.get(user_id):
            await status.edit(
                f"╔═══ 𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐂𝐀𝐍𝐂𝐄𝐋𝐋𝐄𝐃 ═══╗\n"
                f"┃\n"
                f"┃ 📌 Stopped at Message ID: `{msg_id}`\n"
                f"┃ 📤 Messages Forwarded: `{count}` out of `{total}`\n"
                f"╚═════════════════════════╝\n\n"
            )
            cancel_flags[user_id] = False
            return

        try:
            msg = await client.get_messages(start_chat, msg_id)
            if msg and not getattr(msg, "empty", False) and not getattr(msg, "protected_content", False):
                caption = msg.caption
                user_data = users.find_one({"user_id": user_id})
                filters_data = user_data.get("filters", {})
                types = filters_data.get("types", {})
                allowed = (
                    (msg.text and types.get("text")) or
                    (msg.photo and types.get("photo")) or
                    (msg.video and types.get("video")) or
                    (msg.document and types.get("document")) or
                    (msg.audio and types.get("audio")) or
                    (msg.voice and types.get("voice")) or
                    (msg.sticker and types.get("sticker")) or
                    (msg.poll and types.get("poll")) or
                    (msg.animation and types.get("animation"))
                )
                if not allowed:
                    failed += 1
                    continue

                auto_pin = filters_data.get("auto_pin", False)

                if caption:
                    for old, new in filters_data.get("replace", {}).items():
                        caption = caption.replace(old, new)

                    for word in filters_data.get("delete", []):
                        caption = caption.replace(word, "")

                copied = await msg.copy(
                    target_chat,
                    caption=caption if caption else None,
                    caption_entities=msg.caption_entities if caption else None
                )
                if auto_pin:
                    try:
                        pinned_msg_id = None
                        source_chat = await client.get_chat(msg.chat.id)
                        if source_chat.pinned_message:
                            pinned_msg_id = source_chat.pinned_message.id
                        if pinned_msg_id == msg.id:
                            await asyncio.sleep(1)
                            await client.pin_chat_message(target_chat, copied.id)
                            await asyncio.sleep(0.5)
                            try:
                                await client.delete_messages(target_chat, copied.id + 1)
                            except:
                                pass
                    except Exception as e:
                        print(f"[AutoPin Error] {e}")
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
        progress_bar = f"{'⚫' * int(percent // 10)}{'⚪' * (10 - int(percent // 10))}"
        elapsed_text = format_eta(int(elapsed))
        
        try:
            current_status = "🟢 Forwarding"
            if isinstance(e, FloodWait):
                current_status = f"⏳ FloodWait: {e.value}s"
                
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
                f"╔═  📈 𝐏𝐄𝐑𝐅𝐎𝐑𝐌𝐀𝐍𝐂𝐄 𝐌𝐀𝐓𝐑𝐈𝐂𝐒 📈  ═╗\n"
                f"┃\n"
                f"┃ ✅ Success  : `{count}`\n"
                f"┃ ❌ Deleted  :  `{failed}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔════ ⏱️ 𝐓𝐈𝐌𝐈𝐍𝐆 𝐃𝐄𝐓𝐀𝐈𝐋𝐒 ⏱️ ═════╗\n"
                f"┃\n"
                f"┃ ⌛ Elapsed  : `{elapsed_text}`\n"
                f"┃ ⏳ ETA  :  `{eta}`\n"
                f"╚═════════════════════════╝\n\n"
                f"╔════ 🔄 𝐂𝐔𝐑𝐑𝐄𝐍𝐓 𝐒𝐓𝐀𝐓𝐔𝐒 🔄 ════╗\n"
                f"┃\n"
                f"┃ 💬 Status  : `{current_status}`\n"
                f"┃ ⚡ Speed  : `{(count + failed)/elapsed:.2f} msg/sec`\n"
                f"╚═════════════════════════╝"
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
        f"╚══════════════════════════╝"
    )
#================ Cancel running process ======================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
    cancel_flags[message.from_user.id] = True
    await message.reply(
        f"╔═══ 🛑 𝐂𝐀𝐍𝐂𝐄𝐋 𝐑𝐄𝐐𝐔𝐄𝐒𝐓𝐄𝐃 🛑 ═══╗\n"
        f"┃\n"
        f"┃ ⚙️ Attempting to halt forwarding...\n"
        f"┃ ⏳ Please wait a moment.\n"
        f"╚═════════════════════════╝"
    )
#========= Start bot =============
app.run()
