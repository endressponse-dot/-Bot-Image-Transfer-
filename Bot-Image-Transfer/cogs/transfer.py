import discord
from discord.ext import commands
import database

class TransferCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==========================================
    # 1. 通常のメッセージ転送処理
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        groups = database.get_all_groups()
        
        for group in groups:
            if message.channel.id in group["src_channels"]:
                # C案テキストレイアウト
                content = (
                    f"👤 **{message.author.display_name}** in <#{message.channel.id}>\n"
                    f"↗️ [Original]({message.jump_url})"
                )
                
                if message.content:
                    content += f"\n\n{message.content}"

                # Originalへジャンプするボタン
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Original Message", 
                    url=message.jump_url, 
                    style=discord.ButtonStyle.link
                ))

                # 添付ファイルの複製
                files = []
                for attachment in message.attachments:
                    files.append(await attachment.to_file())

                # 転送先チャンネルへ送信
                for dest_id in group["dest_channels"]:
                    dest_channel = self.bot.get_channel(dest_id)
                    if not dest_channel:
                        try:
                            dest_channel = await self.bot.fetch_channel(dest_id)
                        except discord.NotFound:
                            continue
                    
                    if dest_channel:
                        await dest_channel.send(content=content, files=files, view=view)

    # ==========================================
    # 2. 自動昇格（リアクション検知）処理
    # ==========================================
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        # DBからチャンネルの昇格設定を取得
        config = database.get_promotion_config(payload.channel_id)
        if not config:
            return

        # リアクションの絵文字をチェック
        if str(payload.emoji) != config["emoji"]:
            return

        # 既に昇格済みかチェック（重複防止）
        if database.is_message_promoted(payload.message_id):
            return

        # チャンネル・メッセージの取得
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.NotFound:
                return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # リアクション数のカウント
        reaction_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == config["emoji"]:
                reaction_count = reaction.count
                break

        # しきい値達成時の昇格処理
        if reaction_count >= config["threshold"]:
            # DBに昇格済みとして記録
            database.mark_message_as_promoted(payload.message_id, payload.guild_id, payload.channel_id)

            # 昇格先チャンネルの取得
            target_channel = self.bot.get_channel(config["dest_channel_id"])
            if not target_channel:
                try:
                    target_channel = await self.bot.fetch_channel(config["dest_channel_id"])
                except discord.NotFound:
                    print(f"❌ 昇格先チャンネル ({config['dest_channel_id']}) が見つかりませんでした。")
                    return

            # C案レイアウト (昇格ヘッダー付き)
            content = (
                f"🌟 **Promoted Content** ({config['emoji']} x{reaction_count})\n"
                f"👤 **{message.author.display_name}** in <#{message.channel.id}>\n"
                f"↗️ [Original]({message.jump_url})"
            )
            
            if message.content:
                content += f"\n\n{message.content}"

            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Original Message", 
                url=message.jump_url, 
                style=discord.ButtonStyle.link
            ))

            files = []
            for attachment in message.attachments:
                files.append(await attachment.to_file())

            await target_channel.send(content=content, files=files, view=view)
            print(f"✨ メッセージ {message.id} を <#{target_channel.id}> へ自動昇格しました。")

async def setup(bot: commands.Bot):
    await bot.add_cog(TransferCog(bot))
