import os
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands, tasks

# ==========================================
# ⚙️ 設定 & Render用 Web サーバー設定
# ==========================================

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

keep_alive()

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DB_FILE = "bot_database.db"
DELETE_AFTER_DAYS = 3  # 自動削除する経過日数

# ==========================================
# 🗄️ データベースの初期化
# ==========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_channels (
            guild_id INTEGER,
            group_name TEXT,
            channel_id INTEGER,
            type TEXT,
            PRIMARY KEY (guild_id, group_name, channel_id, type)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS guild_languages (
            guild_id INTEGER PRIMARY KEY,
            main_lang TEXT,
            sub_langs TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🌐 多言語ローカライズ用テキスト辞書 & 定義
# ==========================================

TEXTS = {
    "en": {
        "map_title": "📊 **Forwarding Group Configuration List**",
        "no_groups": "No registered groups.",
        "none": "None",
        "source": "Source",
        "dest": "Destination",
        "menu_prompt": "Select an operation from the buttons below:",
        "btn_add": "Add / Edit Group",
        "btn_del": "Delete Group",
        "select_edit_group": "Select a group to edit, or create a new one:",
        "select_del_group": "Select a group to delete:",
        "new_group_option": "Create New Group",
        "modal_new_title": "Create New Group",
        "modal_gname_label": "Group Name",
        "created_msg": "✅ Group **[{name}]** has been saved.",
        "added_msg": "✅ Added {channel} as {type} to **[{name}]**.",
        "group_deleted": "🗑️ Group **[{name}]** has been deleted.",
        "select_target_type": "Select channel type to add to **[{name}]**:",
        "btn_add_src": "Add Source (📥)",
        "btn_add_dest": "Add Destination (📤)",
        "reset_warning": "⚠️ Are you sure you want to reset all settings for this server?",
        "btn_confirm_reset": "Reset All",
        "btn_cancel": "Cancel",
        "reset_complete": "✅ All group settings have been reset.",
        "reset_cancelled": "Cancelled.",
        "embed_title": "New Image Forwarded",
        "embed_desc": "Open original thread (channel: #{channel})\nPosted by: {author}"
    },
    "ja": {
        "map_title": "📊 **転送グループ設定一覧**",
        "no_groups": "登録されているグループはありません。",
        "none": "なし",
        "source": "転送元",
        "dest": "転送先",
        "menu_prompt": "以下のボタンから操作を選択してください:",
        "btn_add": "グループの追加・編集",
        "btn_del": "グループの削除",
        "select_edit_group": "編集するグループを選択するか、新規作成してください:",
        "select_del_group": "削除するグループを選択してください:",
        "new_group_option": "新規グループを作成",
        "modal_new_title": "新規グループ作成",
        "modal_gname_label": "グループ名",
        "created_msg": "✅ グループ **[{name}]** を保存しました。",
        "added_msg": "✅ **[{name}]** の{type}に {channel} を追加しました。",
        "group_deleted": "🗑️ グループ **[{name}]** を削除しました。",
        "select_target_type": "**[{name}]** に追加するチャンネルの種類を選択してください:",
        "btn_add_src": "転送元を追加 (📥)",
        "btn_add_dest": "転送先を追加 (📤)",
        "reset_warning": "⚠️ このサーバーの全設定をリセットしてもよろしいですか？",
        "btn_confirm_reset": "すべてリセット",
        "btn_cancel": "キャンセル",
        "reset_complete": "✅ すべてのグループ設定をリセットしました。",
        "reset_cancelled": "キャンセルしました。",
        "embed_title": "元の投稿（スレッド）を開く",
        "embed_desc": "{author} さんの投稿（#{channel} より）"
    }
}

LANG_MAP = {
    "en": "🇺🇸 English",
    "ja": "🇯🇵 日本語",
    "ko": "🇰🇷 한국어",
    "zh-cn": "🇨🇳 简体中文",
    "zh-tw": "🇹🇼 繁體中文",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch",
    "es": "🇪🇸 Español",
    "it": "🇮🇹 Italiano",
    "ru": "🇷🇺 Русский",
    "pt": "🇵🇹 Português",
    "hi": "🇮🇳 हिन्दी"
}

def get_text(locale_str: str, key: str) -> str:
    lang = locale_str.split('-')[0].lower() if locale_str else "en"
    if lang not in TEXTS:
        lang = "en"
    return TEXTS[lang].get(key, TEXTS["en"].get(key, key))

def get_lang_display(lang_code: str, guild_locale: str) -> str:
    if not lang_code or lang_code == "default":
        actual_lang = guild_locale.split('-')[0].lower()
        base_str = LANG_MAP.get(actual_lang, f"🌐 {actual_lang}")
        return f"{base_str} (サーバー設定)"
    return LANG_MAP.get(lang_code, f"🌐 {lang_code}")

def get_guild_language_setting(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT main_lang, sub_langs FROM guild_languages WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0] or "default", row[1] or ""
    return "default", ""

# ==========================================
# 🤖 Discord Bot の初期化
# ==========================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def build_group_map_text(guild_id: int, locale: discord.Locale) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT group_name, channel_id, type FROM group_channels WHERE guild_id = ? ORDER BY group_name', (guild_id,))
    rows = c.fetchall()
    conn.close()

    map_title = get_text(str(locale), "map_title")
    if not rows:
        return f"{map_title}\n{get_text(str(locale), 'no_groups')}"

    groups = {}
    for gname, cid, ctype in rows:
        if gname not in groups:
            groups[gname] = {"source": [], "dest": []}
        groups[gname][ctype].append(cid)

    map_text = f"{map_title}\n"
    for gname, data in groups.items():
        map_text += f"\n📁 **[{gname}]**\n"
        src_list = [bot.get_channel(cid).mention if bot.get_channel(cid) else f"ID:{cid}" for cid in data["source"]]
        src_str = ", ".join(src_list) if src_list else get_text(str(locale), "none")
        map_text += f"  ├ 📥 **{get_text(str(locale), 'source')}**: {src_str}\n"
        dest_list = [bot.get_channel(cid).mention if bot.get_channel(cid) else f"ID:{cid}" for cid in data["dest"]]
        dest_str = ", ".join(dest_list) if dest_list else get_text(str(locale), "none")
        map_text += f"  └ 📤 **{get_text(str(locale), 'dest')}**: {dest_str}\n"

    return map_text

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    clean_old_messages.start()

# ==========================================
# 🗣️ UIパーツ（言語設定 /set_language フロー）
# ==========================================

class LanguageSettingView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale

    @discord.ui.button(label="メイン言語を変更する", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="edit_main")
    async def edit_main_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainLangSelectView(self.guild_id, self.locale)
        await interaction.response.edit_message(content="変更するメイン言語を選択してください：\n(※選択すると即座に反映されます)", view=view)

    @discord.ui.button(label="サブ言語を追加・編集する", style=discord.ButtonStyle.success, emoji="🌍", custom_id="edit_sub")
    async def edit_sub_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = SubLangSelectView(self.guild_id, self.locale)
        await interaction.response.edit_message(content="追加するサブ言語を選択してください（複数選択可）。\n※「サブ言語なし」を選ぶとクリアされます。\n※選んだ順番で表示されます。", view=view)

class MainLangSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label=f"{label}", value=code) for code, label in LANG_MAP.items()]
        select = discord.ui.Select(placeholder="メイン言語を選択してください", min_values=1, max_values=1, options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_lang = interaction.data["values"][0]
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO guild_languages (guild_id, main_lang) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET main_lang = ?', (self.guild_id, selected_lang, selected_lang))
        conn.commit()
        conn.close()

        await send_language_menu(interaction, self.guild_id, self.locale, edit=True)

class SubLangSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label="🚫 サブ言語なし (クリア)", value="none", description="追加の言語表示をオフにします")]
        options.extend([discord.SelectOption(label=f"{label}", value=code) for code, label in LANG_MAP.items()])
        
        select = discord.ui.Select(placeholder="サブ言語を選択（複数選択可）", min_values=1, max_values=len(LANG_MAP), options=options[:25])
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_langs = interaction.data["values"]
        sub_langs_str = "" if "none" in selected_langs else ",".join(selected_langs)

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO guild_languages (guild_id, sub_langs) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET sub_langs = ?', (self.guild_id, sub_langs_str, sub_langs_str))
        conn.commit()
        conn.close()

        await send_language_menu(interaction, self.guild_id, self.locale, edit=True)

