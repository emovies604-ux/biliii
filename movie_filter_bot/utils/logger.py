from bot import app
from config import LOG_CHANNEL_ID

async def log_event(text):
    try:
        await app.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Logging failed: {e}")