import discord
import sqlite3
from config import DB_FILE, DEFAULT_DELETE_AFTER_DAYS
from database import (
    build_group_map_text,
    get_all_group_names,
    add_group_channel,
    delete_group_channel,
    set_group_description,
    set_group_retention_days
)

# ==========================================
# 1. 外部呼び出し用エントリーポイント
# ==========================================

async def send_group_management_menu(interaction: discord.Interaction, guild_id: int, locale):
    """
    /config コマンドなどから呼び出されるメインパネル送信関数
    """
    embed = discord.Embed(
        title="⚙️ 転送グループ管理パネル",
        description="下のボタンを選択してグループの設定を行ってください。",
        color=discord.Color.blue()
    )
    view = GroupActionView(guild_id, locale)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================
# 2. メイン操作ボタンビュー (GroupActionView)
# ==========================================

class GroupActionView(discord.ui.View):
    def __init__(self, guild_id: int, locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale

    @discord.ui.button(label="📋 一覧表示", style=discord.ButtonStyle.secondary, row=0)
    async def show_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = build_group_map_text(self.guild_id, self.locale)
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="➕ チャンネル追加", style=discord.ButtonStyle.success, row=0)
    async def add_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AddChannelSelectView(self.guild_id, self.locale)
        await interaction.response.send_message("登録するチャンネルを選択してください:", view=view, ephemeral=True)

    @discord.ui.button(label="✏️ 説明文設定", style=discord.ButtonStyle.primary, row=1)
    async def set_desc(self, interaction: discord.Interaction, button: discord.ui.Button):
        groups = get_all_group_names(self.guild_id)
        if not groups:
            await interaction.response.send_message("❌ 設定可能なグループが存在しません。", ephemeral=True)
            return
        view = SelectGroupForModalView(self.guild_id, self.locale, action_type="desc")
        await interaction.response.send_message("説明文を設定するグループを選択してください:", view=view, ephemeral=True)

    @discord.ui.button(label="⏳ 保持期間設定", style=discord.ButtonStyle.primary, row=1)
    async def set_retention(self, interaction: discord.Interaction, button: discord.ui.Button):
        groups = get_all_group_names(self.guild_id)
        if not groups:
            await interaction.response.send_message("❌ 設定可能なグループが存在しません。", ephemeral=True)
            return
        view = SelectGroupForRetentionView(self.guild_id, self.locale)
        await interaction.response.send_message("保持期間を設定するグループを選択してください:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ グループ削除", style=discord.ButtonStyle.danger, row=2)
    async def delete_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        groups = get_all_group_names(self.guild_id)
        if not groups:
            await interaction.response.send_message("❌ 削除可能なグループが存在しません。", ephemeral=True)
            return
        view = GroupDeleteSelectView(self.guild_id, self.locale)
        await interaction.response.send_message("削除するグループを選択してください:", view=view, ephemeral=True)


# ==========================================
# 3. チャンネル追加フロー (UI View & Select)
# ==========================================

class AddChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale

        # チャンネル選択メニュー
        self.add_item(discord.ui.ChannelSelect(
            placeholder="対象のチャンネルを選択...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.forum, discord.ChannelType.news],
            custom_id="select_channel"
        ))

    @discord.ui.select(custom_id="select_channel")
    async def channel_selected(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        selected_channel = select.values[0]
        # 次に転送種別（転送元 or 転送先）を選択するビューへ移行
        view = AddChannelTypeView(self.guild_id, self.locale, selected_channel.id)
        await interaction.response.send_message(
            f"チャンネル <#{selected_channel.id}> の転送種別を選択してください:", 
            view=view, 
            ephemeral=True
        )


class AddChannelTypeView(discord.ui.View):
    def __init__(self, guild_id: int, locale, channel_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        self.channel_id = channel_id

    @discord.ui.button(label="📥 転送元 (Source)", style=discord.ButtonStyle.primary)
    async def select_src(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GroupInputModal(self.guild_id, self.locale, self.channel_id, "src"))

    @discord.ui.button(label="📤 転送先 (Dest)", style=discord.ButtonStyle.success)
    async def select_dest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GroupInputModal(self.guild_id, self.locale, self.channel_id, "dest"))


class GroupInputModal(discord.ui.Modal):
    def __init__(self, guild_id: int, locale, channel_id: int, ch_type: str):
        super().__init__(title="グループ名の入力")
        self.guild_id = guild_id
        self.locale = locale
        self.channel_id = channel_id
        self.ch_type = ch_type

        self.group_name_input = discord.ui.TextInput(
            label="グループ名",
            placeholder="例: main-art, announcements",
            required=True,
            max_length=50
        )
        self.add_item(self.group_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        group_name = self.group_name_input.value.strip()
        add_group_channel(self.guild_id, group_name, self.channel_id, self.ch_type)
        
        # 修正：bot 引数を除外してテキスト取得
        updated_text = build_group_map_text(self.guild_id, self.locale)
        await interaction.response.send_message(
            f"✅ チャンネル <#{self.channel_id}> をグループ `{group_name}` の `{self.ch_type}` に追加しました！\n\n{updated_text}",
            ephemeral=True
        )


# ==========================================
# 4. 説明文設定モーダル & 選択ビュー
# ==========================================

class SelectGroupForModalView(discord.ui.View):
    def __init__(self, guild_id: int, locale, action_type: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        self.action_type = action_type

        groups = get_all_group_names(guild_id)
        options = [discord.SelectOption(label=g, value=g) for g in groups[:25]]

        select = discord.ui.Select(placeholder="グループを選択してください...", options=options)
        select.callback = self.group_selected
        self.add_item(select)

    async def group_selected(self, interaction: discord.Interaction):
        group_name = interaction.data["values"][0]
        if self.action_type == "desc":
            await interaction.response.send_modal(DescriptionModal(self.guild_id, self.locale, group_name))


class DescriptionModal(discord.ui.Modal):
    def __init__(self, guild_id: int, locale, group_name: str):
        super().__init__(title=f"説明文設定: {group_name}")
        self.guild_id = guild_id
        self.locale = locale
        self.group_name = group_name

        self.desc_input = discord.ui.TextInput(
            label="グループの説明文",
            style=discord.TextStyle.paragraph,
            placeholder="このグループの用途を入力してください",
            required=False,
            max_length=200
        )
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction):
        desc = self.desc_input.value.strip()
        set_group_description(self.guild_id, self.group_name, desc)
        
        # 修正：bot 引数を除外
        updated_text = build_group_map_text(self.guild_id, self.locale)
        await interaction.response.send_message(
            f"✅ グループ `{self.group_name}` の説明文を更新しました。\n\n{updated_text}",
            ephemeral=True
        )


# ==========================================
# 5. 保持期間設定ビュー & ドロップダウン
# ==========================================

class SelectGroupForRetentionView(discord.ui.View):
    def __init__(self, guild_id: int, locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale

        groups = get_all_group_names(guild_id)
        options = [discord.SelectOption(label=g, value=g) for g in groups[:25]]

        select = discord.ui.Select(placeholder="グループを選択してください...", options=options)
        select.callback = self.group_selected
        self.add_item(select)

    async def group_selected(self, interaction: discord.Interaction):
        group_name = interaction.data["values"][0]
        view = RetentionSelectView(self.guild_id, self.locale, group_name)
        await interaction.response.send_message(
            f"グループ `{group_name}` のメッセージ保持期間を選択してください:",
            view=view,
            ephemeral=True
        )


class RetentionSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale, group_name: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        self.group_name = group_name

        options = [
            discord.SelectOption(label="無制限 (自動削除なし)", value="0"),
            discord.SelectOption(label="1日間", value="1"),
            discord.SelectOption(label="3日間", value="3"),
            discord.SelectOption(label="7日間 (デフォルト)", value="7"),
            discord.SelectOption(label="14日間", value="14"),
            discord.SelectOption(label="30日間", value="30"),
        ]

        select = discord.ui.Select(placeholder="保持日数を選択...", options=options)
        select.callback = self.retention_selected
        self.add_item(select)

    async def retention_selected(self, interaction: discord.Interaction):
        days = int(interaction.data["values"][0])
        set_group_retention_days(self.guild_id, self.group_name, days)
        
        # 修正：bot 引数を除外
        updated_text = build_group_map_text(self.guild_id, self.locale)
        days_str = f"{days}日間" if days > 0 else "無制限"
        await interaction.response.send_message(
            f"✅ グループ `{self.group_name}` の保持期間を `{days_str}` に設定しました。\n\n{updated_text}",
            ephemeral=True
        )


# ==========================================
# 6. グループ削除フロー (UI View & Select)
# ==========================================

class GroupDeleteSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale

        groups = get_all_group_names(guild_id)
        options = [discord.SelectOption(label=g, value=g) for g in groups[:25]]

        select = discord.ui.Select(placeholder="削除するグループを選択...", options=options)
        select.callback = self.group_selected
        self.add_item(select)

    async def group_selected(self, interaction: discord.Interaction):
        group_name = interaction.data["values"][0]
        delete_group_channel(self.guild_id, group_name)
        
        # 修正：bot 引数を除外
        updated_text = build_group_map_text(self.guild_id, self.locale)
        await interaction.response.send_message(
            f"🗑️ グループ `{group_name}` を削除しました。\n\n{updated_text}",
            ephemeral=True
        )


# ==========================================
# 7. `/ops` コマンド用 ドロップダウン操作ビュー
# ==========================================

class OperationSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale

        options = [
            discord.SelectOption(label="📋 設定一覧の表示", value="list", description="現在の転送設定を表示します"),
            discord.SelectOption(label="➕ チャンネルの追加", value="add", description="転送元/転送先チャンネルを追加します"),
            discord.SelectOption(label="✏️ 説明文の設定", value="desc", description="グループの用途説明を設定します"),
            discord.SelectOption(label="⏳ 保持期間の設定", value="retention", description="メッセージの自動削除期間を設定します"),
            discord.SelectOption(label="🗑️ グループの削除", value="delete", description="グループ設定を削除します"),
        ]

        select = discord.ui.Select(placeholder="実行したい操作を選択してください...", options=options)
        select.callback = self.operation_selected
        self.add_item(select)

    async def operation_selected(self, interaction: discord.Interaction):
        val = interaction.data["values"][0]

        if val == "list":
            # 修正：bot 引数を除外
            text = build_group_map_text(self.guild_id, self.locale)
            await interaction.response.send_message(text, ephemeral=True)
        elif val == "add":
            view = AddChannelSelectView(self.guild_id, self.locale)
            await interaction.response.send_message("登録するチャンネルを選択してください:", view=view, ephemeral=True)
        elif val == "desc":
            view = SelectGroupForModalView(self.guild_id, self.locale, action_type="desc")
            await interaction.response.send_message("説明文を設定するグループを選択してください:", view=view, ephemeral=True)
        elif val == "retention":
            view = SelectGroupForRetentionView(self.guild_id, self.locale)
            await interaction.response.send_message("保持期間を設定するグループを選択してください:", view=view, ephemeral=True)
        elif val == "delete":
            view = GroupDeleteSelectView(self.guild_id, self.locale)
            await interaction.response.send_message("削除するグループを選択してください:", view=view, ephemeral=True)
