import os
import threading
import sqlite3
import asyncio
from flask import Flask
import discord
from discord import app_commands
from discord.ext import tasks, commands
from datetime import datetime, timedelta, timezone

# --- Renderポート開放用のダミーWEBサーバー ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Multi-Server Bot is alive!"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- データベース（SQLite）の初期化 ---
DB_FILE = "settings.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # サーバーごとの転送設定を保存するテーブル
    c.execute('''
        CREATE TABLE IF NOT EXISTS pairs (
            guild_id INTEGER,
            pair_name TEXT,
            source_id INTEGER,
            dest_id INTEGER,
            PRIMARY KEY (guild_id, pair_name)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Botの初期化 ---
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DELETE_AFTER_DAYS = 7

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        # スラッシュコマンドをDiscord全体に同期
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    clean_old_messages.start()

# --- スラッシュコマンド：設定の登録・上書き ---
@bot.tree.command(name="set_pair", description="画像の転送ペア（監視元と転送先）を設定します")
@app_commands.describe(
    pair_name="ペアの名前（例: 一般用、NSFW用など任意）",
    source_channel="監視するフォーラムまたはチャンネル",
    dest_channel="画像を転送するストリームチャンネル"
)
@app_commands.checks.has_permissions(administrator=True)
async def set_pair(interaction: discord.Interaction, pair_name: str, source_channel: discord.abc.GuildChannel, dest_channel: discord.TextChannel):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO pairs (guild_id, pair_name, source_id, dest_id)
        VALUES (?, ?, ?, ?)
    ''', (interaction.guild_id, pair_name, source_channel.id, dest_channel.id))
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"✅ 設定を保存しました！\n"
        f"・**ペア名**: {pair_name}\n"
        f"・**監視元**: {source_channel.mention}\n"
        f"・**転送先**: {dest_channel.mention}",
        ephemeral=True
    )

# --- スラッシュコマンド：設定の一覧確認 ---
@bot.tree.command(name="list_pairs", description="現在の転送ペア設定一覧を表示します")
@app_commands.checks.has_permissions(administrator=True)
async def list_pairs(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT pair_name, source_id, dest_id FROM pairs WHERE guild_id = ?', (interaction.guild_id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("設定されている転送ペアはありません。", ephemeral=True)
        return

    text = "📋 **現在の転送ペア設定一覧:**\n"
    for name, src_id, dest_id in rows:
        src_chan = bot.get_channel(src_id)
        dest_chan = bot.get_channel(dest_id)
        src_name = src_chan.mention if src_chan else f"ID:{src_id}"
        dest_name = dest_chan.mention if dest_chan else f"ID:{dest_id}"
        text += f"・**{name}**: {src_name} ➔ {dest_name}\n"

    await interaction.response.send_message(text, ephemeral=True)

# --- 画像転送処理 ---
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    channel = message.channel
    parent_id = getattr(channel, "parent_id", None)

    # DBからこのサーバーの設定を取得
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT source_id, dest_id FROM pairs WHERE guild_id = ?', (message.guild.id,))
    pairs = c.fetchall()
    conn.close()

    for source_id, dest_id in pairs:
        # 投稿された場所が監視対象（直接またはスレッドの親）か確認
        if channel.id == source_id or parent_id == source_id:
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
                        embed = discord.Embed(
                            title="🔗 元の投稿（スレッド）を開く",
                            url=jump_url,
                            description=f"📷 **{message.author.display_name}** さんの投稿（#{channel.name} より）",
                            color=discord.Color.blue()
                        )
                        embed.set_image(url=f"attachment://{file.filename}")
                        await dest_channel.send(embed=embed, file=file)
            break

# --- 7日後の自動削除タスク ---
@tasks.loop(hours=12)
async def clean_old_messages():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DELETE_AFTER_DAYS)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT DISTINCT dest_id FROM pairs')
    dest_ids = [row[0] for row in c.fetchall()]
    conn.close()

    for dest_id in dest_ids:
        dest_channel = bot.get_channel(dest_id)
        if not dest_channel:
            continue

        async for message in dest_channel.history(limit=200):
            if message.created_at < cutoff:
                try:
                    await message.delete()
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"削除エラー: {e}")

bot.run(BOT_TOKEN)
