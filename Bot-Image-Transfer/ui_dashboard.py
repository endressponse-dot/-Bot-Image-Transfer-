import sqlite3
import discord
from config import DB_FILE
from database import get_all_group_names

# ---------------------------------------------------------
# Embed（ダッシュボード画面）の生成
# ---------------------------------------------------------
def create_dashboard_embed(guild_id: int, group_name: str) -> discord.Embed:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 転送元・転送先チャンネルの取得
    c.execute('SELECT channel_id, type FROM group_channels WHERE guild_id = ? AND group_name = ?',
              (guild_id, group_name))
    channels = c.fetchall()
    
    src_channels = [f"<#{ch_id}>" for ch_id, ch_type in channels if ch_type == 'src']
    dest_channels = [f"<#{ch_id}>" for ch_id, ch_type in channels if ch_type == 'dest']

    # 2. 昇格ルール・コンテンツ・保持日数の取得
    c.execute('SELECT emoji, threshold FROM promotion_rules WHERE guild_id = ? AND group_name = ?',
              (guild_id, group_name))
    rules = c.fetchall()

    c.execute('SELECT target_content, retention_days FROM group_settings WHERE guild_id = ? AND group_name = ?',
              (guild_id, group_name))
    settings = c.fetchone()
    conn.close()

    content_type = settings[0] if settings and settings[0] else "all"
    retention_days = settings[1] if settings and settings[1] is not None else 0

    content_display = {
        "all": "全メッセージ（テキスト＋画像）",
        "image_only": "📷 画像・添付ファイルのみ",
        "text_only": "💬 テキストのみ"
    }.get(content_type, "全メッセージ")

    retention_display = f"{retention_days} 日後に自動削除" if retention_days > 0 else "無期限保持（削除しない）"

    # Embed の構築
    embed = discord.Embed(
        title=f"⚙️ グループ設定ダッシュボード: 【 {group_name} 】",
        description="このグループの転送チャンネルおよび各種ルールを本画面で一元管理します。",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📤 転送元 (送信元チャンネル)",
        value="\n".join(src_channels) if src_channels else "未設定（※このチャンネルでボタンを押して設定）",
        inline=True
    )
    embed.add_field(
        name="📥 転送先 (集約チャンネル)",
        value="\n".join(dest_channels) if dest_channels else "未設定（※このチャンネルでボタンを押して設定）",
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=False) # 改行スペーサー

    embed.add_field(name="📦 転送対象コンテンツ", value=f"**{content_display}**", inline=True)
    embed.add_field(name="⏳ 転送先での保持期間", value=f"**{retention_display}**", inline=True)

    rule_text = "\n".join([f"・ リアクション {emoji} × **{thresh}個** で転送先へ昇格" for emoji, thresh in rules]) if rules else "設定なし"
    embed.add_field(name="⭐ 殿堂入り・自動昇格ルール", value=rule_text, inline=False)

    embed.set_footer(text="下のボタンを押して、現在のチャンネルを転送元/転送先に設定・解除できます")
    return embed


# ---------------------------------------------------------
# モーダル: グループ新規作成
# ---------------------------------------------------------
class CreateGroupModal(discord.ui.Modal, title="➕ 新しいグループの作成"):
    group_name_input = discord.ui.TextInput(
        label="グループ名",
        placeholder="例: イラスト転送, 会議メモ",
        required=True,
        max_length=30
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

        # 作成後、即座にそのグループのダッシュボードを表示
        embed = create_dashboard_embed(guild_id, group_name)
        view = RuleDashboardView(guild_id, group_name)
        await interaction.response.edit_message(content=f"✅ グループ **{group_name}** を作成しました！", embed=embed, view=view)


# ---------------------------------------------------------
# モーダル: 昇格ルールの追加・編集
# ---------------------------------------------------------
class AddRuleModal(discord.ui.Modal, title="⭐ 昇格ルールの追加・編集"):
    emoji_input = discord.ui.TextInput(
        label="対象リアクション (絵文字)",
        placeholder="例: ⭐ または :star:",
        required=True,
        max_length=50
    )
    threshold_input = discord.ui.TextInput(
        label="必要リアクション数 (閾値)",
        placeholder="例: 3",
        required=True,
        max_length=3
    )

    def __init__(self, guild_id: int, group_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.group_name = group_name

    async def on_submit(self, interaction: discord.Interaction):
        try:
            threshold = int(self.threshold_input.value)
            if threshold <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ リアクション数は1以上の整数を指定してください。", ephemeral=True)
            return

        emoji = self.emoji_input.value.strip()

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO promotion_rules (guild_id, group_name, emoji, threshold)
            VALUES (?, ?, ?, ?)
        ''', (self.guild_id, self.group_name, emoji, threshold))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        view = RuleDashboardView(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=view)


# ---------------------------------------------------------
# ビュー: 一画面ダッシュボードの全コントロール
# ---------------------------------------------------------
class RuleDashboardView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name

    # --- 1段目: チャンネル設定 ---
    @discord.ui.button(label="📤 このチャンネルを転送元に設定/解除", style=discord.ButtonStyle.primary, row=0)
    async def toggle_src_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    @discord.ui.button(label="📥 このチャンネルを転送先に設定/解除", style=discord.ButtonStyle.success, row=0)
    async def toggle_dest_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    # --- 2段目: ルール・コンテンツ・保持設定 ---
    @discord.ui.button(label="⭐ 昇格ルール追加/変更", style=discord.ButtonStyle.secondary, row=1)
    async def add_rule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddRuleModal(self.guild_id, self.group_name))

    @discord.ui.button(label="📷 対象コンテンツ切替", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT target_content FROM group_settings WHERE guild_id = ? AND group_name = ?',
                  (self.guild_id, self.group_name))
        row = c.fetchone()
        current = row[0] if row and row[0] else "all"

        next_mode = {"all": "image_only", "image_only": "text_only", "text_only": "all"}.get(current, "all")

        c.execute('''
            INSERT INTO group_settings (guild_id, group_name, target_content) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, group_name) DO UPDATE SET target_content = excluded.target_content
        ''', (self.guild_id, self.group_name, next_mode))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏳ 保持日数切替", style=discord.ButtonStyle.secondary, row=1)
    async def toggle_retention(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT retention_days FROM group_settings WHERE guild_id = ? AND group_name = ?',
                  (self.guild_id, self.group_name))
        row = c.fetchone()
        current = row[0] if row and row[0] is not None else 0

        # 0日(無制限) -> 3日 -> 7日 -> 14日 -> 30日 -> 0日
        rotation = {0: 3, 3: 7, 7: 14, 14: 30, 30: 0}
        next_days = rotation.get(current, 0)

        c.execute('''
            INSERT INTO group_settings (guild_id, group_name, retention_days) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, group_name) DO UPDATE SET retention_days = excluded.retention_days
        ''', (self.guild_id, self.group_name, next_days))
        conn.commit()
        conn.close()

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed, view=self)

    # --- 3段目: グループ削除 ---
    @discord.ui.button(label="❌ このグループを削除", style=discord.ButtonStyle.danger, row=2)
    async def delete_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ?', (self.guild_id, self.group_name))
        c.execute('DELETE FROM promotion_rules WHERE guild_id = ? AND group_name = ?', (self.guild_id, self.group_name))
        c.execute('DELETE FROM group_settings WHERE guild_id = ? AND group_name = ?', (self.guild_id, self.group_name))
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"🗑️ グループ **{self.group_name}** を削除しました。`/setup` で新たなグループ設定を開けます。",
            embed=None,
            view=None
        )
