import os

# 環境変数からトークンを取得（なければ空文字）
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# データベースファイルパス
DB_FILE = os.getenv("DB_FILE", "bot_database.db")

# デフォルトの保持日数
DEFAULT_DELETE_AFTER_DAYS = int(os.getenv("DEFAULT_DELETE_AFTER_DAYS", "7"))
