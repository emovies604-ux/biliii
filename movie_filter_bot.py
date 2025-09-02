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

# Placeholders for your credentials - replace with actual values
API_ID = "27020363"  # e.g., 1234567
API_HASH = "900133bfe09ce6ef78885e3599ba64ca"  # e.g., "abcdef1234567890"
BOT_TOKEN = "8334188484:AAFIJACJ0YPy9LhX3ONh4FztqX47mz7ZC3c"  # e.g., "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
MONGO_URI = "mongodb+srv://Billobb:Billobb@billobb.v67fmki.mongodb.net/?retryWrites=true&w=majority&appName=billobb"  # e.g., "mongodb+srv://user:pass@cluster.mongodb.net/dbname"
LOG_CHANNEL = "-1002967483523"  # e.g., -1001234567890 or "@logchannel"
FILES_CHANNEL = "-1002789851054"  # e.g., -1009876543210 or "@fileschannel"

# Optional: Admin user ID for restricted commands
ADMIN_ID = 1222287481  # Replace with your Telegram user ID

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
        await app.send_message(LOG_CHANNEL, message)
    except Exception as e:
        logger.error(f"Failed to send log: {e}")

# Parse movie name from caption (simple: take the whole caption or extract title)
def parse_movie_name(caption: str) -> str:
    if not caption:
        return None
    # Simple parsing: assume caption is movie name, optionally with year like "Movie Name (2023)"
    match = re.match(r"^(.*?)(?:\s*\(\d{4}\))?$", caption.strip())
    return match.group(1).strip().lower() if match else caption.strip().lower()

# Handler for new messages in files channel (to index new movies)
@app.on_message(filters.chat(FILES_CHANNEL) & (filters.document | filters.video))
async def index_movie(client: Client, message: Message):
    if not message.caption:
        await send_log(f"File received without caption in files channel: {message.id}")
        return
    
    movie_name = parse_movie_name(message.caption)
    if not movie_name:
        await send_log(f"Invalid caption for file: {message.id}")
        return
    
    # Store in DB: upsert to avoid duplicates
    movies_collection.update_one(
        {"name": movie_name},
        {"$set": {"message_id": message.id, "channel_id": FILES_CHANNEL}},
        upsert=True
    )
    await send_log(f"Indexed new movie: {movie_name} (msg_id: {message.id})")
    logger.info(f"Indexed: {movie_name}")

# Handler for user queries (in private or group chats)
@app.on_message(filters.text & ~filters.chat([LOG_CHANNEL, FILES_CHANNEL]) & ~filters.bot)
async def handle_query(client: Client, message: Message):
    query = message.text.strip().lower()
    
    # Search in DB (simple exact match or partial)
    results = list(movies_collection.find({"name": {"$regex": query, "$options": "i"}}).limit(10))
    
    if not results:
        await message.reply_text("No movies found matching your query.")
        return
    
    # Prepare reply with buttons or list
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
        # Multiple results: show buttons
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

# Admin command to re-index all files in channel (careful, can be slow for large channels)
@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def reindex(client: Client, message: Message):
    await message.reply_text("Starting re-indexing...")
    count = 0
    async for msg in client.iter_messages(FILES_CHANNEL, limit=0):  # limit=0 for all
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


# ... (rest of your existing code remains unchanged) ...

# Bot start
async def main():
    await app.start()
    await send_log("Bot started successfully.")
    logger.info("Bot started")
    # Keep the bot running using asyncio.Event
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()  # Wait indefinitely until interrupted
    finally:
        await app.stop()
        await send_log("Bot stopped.")
        logger.info("Bot stopped")

if __name__ == "__main__":
    app.run(main())

