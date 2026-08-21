import sqlite3
import discord
from config import DB_FILE
from locales import LANG_MAP

class LanguageSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

        # LANG_MAPから12言語の選択肢（SelectOption）を自動生成
        main_opts = []
        for code, (flag, name_local, name_en) in LANG_MAP.items():
            label = f"{flag} {name_local} ({name_en})"
            main_opts.append(discord.SelectOption(label=label, value=code, emoji=flag))

        # 自動判別の選択肢を先頭に追加
        main_opts.insert(0, discord.SelectOption(
            label="🌐 自動 (Discordのサーバー設定に従う)",
            value="default",
            description="Discordの標準言語設定を適用します"
        ))
        
        main_select = discord.ui.Select(
            placeholder="メイン表示言語を選択してください...",
            min_values=1,
            max_values=1,
            options=main_opts,
            custom_id="sel_main_lang"
        )
        main_select.callback = self.main_callback
        self.add_item(main_select)

    async def main_callback(self, interaction: discord.Interaction):
        selected_lang = interaction.data['values'][0]
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO guild_languages (guild_id, main_lang, sub_langs)
            VALUES (?, ?, '')
            ON CONFLICT(guild_id) DO UPDATE SET main_lang = excluded.main_lang
        ''', (self.guild_id, selected_lang))
        conn.commit()
        conn.close()

        flag_str = LANG_MAP.get(selected_lang, ("🌐", "", ""))[0]
        await interaction.response.edit_message(
            content=f"✅ メイン言語を `{flag_str} {selected_lang}` に設定しました。",
            view=None
        )

async def send_language_menu(interaction: discord.Interaction, guild_id: int, locale):
    view = LanguageSelectView(guild_id)
    await interaction.response.send_message("🌐 **転送メッセージで使用するメイン言語を選択してください:**", view=view, ephemeral=True)
