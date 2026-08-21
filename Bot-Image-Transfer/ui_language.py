import discord
from locales import LANG_MAP, get_text, get_lang_display
from database import get_guild_language_setting, set_guild_main_lang, set_guild_sub_langs

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
        set_guild_main_lang(self.guild_id, selected_lang)
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
        set_guild_sub_langs(self.guild_id, sub_langs_str)
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