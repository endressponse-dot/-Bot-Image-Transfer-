import discord
from locales import get_text
from database import reset_guild_settings

class ResetConfirmView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.locale = locale

        self.confirm.label = get_text(str(locale), "btn_confirm_reset")
        self.cancel.label = get_text(str(locale), "btn_cancel")

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        reset_guild_settings(self.guild_id)
        msg = get_text(str(self.locale), "reset_complete")
        await interaction.response.edit_message(content=msg, view=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = get_text(str(self.locale), "reset_cancelled")
        await interaction.response.edit_message(content=msg, view=None)