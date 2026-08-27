import os
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands, tasks

from config import DISCORD_BOT_TOKEN, DB_FILE, DEFAULT_DELETE_AFTER_DAYS
from database import (
    init_db, 
    get_guild_language_setting, 
    build_group_map_text,
    is_message_forwarded,
    record_forwarded_message,
    is_message_promoted,
    record_promoted_message,
    get_all_group_names
)
from ui_language import send_language_menu
from ui_group import send_group_management_menu
from keep_alive import keep_alive

# ダッシュボード機能およびモーダルの読み込み
from ui_dashboard import create_dashboard_embed, RuleDashboardView, CreateGroupModal

# 権限(Intents)の設定：スレッド・メッセージコンテンツ・リアクション読み取りを確実に許可
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True

class CustomBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 1. データベースの初期化
        init_db()

        # 2. Cogs の非同期ロード
        try:
            await self.load_extension("cogs.transfer")
            print("Loaded extension: cogs.transfer")
        except Exception as e:
            print(f"Failed to load extension cogs.transfer: {e}")

        try:
            await self.load_extension("cogs.settings")
            print("Loaded extension: cogs.settings")
        except Exception as e:
            print(f"Failed to load extension cogs.settings: {e}")

        # 3. スラッシュコマンドの同期
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

bot = CustomBot()

# ---------------------------------------------------------
# 初期化処理
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    if not clean_old_messages.is_running():
        clean_old_messages.start()

# ---------------------------------------------------------
# 画像抽出ユーティリティ関数
# ---------------------------------------------------------
def extract_image_urls(message: discord.Message) -> list[str]:
    urls = []
    if message.attachments:
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                urls.append(att.url)
            elif att.url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                urls.append(att.url)

    if message.embeds:
        for embed in message.embeds:
            if embed.image and embed.image.url:
                urls.append(embed.image.url)
            elif embed.thumbnail and embed.thumbnail.url:
                urls.append(embed.thumbnail.url)

    return urls

# ---------------------------------------------------------
# 1. 転送メッセージ処理（通常チャンネル & フォーラム・スレッド対応）
# ---------------------------------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if isinstance(message.channel, discord.Thread):
        target_channel_id = message.channel.parent_id
        is_thread = True
    else:
        target_channel_id = message.channel.id
        is_thread = False

    image_urls = extract_image_urls(message)

    if not image_urls:
        await bot.process_commands(message)
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT group_name FROM group_channels WHERE guild_id = ? AND channel_id = ? AND type = "src"',
              (message.guild.id, target_channel_id))
    src_rows = c.fetchall()
    
    if not src_rows:
        conn.close()
        await bot.process_commands(message)
        return

    for row in src_rows:
        group_name = row[0]
        
        if is_message_forwarded(message.id):
            continue

        c.execute('SELECT channel_id FROM group_channels WHERE guild_id = ? AND group_name = ? AND type = "dest"',
                  (message.guild.id, group_name))
        dest_rows = c.fetchall()
        
        for d_row in dest_rows:
            dest_ch = message.guild.get_channel(d_row[0])
            if dest_ch:
                channel_display_name = f"{message.channel.parent.name} > {message.channel.name}" if is_thread else message.channel.name
                
                embed = discord.Embed(
                    title="",
                    description=f"### [📷 画像が共有されました]({message.jump_url})\n👤 投稿者: {message.author.mention} | 📍 チャンネル: **#{channel_display_name}**",
                    color=discord.Color.blue()
                )
                
                if message.content:
                    embed.add_field(name="💬 メッセージ", value=message.content, inline=False)
                
                embed.set_image(url=image_urls[0])
                await dest_ch.send(embed=embed)
                
                for extra_url in image_urls[1:]:
                    img_embed = discord.Embed(color=discord.Color.blue())
                    img_embed.set_image(url=extra_url)
                    await dest_ch.send(embed=img_embed)
                
                record_forwarded_message(message.id, message.guild.id, group_name)

    conn.close()
    await bot.process_commands(message)

