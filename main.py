import os
import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime, timedelta, timezone

# --- 設定項目 ---
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DELETE_AFTER_DAYS = 7                   # 自動削除までの日数

# ★ 監視・転送ペアの設定（何組でも追加可能です）
PAIRS = [
    {
        "name": "一般用ペア",
        "source_ids": [1539156107396780132,1539156837469921330,1539223666720509962],  # 一般用フォーラムのID（複数指定可）
        "dest_id": 1539155223925358663        # 一般用転送先(#image-stream)のID
    },
    {
        "name": "NSFW用ペア",
        "source_ids": [1539232843668922418,1539232990813618216,1539233039647899759],  # NSFW用フォーラムのID（複数指定可）
        "dest_id": 1539233186771374100        # NSFW用転送先(#nsfw-image-stream)のID
    }
]

# --- Botの初期化 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    clean_old_messages.start() # 自動削除タスクを開始

@bot.event
async def on_message(message):
    # Bot自身の投稿は無視
    if message.author.bot:
        return

    channel = message.channel
    parent_id = getattr(channel, "parent_id", None)

    # 設定したペアを順番にチェック
    for pair in PAIRS:
        source_ids = pair["source_ids"]
        dest_id = pair["dest_id"]

        # メッセージが対象フォーラム（またはその中のスレッド）から投稿されたか判定
        if channel.id in source_ids or parent_id in source_ids:
            # 画像ファイルの抽出
            image_attachments = [
                att for att in message.attachments 
                if att.content_type and att.content_type.startswith("image/")
            ]

            if image_attachments:
                dest_channel = bot.get_channel(dest_id)
                if dest_channel:
                    for att in image_attachments:
                        file = await att.to_file()
                        await dest_channel.send(
                            content=f"📷 **{message.author.display_name}** さんの投稿（{channel.name}より）",
                            file=file
                        )
                    print(f"[{pair['name']}] 画像を転送しました: {message.id}")
            break # 対象ペアが見つかったらルーティング終了

# --- 7日以上前のメッセージを自動削除するバックグラウンドタスク ---
@tasks.loop(hours=12) # 12時間ごとに実行
async def clean_old_messages():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DELETE_AFTER_DAYS)

    # 登録されている全ペアの転送先チャンネルをチェック
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
                    await asyncio.sleep(1) # API制限回避
                except Exception as e:
                    print(f"[{pair['name']}] 削除エラー: {e}")

bot.run(BOT_TOKEN)
