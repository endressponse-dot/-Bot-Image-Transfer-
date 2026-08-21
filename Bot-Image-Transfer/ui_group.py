import sqlite3
import discord
from config import DB_FILE
from locales import get_text
from database import build_group_map_text, add_group_channel, delete_group_channel, set_group_description
from ui_retention import RetentionSelectView

class SetGroupOpView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale, bot: discord.Client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

    @discord.ui.button(label="＋ 追加・編集", style=discord.ButtonStyle.primary, custom_id="grp_add_edit")
    async def add_edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        groups = [row[0] for row in c.fetchall()]
        conn.close()

        if not groups:
            modal = GroupNameModal(self.guild_id, self.locale, self.bot)
            await interaction.response.send_modal(modal)
        else:
            view = GroupSelectForEditView(self.guild_id, self.locale, self.bot, groups)
            msg = get_text(str(self.locale), "select_group_to_edit")
            await interaction.response.send_message(msg, view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ グループ削除", style=discord.ButtonStyle.danger, custom_id="grp_delete")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        groups = [row[0] for row in c.fetchall()]
        conn.close()

        if not groups:
            await interaction.response.send_message("削除できるグループがありません。", ephemeral=True)
            return

        view = GroupSelectForDeleteView(self.guild_id, self.locale, self.bot, groups)
        msg = get_text(str(self.locale), "select_group_to_delete")
        await interaction.response.send_message(msg, view=view, ephemeral=True)


class GroupSelectForEditView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale, bot: discord.Client, groups: list):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

        options = [discord.SelectOption(label=g, value=g) for g in groups[:24]]
        options.append(discord.SelectOption(label="＋ 新しいグループを作成", value="__NEW__", description="新しくグループ名を指定して作成します"))

        select = discord.ui.Select(placeholder="グループを選択してください...", min_values=1, max_values=1, options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_value = interaction.data['values'][0]

        if selected_value == "__NEW__":
            modal = GroupNameModal(self.guild_id, self.locale, self.bot)
            await interaction.response.send_modal(modal)
        else:
            view = EditGroupDetailView(self.guild_id, self.locale, self.bot, selected_value)
            map_text = build_group_map_text(self.guild_id, self.locale, self.bot)
            msg = f"{map_text}\n\n【 **{selected_value}** 】の設定を変更中:"
            await interaction.response.edit_message(content=msg, view=view)


class GroupNameModal(discord.ui.Modal):
    def __init__(self, guild_id: int, locale: discord.Locale, bot: discord.Client):
        super().__init__(title="グループ新規作成")
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

        self.group_name_input = discord.ui.TextInput(
            label="グループ名",
            placeholder="例: main-images, art-share など",
            required=True,
            max_length=30
        )
        self.add_item(self.group_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        group_name = self.group_name_input.value.strip()
        view = EditGroupDetailView(self.guild_id, self.locale, self.bot, group_name)
        map_text = build_group_map_text(self.guild_id, self.locale, self.bot)
        msg = f"{map_text}\n\n【 **{group_name}** 】の設定編集:"
        await interaction.response.send_message(msg, view=view, ephemeral=True)


class EditGroupDetailView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale, bot: discord.Client, group_name: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot
        self.group_name = group_name

        # 転送元選択
        src_select = discord.ui.ChannelSelect(
            placeholder="転送元 (Source) チャンネルを選択",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.public_thread, discord.ChannelType.private_thread],
            min_values=0, max_values=1, custom_id="select_src"
        )
        src_select.callback = self.src_callback
        self.add_item(src_select)

        # 転送先選択
        dest_select = discord.ui.ChannelSelect(
            placeholder="転送先 (Destination) チャンネルを選択",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.public_thread, discord.ChannelType.private_thread],
            min_values=0, max_values=1, custom_id="select_dest"
        )
        dest_select.callback = self.dest_callback
        self.add_item(dest_select)

    async def src_callback(self, interaction: discord.Interaction):
        selected_channels = interaction.data.get('values', [])
        if selected_channels:
            ch_id = int(selected_channels[0])
            add_group_channel(self.guild_id, self.group_name, ch_id, "source")
        
        map_text = build_group_map_text(self.guild_id, self.locale, self.bot)
        await interaction.response.edit_message(content=f"{map_text}\n\n【 **{self.group_name}** 】の設定を変更しました。", view=self)

    async def dest_callback(self, interaction: discord.Interaction):
        selected_channels = interaction.data.get('values', [])
        if selected_channels:
            ch_id = int(selected_channels[0])
            add_group_channel(self.guild_id, self.group_name, ch_id, "dest")

        map_text = build_group_map_text(self.guild_id, self.locale, self.bot)
        await interaction.response.edit_message(content=f"{map_text}\n\n【 **{self.group_name}** 】の設定を変更しました。", view=self)

    @discord.ui.button(label="⏳ 保持日数（自動削除）設定", style=discord.ButtonStyle.primary, custom_id="btn_retention")
    async def retention_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RetentionSelectView(self.guild_id, self.group_name, self.locale, self.bot)
        msg = get_text(str(self.locale), "retention_prompt")
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    @discord.ui.button(label="📝 メモを変更", style=discord.ButtonStyle.secondary, custom_id="btn_desc")
    async def desc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GroupDescModal(self.guild_id, self.group_name, self.locale, self.bot)
        await interaction.response.send_modal(modal)


class GroupDescModal(discord.ui.Modal):
    def __init__(self, guild_id: int, group_name: str, locale: discord.Locale, bot: discord.Client):
        super().__init__(title=f"【{group_name}】のメモ編集")
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale
        self.bot = bot

        self.desc_input = discord.ui.TextInput(
            label="メモ・説明文",
            placeholder="例: イラスト自動転送用グループ",
            required=False,
            max_length=100
        )
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction):
        desc = self.desc_input.value.strip()
        set_group_description(self.guild_id, self.group_name, desc)
        map_text = build_group_map_text(self.guild_id, self.locale, self.bot)
        await interaction.response.send_message(f"メモを更新しました！\n\n{map_text}", ephemeral=True)


class GroupSelectForDeleteView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale, bot: discord.Client, groups: list):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

        options = [discord.SelectOption(label=g, value=g) for g in groups[:25]]
        select = discord.ui.Select(placeholder="削除するグループを選択してください...", min_values=1, max_values=1, options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_group = interaction.data['values'][0]
        delete_group_channel(self.guild_id, selected_group)

        map_text = build_group_map_text(self.guild_id, self.locale, self.bot)
        msg = f"🗑️ グループ【 **{selected_group}** 】を削除しました。\n\n{map_text}"
        await interaction.response.edit_message(content=msg, view=None)
