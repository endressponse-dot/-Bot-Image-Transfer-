import os
import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime, timedelta, timezone

# --- 設定項目 ---
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_FORUM_IDS = [1539156107396780132,1539156837469921330,1539223666720509962] # コピー元フォーラムのID（カンマ区切りで複数指定可）
DEST_CHANNEL_ID = 1539155223925358663 # 転送先(#image-stream)のID
DELETE_AFTER_DAYS = 7 # 自動削除までの日数

# --- Botの初期化 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
print(f"Logged in as {bot.user.name}")
clean_old_messages.start() # 7日経過メッセージの自動削除タスクを開始

@bot.event
async def on_message(message):
# Bot自身の投稿は無視
if message.author.bot:
return

# フォーラムチャンネル（スレッド内部を含む）からの投稿か判定
channel = message.channel
parent_id = getattr(channel, "parent_id", None)

if channel.id in SOURCE_FORUM_IDS or parent_id in SOURCE_FORUM_IDS:
# 添付ファイル（画像）のチェック
image_attachments = [
att for att in message.attachments
if att.content_type and att.content_type.startswith("image/")
]

if image_attachments:
dest_channel = bot.get_channel(DEST_CHANNEL_ID)
if dest_channel:
for att in image_attachments:
# 転送先に画像（ファイル）を直接送信
file = await att.to_file()
await dest_channel.send(
content=f"📷 **{message.author.display_name}** さんの投稿（{channel.name}より）",
file=file
)
print(f"画像を転送しました: {message.id}")

# --- 7日以上前のメッセージを自動削除するバックグラウンドタスク ---
@tasks.loop(hours=12) # 12時間ごとにチェックを実行
async def clean_old_messages():
await bot.wait_until_ready()
dest_channel = bot.get_channel(DEST_CHANNEL_ID)
if not dest_channel:
return

now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=DELETE_AFTER_DAYS)

print("古いメッセージの削除チェックを実行中...")
async for message in dest_channel.history(limit=200):
if message.created_at < cutoff:
try:
await message.delete()
print(f"削除完了: {message.id}")
await asyncio.sleep(1) # API制限回避用の短いウェイト
except Exception as e:
print(f"削除エラー: {e}")

# コード内のID書き換え
# BOT_TOKEN = "..."
# SOURCE_FORUM_IDS = [...]
# DEST_CHANNEL_ID = ...

bot.run(BOT_TOKEN)
