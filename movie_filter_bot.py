import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import pymongo
from pymongo import MongoClient
import re
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual credentials
API_ID = "your_api_id"
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"
MONGO_URI = "your_mongo_uri"
LOG_CHANNEL = -1001234567890  # Replace with actual channel ID
FILES_CHANNEL = -1009876543210  # Replace with actual channel ID
ADMIN_ID = 123456789  # Replace with your Telegram user ID

# Connect to MongoDB
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["movie_bot_db"]
    movies_collection = db["movies"]
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    exit(1)

# Create Pyrogram Client
app = Client("movie_filter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Function to send log messages
async def send_log(message: str):
    try:
        logger.info(f"Attempting to send log to {LOG_CHANNEL}")
        await app.send_message(LOG_CHANNEL, message)
    except Exception as e:
        logger.error(f"Failed to send log to {LOG_CHANNEL}: {e}")

# Parse movie name from caption
def parse_movie_name(caption: str) -> str:
    if not caption:
        return None
    match = re.match(r"^(.*?)(?:\s*\(\d{4}\))?$", caption.strip())
    return match.group(1).strip().lower() if match else caption.strip().lower()

# Handler for new messages in files channel
@app.on_message(filters.chat(FILES_CHANNEL) & (filters.document | filters.video))
async def index_movie(client: Client, message: Message):
    if not message.caption:
        await send_log(f"File received without caption in files channel: {message.id}")
        return
    
    movie_name = parse_movie_name(message.caption)
    if not movie_name:
        await send_log(f"Invalid caption for file: {message.id}")
        return
    
    movies_collection.update_one(
        {"name": movie_name},
        {"$set": {"message_id": message.id, "channel_id": FILES_CHANNEL}},
        upsert=True
    )
    await send_log(f"Indexed new movie: {movie_name} (msg_id: {message.id})")
    logger.info(f"Indexed: {movie_name}")

# Handler for user queries
@app.on_message(filters.text & ~filters.chat([LOG_CHANNEL, FILES_CHANNEL]) & ~filters.bot)
async def handle_query(client: Client, message: Message):
    query = message.text.strip().lower()
    
    results = list(movies_collection.find({"name": {"$regex": query, "$options": "i"}}).limit(10))
    
    if not results:
        await message.reply_text("No movies found matching your query.")
        return
    
    if len(results) == 1:
        movie = results[0]
        try:
            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=movie["channel_id"],
                message_id=movie["message_id"],
                reply_to_message_id=message.id
            )
            await send_log(f"Sent movie '{movie['name']}' to user {message.from_user.id}")
        except Exception as e:
            await message.reply_text("Error sending the movie file.")
            await send_log(f"Error sending movie: {e}")
    else:
        buttons = []
        for movie in results:
            buttons.append([InlineKeyboardButton(movie['name'].title(), callback_data=f"movie_{movie['_id']}")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text("Multiple movies found. Select one:", reply_markup=reply_markup)

# Callback handler for multiple results
@app.on_callback_query(filters.regex(r"^movie_(.*)$"))
async def handle_callback(client: Client, callback_query):
    movie_id = callback_query.matches[0].group(1)
    movie = movies_collection.find_one({"_id": movie_id})
    
    if not movie:
        await callback_query.answer("Movie not found.", show_alert=True)
        return
    
    try:
        await client.copy_message(
            chat_id=callback_query.message.chat.id,
            from_chat_id=movie["channel_id"],
            message_id=movie["message_id"],
            reply_to_message_id=callback_query.message.id
        )
        await callback_query.message.edit_text(f"Sent: {movie['name'].title()}")
        await send_log(f"Sent movie '{movie['name']}' via callback to user {callback_query.from_user.id}")
    except Exception as e:
        await callback_query.answer("Error sending the movie file.", show_alert=True)
        await send_log(f"Error sending movie via callback: {e}")

# Admin command to re-index files
@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def reindex(client: Client, message: Message):
    await message.reply_text("Starting re-indexing...")
    count = 0
    async for msg in client.iter_messages(FILES_CHANNEL, limit=0):
        if msg.document or msg.video:
            movie_name = parse_movie_name(msg.caption)
            if movie_name:
                movies_collection.update_one(
                    {"name": movie_name},
                    {"$set": {"message_id": msg.id, "channel_id": FILES_CHANNEL}},
                    upsert=True
                )
                count += 1
    await message.reply_text(f"Re-indexed {count} movies.")
    await send_log(f"Re-indexed {count} movies by admin.")

# Start command
@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply_text("Welcome to Movie Filter Bot! Send a movie name to search.")

# Bot start with peer resolution
async def main():
    await app.start()
    try:
        # Resolve channel IDs to ensure Telegram recognizes them
        for channel in [LOG_CHANNEL, FILES_CHANNEL]:
            try:
                await app.get_chat(channel)
                logger.info(f"Successfully resolved channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to resolve channel {channel}: {e}")
                await app.stop()
                exit(1)
        await send_log("Bot started successfully.")
        logger.info("Bot started")
        # Keep the bot running
        stop_event = asyncio.Event()
        await stop_event.wait()
    finally:
        await app.stop()
        await send_log("Bot stopped.")
        logger.info("Bot stopped")

if __name__ == "__main__":
    app.run(main())
