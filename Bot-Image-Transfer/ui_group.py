import discord
from locales import get_text
from database import (
    get_guild_groups, build_group_map_text, add_group_channel, delete_group
)

class SetGroupOpView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale, bot_client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot_client = bot_client

        self.add_btn.label = get_text(str(locale), "btn_add")
        self.del_btn.label = get_text(str(locale), "btn_del")
        self.close_btn.label = "メニューを閉じる"

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="✏️", custom_id="add_btn", row=0)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        groups = get_guild_groups(self.guild_id)
        view = GroupSelectForEditView(self.guild_id, groups, self.locale, self.bot_client)
        map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_edit_group')}"
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="del_btn", row=0)
    async def del_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        groups = get_guild_groups(self.guild_id)
        if not groups:
            map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
            await interaction.response.edit_message(content=map_text, view=self)
            return

        view = GroupSelectForDeleteView(self.guild_id, groups, self.locale, self.bot_client)
        map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_del_group')}"
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="✖️", custom_id="close_btn", row=1)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
        await interaction.response.edit_message(content=f"{map_text}\n\n🔒 設定メニューを終了しました。", view=None)

class GroupSelectForEditView(discord.ui.View):
    def __init__(self, guild_id: int, groups: list, locale: discord.Locale, bot_client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot_client = bot_client

        options = [discord.SelectOption(label=get_text(str(locale), "new_group_option"), value="__NEW__", emoji="➕")]
        options.extend([discord.SelectOption(label=g, value=g, emoji="📁") for g in groups[:24]])

        select = discord.ui.Select(placeholder="...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        if selected == "__NEW__":
            modal = NewGroupModal(self.guild_id, self.locale, self.bot_client)
            await interaction.response.send_modal(modal)
            map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
            view = SetGroupOpView(self.guild_id, self.locale, self.bot_client)
            await interaction.message.edit(content=f"{map_text}\n\n{get_text(str(self.locale), 'menu_prompt')}", view=view)
        else:
            view = AddTypeTargetView(self.guild_id, selected, self.locale, self.bot_client)
            map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
            msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_target_type').format(name=selected)}"
            await interaction.response.edit_message(content=msg, view=view)

class NewGroupModal(discord.ui.Modal):
    def __init__(self, guild_id: int, locale: discord.Locale, bot_client):
        super().__init__(title=get_text(str(locale), "modal_new_title"))
        self.guild_id = guild_id
        self.locale = locale
        self.bot_client = bot_client

        self.group_name_input = discord.ui.TextInput(
            label=get_text(str(locale), "modal_gname_label"),
            placeholder="Ex: Group-A",
            required=True
        )
        self.add_item(self.group_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        gname = self.group_name_input.value.strip()
        view = NewGroupChannelSelectView(self.guild_id, gname, self.locale, self.bot_client)
        msg = f"📁 **[{gname}]** の転送元（📥）と転送先（📤）チャンネルを選択してください。"
        await interaction.response.send_message(content=msg, view=view, ephemeral=True)

class NewGroupChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale: discord.Locale, bot_client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale
        self.bot_client = bot_client
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

        add_group_channel(self.guild_id, self.group_name, self.selected_src, "source")
        add_group_channel(self.guild_id, self.group_name, self.selected_dest, "dest")

        map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
        success_msg = get_text(str(self.locale), 'created_msg').format(name=self.group_name)
        new_view = SetGroupOpView(self.guild_id, self.locale, self.bot_client)
        msg = f"{map_text}\n\n{success_msg}\n\n{get_text(str(self.locale), 'menu_prompt')}"
        await interaction.response.edit_message(content=msg, view=new_view)

class AddTypeTargetView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale: discord.Locale, bot_client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale
        self.bot_client = bot_client

        self.src_btn.label = get_text(str(locale), "btn_add_src")
        self.dest_btn.label = get_text(str(locale), "btn_add_dest")

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="📥", custom_id="src_btn")
    async def src_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelAddSelectView(self.guild_id, self.group_name, "source", self.locale, self.bot_client)
        await interaction.response.edit_message(content=f"📁 **[{self.group_name}]** に追加する 📥 転送元チャンネルを選択してください:", view=view)

    @discord.ui.button(style=discord.ButtonStyle.success, emoji="📤", custom_id="dest_btn")
    async def dest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelAddSelectView(self.guild_id, self.group_name, "dest", self.locale, self.bot_client)
        await interaction.response.edit_message(content=f"📁 **[{self.group_name}]** に追加する 📤 転送先チャンネルを選択してください:", view=view)

class ChannelAddSelectView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, channel_type: str, locale: discord.Locale, bot_client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.channel_type = channel_type
        self.locale = locale
        self.bot_client = bot_client

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
        add_group_channel(self.guild_id, self.group_name, cid, self.channel_type)

        chan = self.bot_client.get_channel(cid)
        c_mention = chan.mention if chan else f"ID:{cid}"
        t_label = get_text(str(self.locale), "source" if self.channel_type == "source" else "dest")

        map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
        success_msg = get_text(str(self.locale), 'added_msg').format(name=self.group_name, type=t_label, channel=c_mention)
        new_view = SetGroupOpView(self.guild_id, self.locale, self.bot_client)
        msg = f"{map_text}\n\n{success_msg}\n\n{get_text(str(self.locale), 'menu_prompt')}"
        await interaction.response.edit_message(content=msg, view=new_view)

class GroupSelectForDeleteView(discord.ui.View):
    def __init__(self, guild_id: int, groups: list, locale: discord.Locale, bot_client):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot_client = bot_client

        options = [discord.SelectOption(label=g, value=g, emoji="💥") for g in groups[:25]]
        select = discord.ui.Select(placeholder="...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        group_name = interaction.data["values"][0]
        delete_group(self.guild_id, group_name)

        map_text = build_group_map_text(self.guild_id, self.locale, self.bot_client)
        success_msg = get_text(str(self.locale), 'group_deleted').format(name=group_name)
        new_view = SetGroupOpView(self.guild_id, self.locale, self.bot_client)
        msg = f"{map_text}\n\n{success_msg}\n\n{get_text(str(self.locale), 'menu_prompt')}"
        await interaction.response.edit_message(content=msg, view=new_view)