import os
import threading
from flask import Flask
import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime, timedelta, timezone

# --- Renderポート開放用のダミーWEBサーバー ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- Botの設定項目 ---
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DELETE_AFTER_DAYS = 7                   # 自動削除までの日数

# ★ 監視・転送ペアの設定
PAIRS = [
    {
        "name": "一般用ペア",
        "source_ids": [1539156107396780132,1539156837469921330,1539223666720509962],  # 一般用フォーラムのID
        "dest_id": 1539155223925358663        # 一般用転送先のID
    },
    {
        "name": "NSFW用ペア",
        "source_ids": [1539232843668922418,1539232990813618216,1539233039647899759],  # NSFW用フォーラムのID
        "dest_id": 1539233186771374100        # NSFW用転送先のID
    }
]

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

    for pair in PAIRS:
        source_ids = pair["source_ids"]
        dest_id = pair["dest_id"]

        if channel.id in source_ids or parent_id in source_ids:
            image_attachments = [
                att for att in message.attachments 
                if att.content_type and att.content_type.startswith("image/")
            ]

            if image_attachments:
                dest_channel = bot.get_channel(dest_id)
                if dest_channel:
                    jump_url = message.jump_url
                    
                    for att in image_attachments:
                        file = await att.to_file()
                        
                        # Embed（埋め込み）を作成
                        embed = discord.Embed(
                            title="🔗 元の投稿（スレッド）を開く",
                            url=jump_url,
                            description=f"📷 **{message.author.display_name}** さんの投稿（#{channel.name} より）",
                            color=discord.Color.blue()
                        )
                        # 画像をEmbed内にきれいにセット
                        embed.set_image(url=f"attachment://{file.filename}")

                        await dest_channel.send(
                            embed=embed,
                            file=file
                        )
                    print(f"[{pair['name']}] Embed形式で転送しました: {message.id}")
            break

@tasks.loop(hours=12)
async def clean_old_messages():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DELETE_AFTER_DAYS)

    for pair in PAIRS:
        dest_channel = bot.get_channel(pair["dest_id"])
        if not dest_channel:
            continue

        print(f"[{pair['name']}] 古いメッセージの削除チェックを実行中...")
        async for message in dest_channel.history(limit=200):
            if message.created_at < cutoff:
                try:
                    await message.delete()
                    print(f"[{pair['name']}] 削除完了: {message.id}")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[{pair['name']}] 削除エラー: {e}")

# --- エラーハンドリングと自動再接続 ---
@bot.event
async def on_disconnect():
    print("Discordから切断されました。再接続を試みます...")

@bot.event
async def on_resumed():
    print("Discordへの再接続が完了しました。")

bot.run(BOT_TOKEN)
