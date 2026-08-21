import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import tasks
from discord import app_commands

from config import BOT_TOKEN, DB_FILE, DELETE_AFTER_DAYS
from locales import get_text
from database import init_db, build_group_map_text, get_guild_language_setting
from ui_language import send_language_menu
from ui_group import SetGroupOpView
from ui_reset import ResetConfirmView

# Botの準備
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    init_db()
    await tree.sync()
    if not clean_old_messages.is_running():
        clean_old_messages.start()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# ==========================================
# 🚀 スラッシュコマンド
# ==========================================

@tree.command(name="set_group", description="グループの確認・追加編集・削除を行います")
@app_commands.checks.has_permissions(administrator=True)
async def set_group(interaction: discord.Interaction):
    map_text = build_group_map_text(interaction.guild_id, interaction.locale, bot)
    view = SetGroupOpView(interaction.guild_id, interaction.locale, bot)
    msg = f"{map_text}\n\n{get_text(str(interaction.locale), 'menu_prompt')}"
    await interaction.response.send_message(msg, view=view, ephemeral=True)

@tree.command(name="set_language", description="転送先で表示されるメッセージの言語（メイン・サブ）を設定します")
@app_commands.checks.has_permissions(administrator=True)
async def set_language(interaction: discord.Interaction):
    await send_language_menu(interaction, interaction.guild_id, interaction.locale)

@tree.command(name="reset_all_settings", description="【危険】このサーバーのすべての転送グループ設定をリセットします")
@app_commands.checks.has_permissions(administrator=True)
async def reset_all_settings(interaction: discord.Interaction):
    view = ResetConfirmView(interaction.guild_id, interaction.locale)
    msg = get_text(str(interaction.locale), "reset_warning")
    await interaction.response.send_message(msg, view=view, ephemeral=True)

# ==========================================
# 🔄 転送処理 ＆ 自動削除
# ==========================================

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    channel = message.channel
    parent_id = getattr(channel, "parent_id", None)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT group_name, channel_id FROM group_channels WHERE guild_id = ? AND type = "source"', (message.guild.id,))
    source_rows = c.fetchall()

    dest_ids = []
    image_attachments = []

    for group_name, src_id in source_rows:
        if channel.id == src_id or parent_id == src_id:
            image_attachments = [
                att for att in message.attachments 
                if att.content_type and att.content_type.startswith("image/")
            ]

            if image_attachments:
                c.execute('SELECT channel_id FROM group_channels WHERE guild_id = ? AND group_name = ? AND type = "dest"', (message.guild.id, group_name))
                dest_ids = [row[0] for row in c.fetchall()]
            break

    conn.close()

    if image_attachments and dest_ids:
        main_lang_code, sub_langs_str = get_guild_language_setting(message.guild.id)
        
        # サーバーの言語設定（ロケール）を安全にパース
        server_locale_str = str(message.guild.preferred_locale) if message.guild.preferred_locale else "en"
        server_lang_base = server_locale_str.split('-')[0].lower()

        # メイン言語が未設定(default)の場合はサーバーの言語設定を採用
        actual_main = main_lang_code if main_lang_code and main_lang_code != "default" else server_lang_base

        title_text = f"🔗 {get_text(actual_main, 'embed_title')}"
        jump_url = message.jump_url
        
        desc_lines = []
        # メイン言語の設定に基づく説明文を取得して追加
        main_desc = get_text(actual_main, "embed_desc").format(
            author=message.author.display_name,
            channel=channel.name
        )
        desc_lines.append(main_desc)
        
        # サブ言語（langmap）の設定がある場合、それぞれの言語で説明文を追加
        if sub_langs_str:
            sub_langs = sub_langs_str.split(',')
            for sl in sub_langs:
                sl_clean = sl.strip().lower()
                if sl_clean and sl_clean != "none":
                    sub_desc = get_text(sl_clean, "embed_desc").format(
                        author=message.author.display_name,
                        channel=channel.name
                    )
                    desc_lines.append(sub_desc)

        final_desc = "\n\n".join(desc_lines)

        for dest_id in dest_ids:
            dest_channel = bot.get_channel(dest_id)
            if dest_channel:
                for att in image_attachments:
                    file = await att.to_file()
                    embed = discord.Embed(
                        title=title_text,
                        url=jump_url,
                        description=final_desc,
                        color=discord.Color.blue()
                    )
                    embed.set_image(url=f"attachment://{file.filename}")
                    await dest_channel.send(embed=embed, file=file)

@tasks.loop(hours=12)
async def clean_old_messages():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DELETE_AFTER_DAYS)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT DISTINCT channel_id FROM group_channels WHERE type = "dest"')
    dest_ids = [row[0] for row in c.fetchall()]
    conn.close()

    for dest_id in dest_ids:
        dest_channel = bot.get_channel(dest_id)
        if not dest_channel:
            continue

        async for message in dest_channel.history(limit=None):
            if message.created_at < cutoff:
                try:
                    if (now - message.created_at).days < 14:
                        await dest_channel.purge(limit=100, check=lambda m: m.created_at < cutoff)
                        break
                    else:
                        await message.delete()
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"削除エラー: {e}")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)