async def send_language_menu(interaction: discord.Interaction, guild_id: int, locale: discord.Locale, edit=False):
    main_lang, sub_langs = get_guild_language_setting(guild_id)
    server_locale_str = str(interaction.guild.preferred_locale) if interaction.guild else "en"
    
    main_display = get_lang_display(main_lang, server_locale_str)
    
    if sub_langs:
        sub_list = [LANG_MAP.get(l, l) for l in sub_langs.split(',')]
        sub_display = "\n".join([f"  ・{sl}" for sl in sub_list])
    else:
        sub_display = "  ・(なし)"

    msg = (
        f"**【現在の転送先表示言語設定】**\n\n"
        f"👑 **メイン言語**: {main_display}\n"
        f"🌍 **サブ言語**:\n{sub_display}\n\n"
        f"設定を変更する場合は、下のボタンを選択してください。"
    )
    
    view = LanguageSettingView(guild_id, locale)
    if edit:
        await interaction.response.edit_message(content=msg, view=view)
    else:
        await interaction.response.send_message(content=msg, view=view, ephemeral=True)

# ==========================================
# 🛠️ UIパーツ（/set_group フロー - 連続操作・終了ボタン対応）
# ==========================================

class SetGroupOpView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=180) # 連続操作を考慮してタイムアウトを3分に延長
        self.guild_id = guild_id
        self.locale = locale

        self.add_btn.label = get_text(str(locale), "btn_add")
        self.del_btn.label = get_text(str(locale), "btn_del")
        self.close_btn.label = "メニューを閉じる" # 終了用ボタン

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="✏️", custom_id="add_btn", row=0)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        groups = [row[0] for row in c.fetchall()]
        conn.close()

        view = GroupSelectForEditView(self.guild_id, groups, self.locale)
        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_edit_group')}"
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="del_btn", row=0)
    async def del_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        groups = [row[0] for row in c.fetchall()]
        conn.close()

        if not groups:
            map_text = build_group_map_text(self.guild_id, self.locale)
            await interaction.response.edit_message(content=map_text, view=self)
            return

        view = GroupSelectForDeleteView(self.guild_id, groups, self.locale)
        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_del_group')}"
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="✖️", custom_id="close_btn", row=1)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        map_text = build_group_map_text(self.guild_id, self.locale)
        await interaction.response.edit_message(content=f"{map_text}\n\n🔒 設定メニューを終了しました。", view=None)

