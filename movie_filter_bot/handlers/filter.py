from pyrogram import filters
from pyrogram.types import Message
from config import FILE_CHANNELS
from bot import app
from utils.logger import log_event
from utils.caption import format_caption

@app.on_message(filters.text & ~filters.command(["start"]))
async def filter_handler(client, message: Message):
    query = message.text.lower()
    results = []

    for channel_id in FILE_CHANNELS:
        async for msg in client.search_messages(channel_id, query=query, filter="document"):
            results.append(msg)

    if not results:
        await message.reply_text("❌ No matching movies found.")
        await log_event(f"❌ No results for '{query}' by [{message.from_user.id}](tg://user?id={message.from_user.id})")
        return

    await log_event(f"🔍 Query: '{query}' by [{message.from_user.id}](tg://user?id={message.from_user.id})")

    for msg in results[:5]:  # Limit to 5 results
        caption = format_caption(msg.document.file_name, msg.document.file_size)
        await msg.copy(chat_id=message.chat.id, caption=caption)