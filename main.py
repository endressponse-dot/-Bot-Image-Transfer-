import os
import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime, timedelta, timezone

# --- 設定項目 ---
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_FORUM_IDS = [1539156107396780132,1539156837469921330,1539223666720509962]  # コピー元フォーラムのID
DEST_CHANNEL_ID = 1539155223925358663     # 転送先(#image-stream)のID
DELETE_AFTER_DAYS = 7                   # 自動削除までの日数

# --- Botの初期化 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    clean_old_messages.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel = message.channel
    parent_id = getattr(channel, "parent_id", None)
    
    if channel.id in SOURCE_FORUM_IDS or parent_id in SOURCE_FORUM_IDS:
        image_attachments = [
            att for att in message.attachments 
            if att.content_type and att.content_type.startswith("image/")
        ]

        if image_attachments:
            dest_channel = bot.get_channel(DEST_CHANNEL_ID)
            if dest_channel:
                for att in image_attachments:
                    file = await att.to_file()
                    await dest_channel.send(
                        content=f"📷 **{message.author.display_name}** さんの投稿（{channel.name}より）",
                        file=file
                    )
                print(f"画像を転送しました: {message.id}")

@tasks.loop(hours=12)
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
                await asyncio.sleep(1)
            except Exception as e:
                print(f"削除エラー: {e}")

bot.run(BOT_TOKEN)
