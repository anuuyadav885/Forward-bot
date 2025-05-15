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
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URI, OWNER_ID
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid

# Initialize bot and MongoDB
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["forward_bot"]
users = db["users"]
auth_col = db["auth_users"]
cancel_flags = {}

def is_authorized(user_id):
    return auth_col.find_one({"_id": user_id}) or user_id == OWNER_ID

@app.on_message(filters.command("add") & filters.user(OWNER_ID))
async def add_user(_, m):
    if len(m.command) < 2:
        return await m.reply("⚠️ Usage: /add <user_id>")
    try:
        uid = int(m.command[1])
        if not auth_col.find_one({"_id": uid}):
            auth_col.insert_one({"_id": uid})
            await m.reply("✅ User added.")
        else:
            await m.reply("ℹ️ User already exists.")
    except:
        await m.reply("❌ Invalid ID format.")

@app.on_message(filters.command("rem") & filters.user(OWNER_ID))
async def remove_user(_, m):
    if len(m.command) < 2:
        return await m.reply("⚠️ Usage: /rem <user_id>")
    try:
        uid = int(m.command[1])
        result = auth_col.delete_one({"_id": uid})
        await m.reply("✅ User removed." if result.deleted_count else "❌ User not found.")
    except:
        await m.reply("❌ Invalid ID format.")
        
@app.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_all_users(_, m):
    result = auth_col.delete_many({})
    await m.reply(f"✅ All users deleted.\nTotal removed: {result.deleted_count}")

@app.on_message(filters.command("users") & filters.user(OWNER_ID))
async def show_users(_, m):
    users = list(auth_col.find())
    if not users:
        return await m.reply("🚫 No authorized users.")
    user_list = "\n".join(str(u["_id"]) for u in users)
    await m.reply(f"👥 Authorized Users:\n\n{user_list}")

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
        "<blockquote>👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐅𝐎𝐑𝐖𝐀𝐑𝐃 𝐁𝐎𝐓 👋</blockquote>\n\n"
        "📚 **Available Commands  :**\n\n"
        "• /target – Set target via message link\n"
        "• /forward – Forward messages via message links\n"
        "• /cancel – Cancel ongoing forwarding\n\n"
        "• /filters – Edit caption in forwarding\n\n"
        "🚀 *Use the bot to forward messages fast and easily!* 🌟\n"
    )
@app.on_message(filters.command("filters") & filters.private)
async def set_filters(client, message):
    user_id = message.from_user.id
    users.update_one({"user_id": user_id}, {"$setOnInsert": {"filters": {}}}, upsert=True)
    filters_data = users.find_one({"user_id": user_id}).get("filters", {})

    replace = filters_data.get("replace", {})
    delete = filters_data.get("delete", [])
    remove_links = filters_data.get("remove_links", False)

    await message.reply(
        "**🔧 Current Filters:**\n"
        f"🔁 Replace: `{replace}`\n"
        f"❌ Delete: `{delete}`\n"
        f"🔗 Remove Links: `{remove_links}`\n\n"
        "**Send filters in one of these formats:**\n"
        "`word1 => word2` to replace\n"
        "`delete: word` to delete word\n"
        "`remove_links: true/false` to toggle link removal\n\n"
        "Type `/done` to finish.",
    )

    while True:
        try:
            response = await client.listen(message.chat.id, timeout=120)
        except asyncio.TimeoutError:
            return await message.reply("⏳ Timed out. Run /filters again.")
        
        text = response.text.strip()

        if text.lower() == "/done":
            return await message.reply("✅ Filters updated!")

        if "=>" in text:
            old, new = [t.strip() for t in text.split("=>", 1)]
            replace[old] = new
            users.update_one({"user_id": user_id}, {"$set": {"filters.replace": replace}})
            await message.reply(f"🔁 Added replace: `{old}` => `{new}`")

        elif text.lower().startswith("delete:"):
            word = text.split("delete:", 1)[1].strip()
            if word not in delete:
                delete.append(word)
                users.update_one({"user_id": user_id}, {"$set": {"filters.delete": delete}})
            await message.reply(f"❌ Will delete: `{word}`")

        elif text.lower().startswith("remove_links:"):
            val = text.split("remove_links:", 1)[1].strip().lower() in ["true", "yes", "1"]
            users.update_one({"user_id": user_id}, {"$set": {"filters.remove_links": val}})
            await message.reply(f"🔗 Remove links set to: `{val}`")

        else:
            await message.reply("❌ Invalid format. Please try again.")


@app.on_message(filters.command("target") & filters.private)
async def set_target(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
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
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
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
        f"╔════ 𝐅𝐎𝐑𝐖𝐀𝐑𝐃𝐈𝐍𝐆 𝐈𝐍𝐈𝐓𝐈𝐀𝐓𝐄𝐃 ════╗\n"
        f"┃\n"
        f"┃ 🗂 Source : `{source_chat.title}`\n"
        f"┃ 📤 Target : `{target.title}`\n"
        f"╚═════════════════════════╝"
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

                if caption:
                    for old, new in filters_data.get("replace", {}).items():
                        caption = caption.replace(old, new)

                    for word in filters_data.get("delete", []):
                        caption = caption.replace(word, "")

                    if filters_data.get("remove_links", False):
                        caption = re.sub(r'https?://\S+', '', caption)

                await msg.copy(
                    target_chat,
                    caption=caption if caption else None,
                    caption_entities=msg.caption_entities if caption else None
                )
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
                f"╚═════════════════════════╝\n\n"
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

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [꧁ 𝐉𝐨𝐡𝐧 𝐖𝐢𝐜𝐤 ꧂](https://t.me/Dc5txt_bot) !")
        return
    cancel_flags[message.from_user.id] = True
    await message.reply(
        f"╔═══ 🛑 𝐂𝐀𝐍𝐂𝐄𝐋 𝐑𝐄𝐐𝐔𝐄𝐒𝐓𝐄𝐃 🛑 ═══╗\n"
        f"┃\n"
        f"┃ ⚙️ Attempting to halt forwarding...\n"
        f"┃ ⏳ Please wait a moment.\n"
        f"╚═════════════════════════╝"
    )

app.run()
