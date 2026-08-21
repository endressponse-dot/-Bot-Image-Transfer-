import os

# Discord Bot Token（環境変数から取得、無ければ直接記述のフォールバック）
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# データベースファイル名
DB_FILE = "bot_config.db"

# 転送先メッセージの自動削除日数（デフォルト: 7日）
DELETE_AFTER_DAYS = 7