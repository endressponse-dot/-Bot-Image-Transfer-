import discord
from discord.ext import commands
import sqlite3
import datetime
import re

# モジュールインポート（TOKEN から DISCORD_BOT_TOKEN へ修正）
from config import DISCORD_BOT_TOKEN, DB_FILE
from database import (
    init_db,
    build_group_map_text,
    get_guild_language_setting,
    get_promotion_rules,
    is_message_promoted,
    record_promoted_message,
    get_group_retention_days
)
from translator import translate_text, translate_image
from ui_group import GroupActionView, OperationSelectView
from ui_promotion import PromotionRuleView

# Discord Botの準備 (インテント設定)
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ==========================================
# 1. 起動時イベント
# ==========================================
@bot.event
async def on_ready():
    init_db()  # DBテーブル初期化
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# ==========================================
# 2. スラッシュコマンド群
# ==========================================

@bot.tree.command(name="setup", description="グループのチャンネル設定パネルを開きます")
async def setup_command(interaction: discord.Interaction):
    """ボタン群（作成・一覧・追加・削除・説明・保持）を表示するパネル"""
    embed = discord.Embed(
        title="⚙️ 転送グループ管理パネル",
        description="以下のボタンから操作を選択してください。",
        color=discord.Color.blue()
    )
    view = GroupActionView(interaction.guild_id, interaction.locale)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="list", description="現在の設定一覧を表示します")
async def list_command(interaction: discord.Interaction):
    """現在登録されている設定一覧を表示します"""
    text = build_group_map_text(interaction.guild_id, interaction.locale)
    await interaction.response.send_message(text, ephemeral=True)


@bot.tree.command(name="promotion", description="自動昇格（特定リアクションで別グループへ転送）ルールを設定します")
async def promotion_command(interaction: discord.Interaction):
    """自動昇格ルールの設定GUIを表示します"""
    embed = discord.Embed(
        title="⭐ 自動昇格ルールの設定",
        description="特定グループのメッセージに指定リアクションが集まった際、指定の別グループへ自動昇格（転送＋スレッド作成）するルールを設定・管理します。",
        color=discord.Color.gold()
    )
    view = PromotionRuleView(interaction.guild_id, interaction.locale)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="ops", description="操作パネルを表示します")
async def ops_command(interaction: discord.Interaction):
    """ドロップダウン方式の操作パネルを表示します"""
    embed = discord.Embed(
        title="🛠️ Bot操作パネル",
        description="実行したい操作を下のメニューから選択してください。",
        color=discord.Color.green()
    )
    view = OperationSelectView(interaction.guild_id, interaction.locale)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================
# 3. メッセージ転送＆自動翻訳イベント
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    # Bot自身のメッセージやWebhook等は無視
    if message.author.bot:
        return

    # ギルド外メッセージは無視
    if not message.guild:
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 投稿されたチャンネルがどのグループの "src" (転送元) に指定されているか検索
    c.execute('''
        SELECT group_name FROM group_channels 
        WHERE guild_id = ? AND channel_id = ? AND type = 'src'
    ''', (message.guild.id, message.channel.id))
    src_rows = c.fetchall()

    if not src_rows:
        conn.close()
        return

    # サーバーの言語設定を取得 (デフォルトはメイン:ja, サブ:[])
    main_lang, sub_langs = get_guild_language_setting(message.guild.id)

    # 該当するすべてのグループに対して処理
    for row in src_rows:
        group_name = row[0]

        # 転送先 (dest) チャンネルを取得
        c.execute('''
            SELECT channel_id FROM group_channels 
            WHERE guild_id = ? AND group_name = ? AND type = 'dest'
        ''', (message.guild.id, group_name))
        dest_rows = c.fetchall()

        if not dest_rows:
            continue

        # 2. 保持期間の計算 (0なら期限なし)
        days = get_group_retention_days(message.guild.id, group_name)
        delete_at_str = ""
        if days > 0:
            expire_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
            delete_at_str = f"\n🗑️ *保持期限: {expire_dt.strftime('%Y-%m-%d %H:%M UTC')} (自動削除予定)*"

        # 3. 転送先チャンネルへ送るメッセージの組み立て
        for (dest_ch_id,) in dest_rows:
            dest_channel = message.guild.get_channel(dest_ch_id)
            if not dest_channel:
                continue

            # ヘッダー情報
            author_info = f"👤 **{message.author.display_name}** (`{message.author.name}`)"
            origin_info = f"📍 元メッセージ: [移動する]({message.jump_url})"
            header = f"{author_info} | {origin_info}{delete_at_str}\n"

            # A. テキストの翻訳処理
            translated_blocks = []

            if message.content:
                # メイン言語への翻訳
                res_main = await translate_text(message.content, target_lang=main_lang)
                if res_main and res_main.get("text"):
                    translated_blocks.append(f"🌐 **[{main_lang.upper()}]**\n{res_main['text']}")

                # サブ言語への翻訳
                for s_lang in sub_langs:
                    if s_lang.lower() == main_lang.lower():
                        continue
                    res_sub = await translate_text(message.content, target_lang=s_lang)
                    if res_sub and res_sub.get("text"):
                        translated_blocks.append(f"🔤 **[{s_lang.upper()}]**\n{res_sub['text']}")

                # 翻訳結果が得られない、または言語判定でスキップされた場合は原文
                if not translated_blocks:
                    translated_blocks.append(f"📝 **原文**:\n{message.content}")
            
            content_payload = header + "\n\n".join(translated_blocks)

            # B. 添付画像・ファイルの取得と画像内文字翻訳
            files = []
            image_ocr_texts = []

            for attachment in message.attachments:
                # ファイルを再転送用に取得
                try:
                    file_data = await attachment.to_file()
                    files.append(file_data)
                except Exception as e:
                    print(f"Failed to fetch attachment file: {e}")

                # 画像形式であればOCR・翻訳処理
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    try:
                        img_bytes = await attachment.read()
                        ocr_res = await translate_image(img_bytes, target_lang=main_lang)
                        if ocr_res and ocr_res.get("text"):
                            image_ocr_texts.append(
                                f"🖼️ **[画像翻訳: {attachment.filename}]** ({main_lang.upper()})\n{ocr_res['text']}"
                            )
                    except Exception as e:
                        print(f"Failed image translation: {e}")

            if image_ocr_texts:
                content_payload += "\n\n" + "\n\n".join(image_ocr_texts)

            # C. 転送実行
            try:
                await dest_channel.send(content=content_payload, files=files)
            except Exception as e:
                print(f"Error sending forwarded message to {dest_ch_id}: {e}")

    conn.close()


