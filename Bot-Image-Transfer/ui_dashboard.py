import discord
from discord.ui import View, Select, Button
import sqlite3
from config import DB_FILE, DEFAULT_DELETE_AFTER_DAYS

# ==========================================
# データベース取得・更新ヘルパー関数
# ==========================================

def get_rule_dashboard_data(guild_id: int, group_name: str) -> dict:
    """
    指定されたグループの設定状況をDBから一括取得します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # チャンネルマッピングの取得
    c.execute('SELECT channel_id, type FROM group_channels WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    ch_rows = c.fetchall()
    
    src_channels = [f"<#{r[0]}>" for r in ch_rows if r[1] == 'src']
    dest_channels = [f"<#{r[0]}>" for r in ch_rows if r[1] == 'dest']
    
    # 個別設定の取得（コンテンツ対象、保持期間）
    c.execute('SELECT description, retention_days FROM group_settings WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    set_row = c.fetchone()
    
    # 自動昇格ルールの取得
    c.execute('SELECT emoji, threshold FROM promotion_rules WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    promo_rows = c.fetchall()
    
    conn.close()
    
    # 規定値の補約
    content_filter = set_row[0] if set_row and set_row[0] else "all"  # 'all', 'image_only', 'text_only'
    retention_days = set_row[1] if set_row and set_row[1] is not None else DEFAULT_DELETE_AFTER_DAYS
    
    return {
        "group_name": group_name,
        "src": ", ".join(src_channels) if src_channels else "未設定",
        "dest": ", ".join(dest_channels) if dest_channels else "未設定",
        "content_filter": content_filter,
        "retention_days": retention_days,
        "promotion_rules": promo_rows # [(emoji, threshold), ...]
    }

def update_content_filter(guild_id: int, group_name: str, filter_type: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT INTO group_settings (guild_id, group_name, description)
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id, group_name) DO UPDATE SET description = excluded.description
    ''', (guild_id, group_name, filter_type))
    conn.commit()
    conn.close()

def update_retention_days(guild_id: int, group_name: str, days: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT INTO group_settings (guild_id, group_name, retention_days)
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id, group_name) DO UPDATE SET retention_days = excluded.retention_days
    ''', (guild_id, group_name, days))
    conn.commit()
    conn.close()

def set_trigger_condition(guild_id: int, group_name: str, condition_type: str, emoji: str = "⭐", threshold: int = 1):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 既存の昇格ルールをリセットして新規設定
    c.execute('DELETE FROM promotion_rules WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    if condition_type == "stamp":
        c.execute('''
        INSERT INTO promotion_rules (guild_id, group_name, emoji, threshold)
        VALUES (?, ?, ?, ?)
        ''', (guild_id, group_name, emoji, threshold))
    conn.commit()
    conn.close()


# ==========================================
# Embedダッシュボード構築関数
# ==========================================

def create_dashboard_embed(guild_id: int, group_name: str) -> discord.Embed:
    data = get_rule_dashboard_data(guild_id, group_name)
    
    embed = discord.Embed(
        title=f"⚙️ ルールダッシュボード: {group_name}",
        color=discord.Color.blue()
    )
    
    # 📍 ルート設定
    embed.add_field(
        name="📍 ルート設定 (Route)",
        value=f"├ 転送元 (Source): {data['src']}\n└ 転送先 (Dest): {data['dest']}",
        inline=False
    )
    
    # 🔍 対象コンテンツ
    filter_map = {
        "all": "📄 すべてのメッセージ (All)",
        "image_only": "🖼️ 画像のみ (Image Only)",
        "text_only": "💬 テキストのみ (Text Only)"
    }
    filter_text = filter_map.get(data['content_filter'], "📄 すべてのメッセージ")
    embed.add_field(
        name="🔍 対象コンテンツ (Filter)",
        value=f"`{filter_text}`",
        inline=True
    )
    
    # ⚡ 発火条件
    if data['promotion_rules']:
        rules_str = ", ".join([f"{r[0]} × {r[1]}個" for r in data['promotion_rules']])
        trigger_text = f"🎯 スタンプ条件: {rules_str}"
    else:
        trigger_text = "🚀 即時転送 (無条件)"
    
    embed.add_field(
        name="⚡ 発火条件 (Trigger)",
        value=f"`{trigger_text}`",
        inline=True
    )
    
    # ⏳ 保持期間
    days = data['retention_days']
    retention_text = f"⏳ {days}日間で自動削除" if days > 0 else "♾️ 無制限 (削除なし)"
    embed.add_field(
        name="⏳ 保持期間 (Retention)",
        value=f"`{retention_text}`",
        inline=True
    )
    
    embed.set_footer(text="下のドロップダウンメニューから変更したい項目を選択してください。")
    return embed


# ==========================================
# UIコンポーネント（セレクトメニュー & ビュー）
# ==========================================

class ContentFilterSelect(Select):
    def __init__(self, guild_id: int, group_name: str):
        self.guild_id = guild_id
        self.group_name = group_name
        options = [
            discord.SelectOption(label="すべてのメッセージ", value="all", emoji="📄", description="テキスト・画像の両方を転送します"),
            discord.SelectOption(label="画像のみ", value="image_only", emoji="🖼️", description="添付画像・画像URLが含まれる場合のみ転送します"),
            discord.SelectOption(label="テキストのみ", value="text_only", emoji="💬", description="画像が含まれないテキストのみ転送します"),
        ]
        super().__init__(placeholder="🔍 転送対象コンテンツを選択...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        update_content_filter(self.guild_id, self.group_name, self.values[0])
        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed)


class TriggerConditionSelect(Select):
    def __init__(self, guild_id: int, group_name: str):
        self.guild_id = guild_id
        self.group_name = group_name
        options = [
            discord.SelectOption(label="即時無条件転送", value="instant", emoji="🚀", description="投稿されたら即座に転送します"),
            discord.SelectOption(label="⭐ スタンプ 1個以上", value="stamp_1", emoji="⭐", description="⭐が1個ついたら転送します"),
            discord.SelectOption(label="⭐ スタンプ 3個以上", value="stamp_3", emoji="⭐", description="⭐が3個ついたら転送します"),
            discord.SelectOption(label="⭐ スタンプ 5個以上", value="stamp_5", emoji="⭐", description="⭐が5個ついたら転送（昇格）します"),
            discord.SelectOption(label="🔥 スタンプ 3個以上", value="fire_3", emoji="🔥", description="🔥が3個ついたら転送します"),
        ]
        super().__init__(placeholder="⚡ 発火条件（トリガー）を選択...", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "instant":
            set_trigger_condition(self.guild_id, self.group_name, "instant")
        elif val == "stamp_1":
            set_trigger_condition(self.guild_id, self.group_name, "stamp", "⭐", 1)
        elif val == "stamp_3":
            set_trigger_condition(self.guild_id, self.group_name, "stamp", "⭐", 3)
        elif val == "stamp_5":
            set_trigger_condition(self.guild_id, self.group_name, "stamp", "⭐", 5)
        elif val == "fire_3":
            set_trigger_condition(self.guild_id, self.group_name, "stamp", "🔥", 3)

        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed)


class RetentionSelect(Select):
    def __init__(self, guild_id: int, group_name: str):
        self.guild_id = guild_id
        self.group_name = group_name
        options = [
            discord.SelectOption(label="1日後", value="1", emoji="⏳", description="転送から1日後に自動削除"),
            discord.SelectOption(label="3日後", value="3", emoji="⏳", description="転送から3日後に自動削除"),
            discord.SelectOption(label="7日後 (デフォルト)", value="7", emoji="⏳", description="転送から7日後に自動削除"),
            discord.SelectOption(label="14日後", value="14", emoji="⏳", description="転送から14日後に自動削除"),
            discord.SelectOption(label="30日後", value="30", emoji="⏳", description="転送から30日後に自動削除"),
            discord.SelectOption(label="無制限 (自動削除なし)", value="0", emoji="♾️", description="自動削除を行いません"),
        ]
        super().__init__(placeholder="⏳ 保持期間（自動削除タイマー）を選択...", min_values=1, max_values=1, options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        update_retention_days(self.guild_id, self.group_name, int(self.values[0]))
        embed = create_dashboard_embed(self.guild_id, self.group_name)
        await interaction.response.edit_message(embed=embed)


class RuleDashboardView(View):
    def __init__(self, guild_id: int, group_name: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name

        # 各設定用ドロップダウンを追加
        self.add_item(ContentFilterSelect(guild_id, group_name))
        self.add_item(TriggerConditionSelect(guild_id, group_name))
        self.add_item(RetentionSelect(guild_id, group_name))


# ==========================================
# 呼び出し用関数
# ==========================================

async def send_rule_dashboard(interaction: discord.Interaction, group_name: str):
    """
    ダッシュボード画面を送信・表示します。
    """
    guild_id = interaction.guild_id
    embed = create_dashboard_embed(guild_id, group_name)
    view = RuleDashboardView(guild_id, group_name)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
