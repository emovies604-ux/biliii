from pyrogram import filters
from pyrogram.types import Message
from bot import app
from utils.logger import log_event

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await message.reply_text("🎬 Welcome to Movie Filter Bot!\nSend me a movie name to search.")
    await log_event(f"👤 User [{message.from_user.id}](tg://user?id={message.from_user.id}) started the bot.")