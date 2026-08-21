import os

# Render等の環境変数からBOTトークンを取得
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# データベースファイル名
DB_FILE = "bot_database.db"

# 自動削除のデフォルト保持日数（未設定の場合）
DEFAULT_DELETE_AFTER_DAYS = 7
