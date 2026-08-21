import os
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands, tasks

from config import DISCORD_BOT_TOKEN, DB_FILE, DEFAULT_DELETE_AFTER_DAYS
from locales import get_text
from database import init_db, get_guild_language_setting, build_group_map_text
from ui_language import send_language_menu
from ui_group import send_group_management_menu
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# 初期化処理
# ---------------------------------------------------------
@bot.event
async def on_ready():
    init_db()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    clean_old_messages.start()

# ---------------------------------------------------------
# 1. 転送メッセージ処理（Embedデザイン構築の更新）
# ---------------------------------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # 画像アタッチメントがなければスキップ
    if not message.attachments:
        await bot.process_commands(message)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 送信チャンネルがどのグループの転送元(src)か取得
    c.execute('SELECT group_name FROM group_channels WHERE guild_id = ? AND channel_id = ? AND type = "src"',
              (message.guild.id, message.channel.id))
    src_rows = c.fetchall()
    
    if not src_rows:
        conn.close()
        await bot.process_commands(message)
        return

    main_lang, _ = get_guild_language_setting(message.guild.id)
    actual_lang = message.guild.preferred_locale if main_lang == "default" else main_lang

    embed_title = get_text(actual_lang, "embed_title")
    embed_desc_template = get_text(actual_lang, "embed_desc")
    
    # 📌 マークダウンリンク付きタイトル・太字＆絵文字つきコンパクトDescriptionの作成
    title_text = f"[{embed_title}]({message.jump_url})"
    formatted_desc = embed_desc_template.format(
        author=message.author.mention,
        channel=message.channel.name
    )

    for row in src_rows:
        group_name = row[0]
        c.execute('SELECT channel_id FROM group_channels WHERE guild_id = ? AND group_name = ? AND type = "dest"',
                  (message.guild.id, group_name))
        dest_rows = c.fetchall()
        
        for d_row in dest_rows:
            dest_ch = message.guild.get_channel(d_row[0])
            if dest_ch:
                embed = discord.Embed(
                    title="",
                    description=f"### {title_text}\n{formatted_desc}",
                    color=discord.Color.blue()
                )
                if message.content:
                    embed.add_field(name="💬 Message", value=message.content, inline=False)
                
                # 最初のアタッチメント画像をメインに設定
                embed.set_image(url=message.attachments[0].url)
                await dest_ch.send(embed=embed)
                
                # 複数画像がある場合は追加で送信
                for att in message.attachments[1:]:
                    img_embed = discord.Embed(color=discord.Color.blue())
                    img_embed.set_image(url=att.url)
                    await dest_ch.send(embed=img_embed)

    conn.close()
    await bot.process_commands(message)

# ---------------------------------------------------------
# 2. スラッシュコマンド群
# ---------------------------------------------------------
@bot.tree.command(name="config", description="転送設定メニューを開きます")
async def config_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ このコマンドは管理者専用です。", ephemeral=True)
        return
    
    await send_group_management_menu(interaction, interaction.guild_id, interaction.locale)

@bot.tree.command(name="language", description="言語設定を変更します")
async def language_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ このコマンドは管理者専用です。", ephemeral=True)
        return
    
    await send_language_menu(interaction, interaction.guild_id, interaction.locale)

@bot.tree.command(name="list", description="現在の設定一覧を表示します")
async def list_command(interaction: discord.Interaction):
    text = build_group_map_text(interaction.guild_id, interaction.locale, bot)
    await interaction.response.send_message(text, ephemeral=True)

# 3. チャンネル全削除機能 (/clear_channel)
class ClearConfirmView(discord.ui.View):
    def __init__(self, locale):
        super().__init__(timeout=60)
        self.locale = locale

    @discord.ui.button(label="🗑️ 実行する", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        
        now = datetime.now(timezone.utc)
        fourteen_days_ago = now - timedelta(days=14)
        
        deleted_count = 0
        # 14日以内のメッセージは一括削除(purge)
        try:
            purged = await channel.purge(limit=1000, after=fourteen_days_ago)
            deleted_count += len(purged)
        except Exception as e:
            print(f"Purge error: {e}")

        # 14日以上経過した古いメッセージは個別に削除
        async for msg in channel.history(limit=1000, before=fourteen_days_ago):
            try:
                await msg.delete()
                deleted_count += 1
                await asyncio.sleep(1.0)  # レートリミット回避のウェイト
            except Exception:
                pass
                
        await interaction.followup.send(f"🧹 チャンネル内のメッセージを削除しました（計 {deleted_count} 通）。", ephemeral=True)

@bot.tree.command(name="clear_channel", description="このチャンネル内のメッセージをすべて削除します（管理者専用）")
async def clear_channel_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ このコマンドは管理者専用です。", ephemeral=True)
        return
    
    warn_text = get_text(interaction.locale, "clear_confirm")
    view = ClearConfirmView(interaction.locale)
    await interaction.response.send_message(warn_text, view=view, ephemeral=True)

# ---------------------------------------------------------
# 4. 動的自動削除バックグラウンドタスク
# ---------------------------------------------------------
@tasks.loop(hours=1)
async def clean_old_messages():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 転送先(dest)チャンネルとその保持日数（グループ設定）を取得
    c.execute('''
        SELECT gc.channel_id, COALESCE(gs.retention_days, ?) 
        FROM group_channels gc
        LEFT JOIN group_settings gs ON gc.guild_id = gs.guild_id AND gc.group_name = gs.group_name
        WHERE gc.type = 'dest'
    ''', (DEFAULT_DELETE_AFTER_DAYS,))
    
    dest_channels = c.fetchall()
    conn.close()

    now = datetime.now(timezone.utc)

    for ch_id, retention_days in dest_channels:
        if retention_days <= 0:
            continue  # 0以下の場合は削除無制限
        
        channel = bot.get_channel(ch_id)
        if not channel:
            continue

        cutoff_time = now - timedelta(days=retention_days)
        
        try:
            async for message in channel.history(limit=200, before=cutoff_time):
                if message.pinned:
                    continue
                try:
                    await message.delete()
                    await asyncio.sleep(1.0)
                except Exception as e:
                    print(f"Error deleting message {message.id}: {e}")
        except Exception as e:
            print(f"Error checking channel {ch_id}: {e}")

# ---------------------------------------------------------
# Bot起動
# ---------------------------------------------------------

if __name__ == "__main__":
    keep_alive()  # 👈 Bot起動前にダミーWebサーバーをバックグラウンド起動
    if DISCORD_BOT_TOKEN:
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKENが設定されていません。")
