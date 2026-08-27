import sqlite3
import discord
from config import DB_FILE
from database import get_all_group_names

# ---------------------------------------------------------
# 1. Embed生成関数（現在の設定状態を可視化）
# ---------------------------------------------------------
def create_dashboard_embed(guild_id: int, group_name: str = None) -> discord.Embed:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # グループが指定されていない場合、最初のグループを取得
    if not group_name:
        groups = get_all_group_names(guild_id)
        group_name = groups[0] if groups else "デフォルト"

    # 転送元・転送先チャンネルの取得
    c.execute('SELECT channel_id, type FROM group_channels WHERE guild_id = ? AND group_name = ?',
              (guild_id, group_name))
    channels = c.fetchall()
    
    src_channels = [f"<#{ch_id}>" for ch_id, ch_type in channels if ch_type == 'src']
    dest_channels = [f"<#{ch_id}>" for ch_id, ch_type in channels if ch_type == 'dest']

    # 昇格ルールの取得
    c.execute('SELECT emoji, threshold FROM promotion_rules WHERE guild_id = ? AND group_name = ?',
              (guild_id, group_name))
    rules = c.fetchall()

    # グループ設定（対象コンテンツ・保持期間）の取得
    c.execute('SELECT target_content, retention_days FROM group_settings WHERE guild_id = ? AND group_name = ?',
              (guild_id, group_name))
    settings = c.fetchone()
    conn.close()

    content_type = settings[0] if settings and settings[0] else "all"
    retention_days = settings[1] if settings and settings[1] is not None else 0

    content_display = {
        "all": "🌐 全メッセージ", 
        "image_only": "📷 画像のみ", 
        "text_only": "💬 テキストのみ"
    }.get(content_type, "🌐 全メッセージ")

    retention_display = f"⏳ {retention_days} 日後に自動削除" if retention_days > 0 else "♾️ 無期限保持"

    embed = discord.Embed(
        title=f"🎛️ 統合管理ダッシュボード 【 {group_name} 】",
        description="下の操作ボタンを押すことで、**現在操作中のチャンネル**に対する設定変更やルール更新が行えます。",
        color=discord.Color.blue()
    )

    embed.add_field(name="📤 転送元 (src)", value="\n".join(src_channels) if src_channels else "未設定", inline=True)
    embed.add_field(name="📥 転送先 (dest)", value="\n".join(dest_channels) if dest_channels else "未設定", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(name="📦 転送対象", value=f"**{content_display}**", inline=True)
    embed.add_field(name="🧹 保持期間", value=f"**{retention_display}**", inline=True)

    rule_text = "\n".join([f"・ リアクション {emoji} × **{thresh}個** で昇格" for emoji, thresh in rules]) if rules else "設定なし"
    embed.add_field(name="⭐ 昇格ルール", value=rule_text, inline=False)

    embed.set_footer(text="※グループを切り替えるには、再度 /setup を実行するか上の選択メニューをご利用ください")
    return embed


# ---------------------------------------------------------
# 2. モーダルクラス（新規グループ作成 & 昇格ルール追加）
# ---------------------------------------------------------
class CreateGroupModal(discord.ui.Modal, title="➕ 新しいグループの作成"):
    group_name_input = discord.ui.TextInput(
        label="グループ名",
        placeholder="例: イラスト通知, 殿堂入り, 議事録",
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        group_name = self.group_name_input.value.strip()
        guild_id = interaction.guild_id

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO group_settings (guild_id, group_name, target_content, retention_days)
            VALUES (?, ?, 'all', 0)
        ''', (guild_id, group_name))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(guild_id, group_name)
        view = RuleDashboardView(guild_id, group_name)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class AddRuleModal(discord.ui.Modal, title="⭐ 昇格ルールの追加・更新"):
    def __init__(self, guild_id: int, group_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.group_name = group_name

    emoji_input = discord.ui.TextInput(
        label="絵文字 (Emoji)",
        placeholder="例: ⭐, 🔥, ❤️ (1つ指定)",
        required=True,
        max_length=10
    )
    threshold_input = discord.ui.TextInput(
        label="必要リアクション数",
        placeholder="例: 3, 5, 10",
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        emoji_str = self.emoji_input.value.strip()
        try:
            threshold = int(self.threshold_input.value.strip())
            if threshold <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ しきい値には1以上の整数を入力してください。", ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO promotion_rules (guild_id, group_name, emoji, threshold)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, group_name, emoji) DO UPDATE SET threshold = excluded.threshold
        ''', (self.guild_id, self.group_name, emoji_str, threshold))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        view = RuleDashboardView(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=view)


class SetRetentionModal(discord.ui.Modal, title="⏳ 保持日数の設定"):
    def __init__(self, guild_id: int, group_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.group_name = group_name

    days_input = discord.ui.TextInput(
        label="自動削除までの日数 (0で無期限)",
        placeholder="例: 0 (=無効), 7, 30",
        required=True,
        max_length=4
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            days = int(self.days_input.value.strip())
            if days < 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ 0以上の整数を入力してください。", ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO group_settings (guild_id, group_name, retention_days)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, group_name) DO UPDATE SET retention_days = excluded.retention_days
        ''', (self.guild_id, self.group_name, days))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        view = RuleDashboardView(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=view)


# ---------------------------------------------------------
# 3. メインダッシュボードView（一画面コントロールパネル）
# ---------------------------------------------------------
class RuleDashboardView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name

    # --- 行 1: チャンネルトグル操作 ---
    @discord.ui.button(label="📤 このCHを転送元(src)に設定/解除", style=discord.ButtonStyle.primary, row=0)
    async def toggle_src(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = interaction.channel_id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute('SELECT 1 FROM group_channels WHERE guild_id = ? AND group_name = ? AND channel_id = ? AND type = "src"',
                  (self.guild_id, self.group_name, channel_id))
        exists = c.fetchone()

        if exists:
            c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ? AND channel_id = ? AND type = "src"',
                      (self.guild_id, self.group_name, channel_id))
        else:
            c.execute('INSERT INTO group_channels (guild_id, group_name, channel_id, type) VALUES (?, ?, ?, "src")',
                      (self.guild_id, self.group_name, channel_id))

        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📥 このCHを転送先(dest)に設定/解除", style=discord.ButtonStyle.success, row=0)
    async def toggle_dest(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = interaction.channel_id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute('SELECT 1 FROM group_channels WHERE guild_id = ? AND group_name = ? AND channel_id = ? AND type = "dest"',
                  (self.guild_id, self.group_name, channel_id))
        exists = c.fetchone()

        if exists:
            c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ? AND channel_id = ? AND type = "dest"',
                      (self.guild_id, self.group_name, channel_id))
        else:
            c.execute('INSERT INTO group_channels (guild_id, group_name, channel_id, type) VALUES (?, ?, ?, "dest")',
                      (self.guild_id, self.group_name, channel_id))

        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=self)

    # --- 行 2: フィルタ＆保持期間設定 ---
    @discord.ui.button(label="📦 対象コンテンツ切替 (全/画像/テキスト)", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_content_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute('SELECT target_content FROM group_settings WHERE guild_id = ? AND group_name = ?',
                  (self.guild_id, self.group_name))
        row = c.fetchone()
        current_type = row[0] if row and row[0] else "all"

        # 状態のサイクロート: all -> image_only -> text_only -> all
        next_type = {"all": "image_only", "image_only": "text_only", "text_only": "all"}.get(current_type, "all")

        c.execute('''
            INSERT INTO group_settings (guild_id, group_name, target_content)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, group_name) DO UPDATE SET target_content = excluded.target_content
        ''', (self.guild_id, self.group_name, next_type))

        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏳ 保持日数変更", style=discord.ButtonStyle.secondary, row=1)
    async def set_retention_days(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetRetentionModal(self.guild_id, self.group_name))

    # --- 行 3: 昇格ルール設定 & グループ削除 ---
    @discord.ui.button(label="⭐ 昇格ルール追加/更新", style=discord.ButtonStyle.primary, row=2)
    async def add_promotion_rule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddRuleModal(self.guild_id, self.group_name))

    @discord.ui.button(label="🗑️ 昇格ルール全消去", style=discord.ButtonStyle.danger, row=2)
    async def clear_promotion_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM promotion_rules WHERE guild_id = ? AND group_name = ?',
                  (self.guild_id, self.group_name))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ このグループを削除", style=discord.ButtonStyle.danger, row=3)
    async def delete_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ?', (self.guild_id, self.group_name))
        c.execute('DELETE FROM group_settings WHERE guild_id = ? AND group_name = ?', (self.guild_id, self.group_name))
        c.execute('DELETE FROM promotion_rules WHERE guild_id = ? AND group_name = ?', (self.guild_id, self.group_name))
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"🗑️ グループ **「{self.group_name}」** とそれに関連する全設定を削除しました。",
            embed=None,
            view=None
        )
