import discord
from discord import app_commands
from discord.ext import commands
import database
from ui_group import GroupMenuView, GroupDeleteView, PromotionSetupView

# ---------------------------------------------------------
# 絵文字選択ドロップダウンUI
# ---------------------------------------------------------
class EmojiSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild, current_emoji: str = "⭐"):
        super().__init__(timeout=180)
        
        options = [
            discord.SelectOption(
                label="全絵文字（どの絵文字でも1人1カウント）", 
                value="ANY_EMOJI", 
                description="押された絵文字の種類を問わず、ユニーク人数をカウントします",
                emoji="🌟"
            ),
            discord.SelectOption(label="⭐ スター", value="⭐", emoji="⭐"),
            discord.SelectOption(label="👍 いいね", value="👍", emoji="👍"),
            discord.SelectOption(label="❤️ ハート", value="❤️", emoji="❤️"),
        ]
        
        # サーバーのカスタム絵文字（スタンプ候補）を最大20個追加
        if guild and guild.emojis:
            for emoji in guild.emojis[:20]:
                options.append(
                    discord.SelectOption(
                        label=emoji.name,
                        value=str(emoji),
                        emoji=emoji
                    )
                )

        select = discord.ui.Select(
            placeholder="自動昇格の対象にする絵文字を選択...",
            min_values=1,
            max_values=1,
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_emoji = interaction.data["values"][0]
        # ※ ui_group.py や database.py 側の保持変数等へ一時保存・更新する処理を行う
        display_name = "全絵文字（1人1カウント）" if selected_emoji == "ANY_EMOJI" else selected_emoji
        await interaction.response.send_message(f"✅ 対象絵文字を `{display_name}` に設定しました。", ephemeral=True)


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
                "特定のチャンネルで一定数のリアクションがついた投稿を、"
                "自動的に「画展」や「作品ギャラリー」へ昇格・転送する設定を行います。\n\n"
                "1️⃣ **監視する転送元** を選択\n"
                "2️⃣ **昇格先（画展チャンネル）** を選択\n"
                "3️⃣ **対象スタンプ・しきい値** を設定して保存"
            ),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, view=PromotionSetupView(), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