# ---------------------------------------------------------
# 2. リアクションによる自動昇格＆スレッド作成イベント
# ---------------------------------------------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id or not payload.guild_id:
        return

    if is_message_promoted(payload.message_id):
        return

    channel = bot.get_channel(payload.channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        return

    target_channel_id = channel.parent_id if isinstance(channel, discord.Thread) else channel.id

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute('SELECT group_name FROM group_channels WHERE guild_id = ? AND channel_id = ? AND type = "src"',
              (payload.guild_id, target_channel_id))
    src_rows = c.fetchall()

    if not src_rows:
        conn.close()
        return

    emoji_str = str(payload.emoji)

    for row in src_rows:
        group_name = row[0]
        
        c.execute('SELECT threshold FROM promotion_rules WHERE guild_id = ? AND group_name = ? AND emoji = ?',
                  (payload.guild_id, group_name, emoji_str))
        rule = c.fetchone()

        if not rule:
            continue

        threshold = rule[0]
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name if payload.emoji.is_customemoji() else payload.emoji.name)
        count = reaction.count if reaction else 0

        if count >= threshold:
            c.execute('SELECT channel_id FROM group_channels WHERE guild_id = ? AND group_name = ? AND type = "dest"',
                      (payload.guild_id, group_name))
            dest_rows = c.fetchall()

            image_urls = extract_image_urls(message)

            for d_row in dest_rows:
                dest_ch = message.guild.get_channel(d_row[0])
                if dest_ch:
                    channel_display_name = f"{channel.parent.name} > {channel.name}" if isinstance(channel, discord.Thread) else channel.name

                    embed = discord.Embed(
                        title="⭐ 殿堂入り作品（自動昇格）",
                        description=f"### [🌟 元メッセージを見る]({message.jump_url})\n👤 作者: {message.author.mention} | 📍 チャンネル: **#{channel_display_name}**",
                        color=discord.Color.gold()
                    )

                    if message.content:
                        embed.add_field(name="💬 メッセージ", value=message.content, inline=False)

                    if image_urls:
                        embed.set_image(url=image_urls[0])

                    promoted_msg = await dest_ch.send(embed=embed)

                    if len(image_urls) > 1:
                        for extra_url in image_urls[1:]:
                            img_embed = discord.Embed(color=discord.Color.gold())
                            img_embed.set_image(url=extra_url)
                            await dest_ch.send(embed=img_embed)

                    thread_name = f"💬 感想・コメント: {message.author.display_name}の作品"
                    thread = await promoted_msg.create_thread(name=thread_name[:100], auto_archive_duration=10080)

                    record_promoted_message(
                        original_message_id=message.id,
                        promoted_message_id=promoted_msg.id,
                        thread_id=thread.id,
                        guild_id=payload.guild_id,
                        group_name=group_name
                    )
                    break

    conn.close()

# ---------------------------------------------------------
# 3. ダッシュボード起動用UIクラス
# ---------------------------------------------------------
class DashboardGroupSelect(discord.ui.Select):
    def __init__(self, guild_id: int, groups: list):
        self.guild_id = guild_id
        options = [discord.SelectOption(label=f"⚙️ {g}", value=g) for g in groups]
        super().__init__(placeholder="設定するグループを選択してください...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        group_name = self.values[0]
        embed = create_dashboard_embed(self.guild_id, group_name)
        view = RuleDashboardView(self.guild_id, group_name)
        await interaction.response.edit_message(content=None, embed=embed, view=view)

# ---------------------------------------------------------
# 4. スラッシュコマンド群
# ---------------------------------------------------------
@bot.tree.command(name="setup", description="一画面設定ダッシュボードを開きます（管理者専用）")
async def setup_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ このコマンドは管理者専用です。", ephemeral=True)
        return
    
    guild_id = interaction.guild_id
    existing_groups = get_all_group_names(guild_id)
    
    if not existing_groups:
        # グループが一つも無い場合は直接モーダルを開いて新規作成へ誘導
        await interaction.response.send_modal(CreateGroupModal())
    else:
        view = discord.ui.View()
        view.add_item(DashboardGroupSelect(guild_id, existing_groups))
        await interaction.response.send_message("📁 **ダッシュボードを開くグループを選択してください:**", view=view, ephemeral=True)

@bot.tree.command(name="config", description="従来の転送設定メニューを開きます")
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
    text = build_group_map_text(interaction.guild_id, interaction.locale)
    await interaction.response.send_message(text, ephemeral=True)

# ---------------------------------------------------------
# 5. チャンネル全削除機能 (/clear_channel)
# ---------------------------------------------------------
class ClearConfirmView(discord.ui.View):
    def __init__(self, locale):
        super().__init__(timeout=60)
        self.locale = locale

    @discord.ui.button(label="🗑️ 実行する", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="⏳ メッセージ削除処理を実行中です...", 
            view=None
        )
        
        channel = interaction.channel
        now = datetime.now(timezone.utc)
        fourteen_days_ago = now - timedelta(days=14)
        
        deleted_count = 0
        
        try:
            purged = await channel.purge(limit=1000, after=fourteen_days_ago)
            deleted_count += len(purged)
        except Exception as e:
            print(f"Purge error: {e}")

        try:
            async for msg in channel.history(limit=1000, before=fourteen_days_ago):
                try:
                    await msg.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.8)
                except Exception:
                    pass
        except Exception as e:
            print(f"History purge error: {e}")
        
        await interaction.followup.send(f"🧹 チャンネル内のメッセージを削除しました（計 {deleted_count} 通）。", ephemeral=True)

@bot.tree.command(name="clear_channel", description="このチャンネル内のメッセージをすべて削除します（管理者専用）")
async def clear_channel_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ このコマンドは管理者専用です。", ephemeral=True)
        return
    
    warn_text = "⚠️ **警告**: このチャンネルの過去メッセージを削除します。よろしいですか？"
    view = ClearConfirmView(interaction.locale)
    await interaction.response.send_message(warn_text, view=view, ephemeral=True)

# ---------------------------------------------------------
# 6. 動的自動削除バックグラウンドタスク
# ---------------------------------------------------------
@tasks.loop(hours=1)
async def clean_old_messages():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
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
            continue
        
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
    keep_alive()
    if DISCORD_BOT_TOKEN:
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKENが設定されていません。")
