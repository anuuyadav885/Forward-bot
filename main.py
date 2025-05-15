import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from pyrogram.errors import FloodWait, PeerIdInvalid, RPCError
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URI

# Initialize bot and MongoDB
app = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["forward_bot"]
users = db["users"]

# Store cancel flags per user
cancel_flags = {}

@app.on_message(filters.command("start"))
async def start_cmd(_, msg: Message):
    text = """
👋 **Welcome to Advanced Telegram Forward Bot!**

Use:
/settarget <target_chat_id>
/forward <source_chat_id> <start_msg_id> <end_msg_id>
/cancel to cancel ongoing forwarding
    """
    await msg.reply(text)

@app.on_message(filters.command("settarget") & filters.private)
async def set_target(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /settarget <target_chat_id>")
    target_chat = message.command[1]
    users.update_one({"user_id": message.from_user.id}, {"$set": {"target_chat": target_chat}}, upsert=True)
    await message.reply(f"✅ Target chat set to `{target_chat}`")

@app.on_message(filters.command("forward") & filters.private)
async def forward_range(client, message):
    args = message.command
    if len(args) != 4:
        return await message.reply("Usage: /forward <source_chat_id> <start_msg_id> <end_msg_id>")

    user_id = message.from_user.id
    cancel_flags[user_id] = False

    source_chat, start_id, end_id = args[1], int(args[2]), int(args[3])
    user = users.find_one({"user_id": user_id})
    if not user or "target_chat" not in user:
        return await message.reply("❗ Please set target first using /settarget")

    target_chat = user["target_chat"]
    total = end_id - start_id + 1
    count = 0

    try:
        await client.get_chat(source_chat)
    except PeerIdInvalid:
        return await message.reply("❌ Bot hasn't interacted with the source chat yet.\nPlease forward one message manually using the bot.")

    status = await message.reply(f"🔄 Forwarding started...\n0/{total} messages.")

    for msg_id in range(start_id, end_id + 1):
        if cancel_flags.get(user_id):
            await status.edit(f"🚫 Cancelled at message {msg_id}. Forwarded {count}/{total}.")
            cancel_flags[user_id] = False
            return

        try:
            msg = await client.get_messages(source_chat, msg_id)
            if msg and not getattr(msg, "empty", False) and not getattr(msg, "protected_content", False):
                await msg.copy(target_chat)
                count += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except PeerIdInvalid:
            await status.edit("❌ Error: Peer ID is invalid. Make sure the bot is added and has access.")
            return
        except RPCError as e:
            print(f"Error at msg_id {msg_id}: {e}")
            continue

        await asyncio.sleep(0.5)

        if count % 20 == 0 or msg_id == end_id:
            try:
                await status.edit(f"🔄 Forwarding...\n{count}/{total} done.")
            except:
                pass

    await status.edit(f"✅ Completed.\nForwarded {count}/{total} messages.")

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_forwarding(client, message):
    cancel_flags[message.from_user.id] = True
    await message.reply("🛑 Cancelling... Please wait.")

app.run()