class GroupSelectForEditView(discord.ui.View):
    def __init__(self, guild_id: int, groups: list, locale: discord.Locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale

        options = [discord.SelectOption(label=get_text(str(locale), "new_group_option"), value="__NEW__", emoji="➕")]
        options.extend([discord.SelectOption(label=g, value=g, emoji="📁") for g in groups[:24]])

        select = discord.ui.Select(placeholder="...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        if selected == "__NEW__":
            modal = NewGroupModal(self.guild_id, self.locale)
            await interaction.response.send_modal(modal)
            # モダンのポップアップ後に元のメッセージをメインメニューに戻す
            map_text = build_group_map_text(self.guild_id, self.locale)
            view = SetGroupOpView(self.guild_id, self.locale)
            await interaction.message.edit(content=f"{map_text}\n\n{get_text(str(self.locale), 'menu_prompt')}", view=view)
        else:
            view = AddTypeTargetView(self.guild_id, selected, self.locale)
            map_text = build_group_map_text(self.guild_id, self.locale)
            msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_target_type').format(name=selected)}"
            await interaction.response.edit_message(content=msg, view=view)

class NewGroupModal(discord.ui.Modal):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(title=get_text(str(locale), "modal_new_title"))
        self.guild_id = guild_id
        self.locale = locale

        self.group_name_input = discord.ui.TextInput(
            label=get_text(str(locale), "modal_gname_label"),
            placeholder="Ex: Group-A",
            required=True
        )
        self.add_item(self.group_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        gname = self.group_name_input.value.strip()
        view = NewGroupChannelSelectView(self.guild_id, gname, self.locale)
        msg = f"📁 **[{gname}]** の転送元（📥）と転送先（📤）チャンネルを選択してください。"
        await interaction.response.send_message(content=msg, view=view, ephemeral=True)

class NewGroupChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale: discord.Locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale
        self.selected_src = None
        self.selected_dest = None

        self.src_select = discord.ui.ChannelSelect(
            placeholder="📥 転送元チャンネルを選択...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.forum],
            min_values=1, max_values=1
        )
        self.src_select.callback = self.src_callback
        self.add_item(self.src_select)

        self.dest_select = discord.ui.ChannelSelect(
            placeholder="📤 転送先チャンネルを選択...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1, max_values=1
        )
        self.dest_select.callback = self.dest_callback
        self.add_item(self.dest_select)

    async def src_callback(self, interaction: discord.Interaction):
        self.selected_src = self.src_select.values[0].id
        await interaction.response.defer()

    async def dest_callback(self, interaction: discord.Interaction):
        self.selected_dest = self.dest_select.values[0].id
        await interaction.response.defer()

    @discord.ui.button(label="保存する", style=discord.ButtonStyle.success, emoji="💾", row=2)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_src or not self.selected_dest:
            await interaction.response.send_message("転送元と転送先を両方選択してください。", ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, "source")', (self.guild_id, self.group_name, self.selected_src))
        c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, "dest")', (self.guild_id, self.group_name, self.selected_dest))
        conn.commit()
        conn.close()

        # 保存完了後、メインメニューと最新マップを再描画して継続操作できるようにする
        map_text = build_group_map_text(self.guild_id, self.locale)
        success_msg = get_text(str(self.locale), 'created_msg').format(name=self.group_name)
        new_view = SetGroupOpView(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{success_msg}\n\n{get_text(str(self.locale), 'menu_prompt')}"
        await interaction.response.edit_message(content=msg, view=new_view)

class AddTypeTargetView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale: discord.Locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale

        self.src_btn.label = get_text(str(locale), "btn_add_src")
        self.dest_btn.label = get_text(str(locale), "btn_add_dest")

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="📥", custom_id="src_btn")
    async def src_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelAddSelectView(self.guild_id, self.group_name, "source", self.locale)
        await interaction.response.edit_message(content=f"📁 **[{self.group_name}]** に追加する 📥 転送元チャンネルを選択してください:", view=view)

    @discord.ui.button(style=discord.ButtonStyle.success, emoji="📤", custom_id="dest_btn")
    async def dest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelAddSelectView(self.guild_id, self.group_name, "dest", self.locale)
        await interaction.response.edit_message(content=f"📁 **[{self.group_name}]** に追加する 📤 転送先チャンネルを選択してください:", view=view)

class ChannelAddSelectView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, channel_type: str, locale: discord.Locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.channel_type = channel_type
        self.locale = locale

        c_types = [discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.forum] if channel_type == "source" else [discord.ChannelType.text, discord.ChannelType.news]
        
        self.chan_select = discord.ui.ChannelSelect(
            placeholder="チャンネルを選択...",
            channel_types=c_types,
            min_values=1, max_values=1
        )
        self.chan_select.callback = self.select_callback
        self.add_item(self.chan_select)

    async def select_callback(self, interaction: discord.Interaction):
        cid = self.chan_select.values[0].id

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, ?)', (self.guild_id, self.group_name, cid, self.channel_type))
        conn.commit()
        conn.close()

        chan = bot.get_channel(cid)
        c_mention = chan.mention if chan else f"ID:{cid}"
        t_label = get_text(str(self.locale), "source" if self.channel_type == "source" else "dest")

        # 追加完了後、メインメニューと最新マップに戻して継続操作できるようにする
        map_text = build_group_map_text(self.guild_id, self.locale)
        success_msg = get_text(str(self.locale), 'added_msg').format(name=self.group_name, type=t_label, channel=c_mention)
        new_view = SetGroupOpView(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{success_msg}\n\n{get_text(str(self.locale), 'menu_prompt')}"
        await interaction.response.edit_message(content=msg, view=new_view)

class GroupSelectForDeleteView(discord.ui.View):
    def __init__(self, guild_id: int, groups: list, locale: discord.Locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale

        options = [discord.SelectOption(label=g, value=g, emoji="💥") for g in groups[:25]]
        select = discord.ui.Select(placeholder="...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        group_name = interaction.data["values"][0]

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ?', (self.guild_id, group_name))
        conn.commit()
        conn.close()

        # 削除完了後、メインメニューと最新マップに戻して継続操作できるようにする
        map_text = build_group_map_text(self.guild_id, self.locale)
        success_msg = get_text(str(self.locale), 'group_deleted').format(name=group_name)
        new_view = SetGroupOpView(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{success_msg}\n\n{get_text(str(self.locale), 'menu_prompt')}"
        await interaction.response.edit_message(content=msg, view=new_view)

# ==========================================
# 🚀 スラッシュコマンド
# ==========================================

@bot.tree.command(name="set_group", description="グループの確認・追加編集・削除を行います")
@app_commands.checks.has_permissions(administrator=True)
async def set_group(interaction: discord.Interaction):
    map_text = build_group_map_text(interaction.guild_id, interaction.locale)
    view = SetGroupOpView(interaction.guild_id, interaction.locale)
    msg = f"{map_text}\n\n{get_text(str(interaction.locale), 'menu_prompt')}"
    await interaction.response.send_message(msg, view=view, ephemeral=True)

@bot.tree.command(name="set_language", description="転送先で表示されるメッセージの言語（メイン・サブ）を設定します")
@app_commands.checks.has_permissions(administrator=True)
async def set_language(interaction: discord.Interaction):
    await send_language_menu(interaction, interaction.guild_id, interaction.locale)

@bot.tree.command(name="reset_all_settings", description="【危険】このサーバーのすべての転送グループ設定をリセットします")
@app_commands.checks.has_permissions(administrator=True)
async def reset_all_settings(interaction: discord.Interaction):
    view = ResetConfirmView(interaction.guild_id, interaction.locale)
    msg = get_text(str(interaction.locale), "reset_warning")
    await interaction.response.send_message(msg, view=view, ephemeral=True)

class ResetConfirmView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.locale = locale

        self.confirm.label = get_text(str(locale), "btn_confirm_reset")
        self.cancel.label = get_text(str(locale), "btn_cancel")

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        conn.commit()
        conn.close()

        msg = get_text(str(self.locale), "reset_complete")
        await interaction.response.edit_message(content=msg, view=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = get_text(str(self.locale), "reset_cancelled")
        await interaction.response.edit_message(content=msg, view=None)

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
        server_locale_str = str(message.guild.preferred_locale)
        actual_main = main_lang_code if main_lang_code != "default" else server_locale_str.split('-')[0].lower()
        
        title_text = get_text(actual_main, "embed_title")
        jump_url = message.jump_url
        
        desc_lines = []
        main_desc = get_text(actual_main, "embed_desc").format(
            author=message.author.display_name,
            channel=channel.name
        )
        desc_lines.append(main_desc)
        
        if sub_langs_str:
            sub_langs = sub_langs_str.split(',')
            for sl in sub_langs:
                if sl and sl != "none":
                    sl_desc = get_text(sl, "embed_desc").format(
                        author=message.author.display_name,
                        channel=channel.name
                    )
                    desc_lines.append(sl_desc)

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

bot.run(BOT_TOKEN)
