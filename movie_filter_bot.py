import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message
import pymongo
from pymongo import MongoClient

# Replace these with your actual values
API_ID = 27020363  # Your API ID
API_HASH = "900133bfe09ce6ef78885e3599ba64ca"  # Your API Hash
BOT_TOKEN = "8334188484:AAFIJACJ0YPy9LhX3ONh4FztqX47mz7ZC3c"  # Your Bot Token from BotFather
MONGO_URI = "mongodb+srv://Billobb:Billobb@billobb.v67fmki.mongodb.net/?retryWrites=true&w=majority&appName=billobb"  # Your MongoDB connection string
DB_NAME = "movie_bot_db"  # Database name
COLLECTION_NAME = "movies"  # Collection name for storing movie data
LOG_CHANNEL_ID = -1002967483523  # ID of the log channel (include -100 for channels)
FILE_CHANNEL_ID = -1002789851054  # ID of the file storage channel (include -100 for channels)

# Initialize MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
movies_collection = db[COLLECTION_NAME]

# Initialize Pyrogram Client
app = Client(
    "movie_filter_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Handler for /start command in private chats
@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    await message.reply_text("Welcome to the Movie Filter Bot! Send me a movie name to search for it.")

# Handler for text messages in private chats (user searches)
@app.on_message(filters.private & filters.text)
async def search_handler(client: Client, message: Message):
    query = message.text.strip()
    if not query:
        return

    # Search in MongoDB with case-insensitive regex
    results = list(movies_collection.find({"name": {"$regex": query, "$options": "i"}}).limit(10))  # Limit to 10 results

    if not results:
        await message.reply_text(f"No movies found matching '{query}'.")
        return

    # If multiple results, list them with options; for simplicity, send all files
    if len(results) == 1:
        movie = results[0]
        await message.reply_document(
            document=movie["file_id"],
            caption=movie["name"]
        )
    else:
        response = f"Found {len(results)} movies matching '{query}':\n\n"
        for idx, movie in enumerate(results, 1):
            response += f"{idx}. {movie['name']}\n"
        await message.reply_text(response)
        # Optionally, send each file one by one
        for movie in results:
            await message.reply_document(
                document=movie["file_id"],
                caption=movie["name"]
            )

# Handler for new documents in the file channel (auto-indexing)
@app.on_message(filters.chat(FILE_CHANNEL_ID) & filters.document)
async def index_handler(client: Client, message: Message):
    if not message.caption:
        return  # Skip if no caption (movie name)

    name = message.caption.strip()
    file_id = message.document.file_id

    # Check if already exists to avoid duplicates
    if movies_collection.find_one({"file_id": file_id}):
        return

    # Insert into DB
    movies_collection.insert_one({"name": name, "file_id": file_id})

    # Log to log channel
    await client.send_message(LOG_CHANNEL_ID, f"Indexed new movie: {name} (File ID: {file_id})")

# Optional: Admin command to manually index all files in the channel (use with caution, can be slow for large channels)
@app.on_message(filters.private & filters.command("index_all") & filters.user(123456789))  # Replace with your user ID for admin
async def index_all_handler(client: Client, message: Message):
    count = 0
    async for msg in client.iter_messages(FILE_CHANNEL_ID, filter="document"):
        if msg.document and msg.caption:
            name = msg.caption.strip()
            file_id = msg.document.file_id
            if not movies_collection.find_one({"file_id": file_id}):
                movies_collection.insert_one({"name": name, "file_id": file_id})
                count += 1
    await message.reply_text(f"Indexed {count} new movies.")
    await client.send_message(LOG_CHANNEL_ID, f"Full index completed: {count} movies added.")

# Main function to run the bot
async def main():
    await app.start()
    await app.send_message(LOG_CHANNEL_ID, "Movie Filter Bot has started!")
    await idle()
    await app.send_message(LOG_CHANNEL_ID, "Movie Filter Bot is stopping.")
    await app.stop()

# Run the bot
if __name__ == "__main__":

    asyncio.run(main())