# ==========================================
# 4. リアクションによる自動昇格イベント
# ==========================================
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Bot自身のリアクションは無視
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    channel = guild.get_channel(payload.channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        return

    # メッセージ送信者がBotの場合は無視
    if message.author.bot:
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. リアクションが押されたチャンネルが属するグループを特定
    c.execute('''
        SELECT group_name FROM group_channels 
        WHERE guild_id = ? AND channel_id = ?
    ''', (guild.id, channel.id))
    rows = c.fetchall()

    if not rows:
        conn.close()
        return

    # リアクションされた絵文字表記の統一 (絵文字オブジェクト -> 文字列)
    emoji_str = str(payload.emoji)

    for (group_name,) in rows:
        # 2. このグループに設定されている昇格ルールを取得
        rules = get_promotion_rules(guild.id, group_name)
        if not rules:
            continue

        for rule in rules:
            target_emoji = rule["emoji"]
            threshold = rule["threshold"]

            # リアクションの絵文字がルールに合致するかチェック
            if emoji_str == target_emoji:
                # リアクション数のカウント
                reaction_obj = discord.utils.get(message.reactions, emoji=payload.emoji.name if payload.emoji.is_custom_emoji() else payload.emoji.name)
                
                # パラメータ差異の吸収（オブジェクト直接検索）
                count = 0
                for r in message.reactions:
                    if str(r.emoji) == emoji_str:
                        count = r.count
                        break

                # 閾値に達している場合
                if count >= threshold:
                    # 既に昇格済みメッセージであればスキップ
                    if is_message_promoted(message.id):
                        continue

                    # 3. 昇格先の転送グループを取得
                    c.execute('''
                        SELECT channel_id FROM group_channels 
                        WHERE guild_id = ? AND group_name = ? AND type = 'dest'
                    ''', (guild.id, group_name))
                    dest_channels = c.fetchall()

                    for (dest_ch_id,) in dest_channels:
                        dest_ch = guild.get_channel(dest_ch_id)
                        if not dest_ch:
                            continue

                        # 昇格メッセージの作成
                        embed = discord.Embed(
                            title="⭐ 注目メッセージ（自動昇格）",
                            description=message.content if message.content else "*(本文なし・添付ファイルのみ)*",
                            color=discord.Color.gold(),
                            timestamp=message.created_at
                        )
                        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                        embed.add_field(name="元メッセージ", value=f"[リンクはこちら]({message.jump_url})", inline=False)
                        embed.set_footer(text=f"リアクション {emoji_str} × {count} 達成")

                        # 画像のプレビュー表示（最初の1枚）
                        if message.attachments:
                            first_att = message.attachments[0]
                            if first_att.content_type and first_att.content_type.startswith("image/"):
                                embed.set_image(url=first_att.url)

                        # メッセージ転送
                        promoted_msg = await dest_ch.send(embed=embed)

                        # スレッドの自動作成
                        thread_title = re.sub(r'[\r\n]+', ' ', message.content)[:30] if message.content else "画展議論スレッド"
                        thread = await promoted_msg.create_thread(
                            name=f"💬 {thread_title}",
                            auto_archive_duration=1440 # 24時間でアーカイブ
                        )

                        # DBに昇格記録を保存（二重昇格防止）
                        record_promoted_message(
                            original_message_id=message.id,
                            promoted_message_id=promoted_msg.id,
                            thread_id=thread.id,
                            guild_id=guild.id,
                            group_name=group_name
                        )

    conn.close()


# ==========================================
# 5. Bot起動エントリーポイント（変数名を修正）
# ==========================================
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("エラー: config.py または環境変数に DISCORD_BOT_TOKEN が設定されていません。")
    else:
        bot.run(DISCORD_BOT_TOKEN)
