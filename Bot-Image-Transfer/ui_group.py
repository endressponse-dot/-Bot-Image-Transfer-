import sqlite3
import discord
from config import DB_FILE, DEFAULT_DELETE_AFTER_DAYS
from locales import get_text
from database import (
    add_group_channel, 
    delete_group_channel, 
    set_group_retention_days, 
    get_group_retention_days,
    build_group_map_text
)

# ==========================================
# 1. 操作選択メニュー（確認・編集・削除）
# ==========================================

class RetentionSelect(discord.ui.Select):
    def __init__(self, group_name: str, guild_id: int):
        self.group_name = group_name
        self.guild_id = guild_id
        
        options = [
            discord.SelectOption(label="1日", value="1", description="1日後にメッセージを自動削除"),
            discord.SelectOption(label="3日", value="3", description="3日後にメッセージを自動削除"),
            discord.SelectOption(label="7日 (デフォルト)", value="7", description="7日後にメッセージを自動削除"),
            discord.SelectOption(label="14日", value="14", description="14日後にメッセージを自動削除"),
            discord.SelectOption(label="30日", value="30", description="30日後にメッセージを自動削除"),
            discord.SelectOption(label="無制限 (自動削除なし)", value="0", description="自動削除を行いません"),
        ]
        super().__init__(placeholder="⏳ 画像・メッセージの保持期間を選択...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        days = int(self.values[0])
        set_group_retention_days(self.guild_id, self.group_name, days)
        days_str = f"{days}日間" if days > 0 else "無制限"
        await interaction.response.send_message(
            f"✅ グループ **{self.group_name}** の保持期間を **{days_str}** に設定しました。",
            ephemeral=True
        )


class GroupChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, action_type: str, locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.action_type = action_type  # 'add_src', 'add_dest'
        self.locale = locale

        channel_select = discord.ui.ChannelSelect(
            placeholder="対象のチャンネルまたはスレッドを選択...",
            channel_types=[
                discord.ChannelType.text,           # テキストチャンネル
                discord.ChannelType.forum,          # フォーラムチャンネル
                discord.ChannelType.public_thread,   # 公開スレッド
                discord.ChannelType.private_thread,  # 非公開スレッド
                discord.ChannelType.news,            # アナウンスチャンネル
                discord.ChannelType.news_thread      # アナウンススレッド
            ],
            min_values=1,
            max_values=1
        )
        channel_select.callback = self.channel_select_callback
        self.add_item(channel_select)

    async def channel_select_callback(self, interaction: discord.Interaction):
        selected_channel_id = interaction.data['values'][0]
        ch_type = "src" if self.action_type == "add_src" else "dest"
        
        add_group_channel(self.guild_id, self.group_name, int(selected_channel_id), ch_type)
        
        type_str = "転送元 (Source)" if ch_type == "src" else "転送先 (Dest)"
        await interaction.response.send_message(
            f"✅ グループ **{self.group_name}** の **{type_str}** に <#{selected_channel_id}> を追加しました。",
            ephemeral=True
        )


# ==========================================
# 2. グループ詳細操作・編集UI
# ==========================================

class GroupActionView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale

        # 保持期間選択ドロップダウンを追加
        self.add_item(RetentionSelect(group_name, guild_id))

    @discord.ui.button(label="📥 転送元を追加", style=discord.ButtonStyle.primary, row=1)
    async def add_source(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GroupChannelSelectView(self.guild_id, self.group_name, "add_src", self.locale)
        await interaction.response.send_message("📥 転送元に指定するチャンネルまたはスレッドを選択してください:", view=view, ephemeral=True)

    @discord.ui.button(label="📤 転送先を追加", style=discord.ButtonStyle.success, row=1)
    async def add_dest(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GroupChannelSelectView(self.guild_id, self.group_name, "add_dest", self.locale)
        await interaction.response.send_message("📤 転送先に指定するチャンネルまたはスレッドを選択してください:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ このグループを削除", style=discord.ButtonStyle.danger, row=1)
    async def delete_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        delete_group_channel(self.guild_id, self.group_name)
        await interaction.response.send_message(f"🗑️ グループ **{self.group_name}** を削除しました。", ephemeral=True)


# ==========================================
# 3. グループ選択・新規作成モーダル
# ==========================================

class NewGroupModal(discord.ui.Modal, title="新規グループ作成"):
    group_name_input = discord.ui.TextInput(
        label="グループ名",
        placeholder="例: main-group, art-forward",
        required=True,
        max_length=30
    )

    def __init__(self, guild_id: int, locale):
        super().__init__()
        self.guild_id = guild_id
        self.locale = locale

    async def on_submit(self, interaction: discord.Interaction):
        g_name = self.group_name_input.value.strip()
        view = GroupActionView(self.guild_id, g_name, self.locale)
        await interaction.response.send_message(
            f"✨ 新規グループ **{g_name}** を作成しました。続いて設定を行ってください:",
            view=view,
            ephemeral=True
        )


class GroupSelectMenu(discord.ui.Select):
    def __init__(self, guild_id: int, groups: list, locale):
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label=f"📁 {g}", value=g) for g in groups]
        options.append(discord.SelectOption(label="➕ 新しいグループを作成", value="__new__"))
        
        super().__init__(placeholder="編集するグループを選択してください...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0]
        if selected_val == "__new__":
            modal = NewGroupModal(self.guild_id, self.locale)
            await interaction.response.send_modal(modal)
        else:
            view = GroupActionView(self.guild_id, selected_val, self.locale)
            await interaction.response.send_message(
                f"⚙️ グループ **{selected_val}** の設定・編集を行います。操作を選択してください:",
                view=view,
                ephemeral=True
            )


class GroupDeleteSelectMenu(discord.ui.Select):
    def __init__(self, guild_id: int, groups: list, locale):
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label=f"🗑️ {g}", value=g) for g in groups]
        super().__init__(placeholder="削除するグループを選択してください...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0]
        delete_group_channel(self.guild_id, selected_val)
        await interaction.response.send_message(f"🗑️ グループ **{selected_val}** を削除しました。", ephemeral=True)


# ==========================================
# 4. トップレベル操作選択UI（Main Menu）
# ==========================================

class OperationSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale, bot):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

    @discord.ui.button(label="📋 設定一覧を表示", style=discord.ButtonStyle.secondary, row=0)
    async def show_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = build_group_map_text(self.guild_id, self.locale, self.bot)
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="⚙️ グループ編集・追加", style=discord.ButtonStyle.primary, row=0)
    async def edit_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        rows = c.fetchall()
        conn.close()
        
        existing_groups = [r[0] for r in rows]
        view = discord.ui.View()
        view.add_item(GroupSelectMenu(self.guild_id, existing_groups, self.locale))
        
        prompt_text = get_text(self.locale, "select_group_to_edit")
        await interaction.response.send_message(prompt_text, view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ グループ削除", style=discord.ButtonStyle.danger, row=0)
    async def delete_group_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        rows = c.fetchall()
        conn.close()
        
        existing_groups = [r[0] for r in rows]
        if not existing_groups:
            await interaction.response.send_message("❌ 削除できるグループが存在しません。", ephemeral=True)
            return

        view = discord.ui.View()
        view.add_item(GroupDeleteSelectMenu(self.guild_id, existing_groups, self.locale))
        
        prompt_text = get_text(self.locale, "select_group_to_delete")
        await interaction.response.send_message(prompt_text, view=view, ephemeral=True)


class GroupManageMainView(discord.ui.View):
    def __init__(self, guild_id: int, locale):
        super().__init__(timeout=180)
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (guild_id,))
        rows = c.fetchall()
        conn.close()
        
        existing_groups = [r[0] for r in rows]
        self.add_item(GroupSelectMenu(guild_id, existing_groups, locale))


async def send_group_management_menu(interaction: discord.Interaction, guild_id: int, locale):
    prompt_text = get_text(locale, "menu_prompt")
    view = OperationSelectView(guild_id, locale, interaction.client)
    await interaction.response.send_message(f"📁 **{prompt_text}**", view=view, ephemeral=True)
