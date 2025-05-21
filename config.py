# config.py
from os import environ

API_ID = int(environ.get("API_ID", ""))
API_HASH = environ.get("API_HASH", "")
BOT_TOKEN = environ.get("BOT_TOKEN", "")
MONGO_URI = environ.get("MONGO_URI", "")
OWNER_ID = int(environ.get("OWNER_ID", ""))
OWNER_LOG_GROUP = environ.get("OWNER_LOG_GROUP", "-1002512261473")
FORCE_CHANNEL = environ.get("FORCE_CHANNEL", "-1002458623455")
