import discord
from discord import app_commands
from discord.ext import commands
import database
from ui_group import GroupMenuView, GroupDeleteView, PromotionSetupView

class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="group_setup", description="転送グループを新規作成・設定します")
    @app_commands.default_permissions(administrator=True)
    async def group_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ 転送グループ設定",
            description="転送元、転送先、および保持期間を選択して保存してください。",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=GroupMenuView(), ephemeral=True)

    @app_commands.command(name="group_delete", description="作成済みの転送グループを削除します")
    @app_commands.default_permissions(administrator=True)
    async def group_delete(self, interaction: discord.Interaction):
        groups = database.get_all_groups()
        if not groups:
            await interaction.response.send_message("❌ 削除できるグループが存在しません。", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗑️ 転送グループ削除",
            description="削除したいグループをメニューから選択してください。",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=GroupDeleteView(groups), ephemeral=True)

    @app_commands.command(name="promote_setup", description="自動昇格（画展連携）ルールを設定します")
    @app_commands.default_permissions(administrator=True)
    async def promote_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌟 自動昇格（画展連携）設定パネル",
            description=(
                "特定のチャンネルで一定数のリアクション（⭐など）がついた投稿を、"
                "自動的に「画展」や「作品ギャラリー」へ昇格・転送する設定を行います。\n\n"
                "1️⃣ **監視する転送元** を選択\n"
                "2️⃣ **昇格先（画展チャンネル）** を選択\n"
                "3️⃣ **条件を入力して設定保存** を押す"
            ),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, view=PromotionSetupView(), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
