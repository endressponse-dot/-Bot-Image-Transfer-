import discord
from locales import get_text
from database import (
    add_group_channel, 
    delete_group_channel, 
    set_group_retention_days, 
    build_group_map_text,
    get_all_group_names,
    set_promotion_rule,
    get_promotion_rules,
    delete_promotion_rule
)

# ==========================================
# 戻るボタン用のコンポーネント
# ==========================================

class BackToMainMenuButton(discord.ui.Button):
    def __init__(self, guild_id: int, locale, bot, row: int = 2):
        super().__init__(label="🔙 メインメニューへ戻る", style=discord.ButtonStyle.secondary, row=row)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        prompt_text = get_text(self.locale, "menu_prompt")
        view = OperationSelectView(self.guild_id, self.locale, self.bot)
        await interaction.response.edit_message(content=f"📁 **{prompt_text}**", view=view)


# ==========================================
# 1. 操作選択メニュー（保持期間・チャンネル選択）
# ==========================================

class RetentionSelect(discord.ui.Select):
    def __init__(self, group_name: str, guild_id: int, locale):
        self.group_name = group_name
        self.guild_id = guild_id
        self.locale = locale
        
        options = [
            discord.SelectOption(label="1日", value="1", description="1日後にメッセージを自動削除"),
            discord.SelectOption(label="3日", value="3", description="3日後にメッセージを自動削除"),
            discord.SelectOption(label="7日 (デフォルト)", value="7", description="7日後にメッセージを自動削除"),
            discord.SelectOption(label="14日", value="14", description="14日後にメッセージを自動削除"),
            discord.SelectOption(label="30日", value="30", description="30日後にメッセージを自動削除"),
            discord.SelectOption(label="無制限 (自動削除なし)", value="0", description="自動削除を行いません"),
        ]
        super().__init__(placeholder="⏳ 画像・メッセージの保持期間を選択...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        days = int(self.values[0])
        set_group_retention_days(self.guild_id, self.group_name, days)
        days_str = f"{days}日間" if days > 0 else "無制限"
        
        # 画面圧迫防止のため、画面上のメニューを最新のグループ管理画面に更新
        view = GroupActionView(self.guild_id, self.group_name, self.locale, interaction.client)
        updated_text = build_group_map_text(self.guild_id, self.locale, interaction.client)
        msg_content = f"✅ グループ **{self.group_name}** の保持期間を **{days_str}** に設定しました。\n\n{updated_text}"
        
        await interaction.response.edit_message(content=msg_content, view=view)


class GroupChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, action_type: str, locale, bot):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.action_type = action_type  # 'add_src', 'add_dest'
        self.locale = locale
        self.bot = bot

        channel_select = discord.ui.ChannelSelect(
            placeholder="対象のチャンネルまたはスレッドを選択...",
            channel_types=[
                discord.ChannelType.text,           # テキストチャンネル
                discord.ChannelType.forum,          # フォーラムチャンネル
                discord.ChannelType.public_thread,  # 公開スレッド
                discord.ChannelType.private_thread, # 非公開スレッド
                discord.ChannelType.news,           # アナウンスチャンネル
                discord.ChannelType.news_thread     # アナウンススレッド
            ],
            min_values=1,
            max_values=1
        )
        channel_select.callback = self.channel_select_callback
        self.add_item(channel_select)
        
        # 戻るボタンの追加
        self.add_item(BackToMainMenuButton(guild_id, locale, bot, row=1))

    async def channel_select_callback(self, interaction: discord.Interaction):
        values = interaction.data.get('values', [])
        if not values:
            await interaction.response.send_message("❌ チャンネルの取得に失敗しました。", ephemeral=True, delete_after=5)
            return

        selected_channel_id = values[0]
        ch_type = "src" if self.action_type == "add_src" else "dest"
        
        add_group_channel(self.guild_id, self.group_name, int(selected_channel_id), ch_type)
        
        type_str = "転送元 (Source)" if ch_type == "src" else "転送先 (Dest)"
        
        # 画面圧迫防止：編集画面に戻しつつ更新通知を表示
        view = GroupActionView(self.guild_id, self.group_name, self.locale, interaction.client)
        updated_text = build_group_map_text(self.guild_id, self.locale, interaction.client)
        msg_content = f"✅ グループ **{self.group_name}** の **{type_str}** に <#{selected_channel_id}> を追加しました。\n\n{updated_text}"
        
        await interaction.response.edit_message(content=msg_content, view=view)


# ==========================================
# 2. 自動昇格ルール設定 UI・モーダル
# ==========================================

class EmojiSelect(discord.ui.Select):
    def __init__(self, guild_id: int, group_name: str, locale):
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale

        options = [
            discord.SelectOption(label="⭐ 星 (Star)", value="⭐", emoji="⭐"),
            discord.SelectOption(label="❤️ ハート (Heart)", value="❤️", emoji="❤️"),
            discord.SelectOption(label="🔥 炎 (Fire)", value="🔥", emoji="🔥"),
            discord.SelectOption(label="👍 グッド (Thumbs Up)", value="👍", emoji="👍"),
            discord.SelectOption(label="👏 拍手 (Clap)", value="👏", emoji="👏"),
            discord.SelectOption(label="🎉 クラッカー (Tada)", value="🎉", emoji="🎉"),
        ]
        super().__init__(
            placeholder="使用する絵文字を選択してください...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        selected_emoji = self.values[0]
        modal = PromotionThresholdModal(self.guild_id, self.group_name, selected_emoji, self.locale)
        await interaction.response.send_modal(modal)


class PromotionThresholdModal(discord.ui.Modal):
    threshold_input = discord.ui.TextInput(
        label="昇格に必要なリアクション数",
        placeholder="例: 5",
        required=True,
        max_length=5
    )

    def __init__(self, guild_id: int, group_name: str, emoji_str: str, locale):
        super().__init__(title=f"「{emoji_str}」の必要リアクション数設定")
        self.guild_id = guild_id
        self.group_name = group_name
        self.emoji_str = emoji_str
        self.locale = locale

    async def on_submit(self, interaction: discord.Interaction):
        try:
            threshold = int(self.threshold_input.value.strip())
            if threshold <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ リアクション数は1以上の数値を入力してください。", ephemeral=True)
            return

        set_promotion_rule(self.guild_id, self.group_name, self.emoji_str, threshold)

        view = PromotionSetupView(self.guild_id, self.group_name, self.locale, interaction.client)
        rules = get_promotion_rules(self.guild_id, self.group_name)
        rules_str = "\n".join([f"• {r['emoji']} : {r['threshold']}個" for r in rules]) if rules else "設定なし"

        await interaction.response.edit_message(
            content=f"✅ グループ **{self.group_name}** に昇格ルール（{self.emoji_str} × {threshold}個）を設定しました。\n\n**【現在の設定一覧】**\n{rules_str}",
            view=view
        )


class CustomEmojiPromotionModal(discord.ui.Modal, title="手動入力でルールを追加"):
    emoji_input = discord.ui.TextInput(
        label="対象の絵文字 (絵文字またはカスタム絵文字)",
        placeholder="例: ⭐ や :custom_emoji:",
        required=True,
        max_length=50
    )
    threshold_input = discord.ui.TextInput(
        label="昇格に必要なリアクション数",
        placeholder="例: 5",
        required=True,
        max_length=5
    )

    def __init__(self, guild_id: int, group_name: str, locale):
        super().__init__()
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale

    async def on_submit(self, interaction: discord.Interaction):
        emoji_str = self.emoji_input.value.strip()
        try:
            threshold = int(self.threshold_input.value.strip())
            if threshold <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("❌ リアクション数は1以上の数値を入力してください。", ephemeral=True)
            return

        set_promotion_rule(self.guild_id, self.group_name, emoji_str, threshold)

        view = PromotionSetupView(self.guild_id, self.group_name, self.locale, interaction.client)
        rules = get_promotion_rules(self.guild_id, self.group_name)
        rules_str = "\n".join([f"• {r['emoji']} : {r['threshold']}個" for r in rules]) if rules else "設定なし"

        await interaction.response.edit_message(
            content=f"✅ グループ **{self.group_name}** に昇格ルールを追加しました。\n\n**【現在の設定一覧】**\n{rules_str}",
            view=view
        )


class RuleDeleteSelect(discord.ui.Select):
    def __init__(self, guild_id: int, group_name: str, rules: list, locale):
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale

        options = [
            discord.SelectOption(
                label=f"{r['emoji']} (必要数: {r['threshold']}個)", 
                value=r['emoji']
            ) for r in rules
        ]
        super().__init__(
            placeholder="削除する昇格ルールを選択してください...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_emoji = self.values[0]
        delete_promotion_rule(self.guild_id, self.group_name, selected_emoji)

        rules = get_promotion_rules(self.guild_id, self.group_name)
        rules_str = "\n".join([f"• {r['emoji']} : {r['threshold']}個" for r in rules]) if rules else "設定なし"
        view = PromotionSetupView(self.guild_id, self.group_name, self.locale, interaction.client)

        await interaction.response.edit_message(
            content=f"🗑️ 昇格ルール（{selected_emoji}）を削除しました。\n\n**【現在の設定一覧】**\n{rules_str}",
            view=view
        )


class PromotionSetupView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale, bot):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale
        self.bot = bot

        # 絵文字選択ドロップダウンの追加
        self.add_item(EmojiSelect(guild_id, group_name, locale))

    @discord.ui.button(label="✏️ その他の絵文字を入力", style=discord.ButtonStyle.primary, row=1)
    async def add_custom_rule(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomEmojiPromotionModal(self.guild_id, self.group_name, self.locale)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ ルールを削除", style=discord.ButtonStyle.danger, row=1)
    async def delete_rule_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        rules = get_promotion_rules(self.guild_id, self.group_name)
        if not rules:
            await interaction.response.send_message("❌ 削除できる昇格ルールが存在しません。", ephemeral=True, delete_after=5)
            return

        view = discord.ui.View()
        view.add_item(RuleDeleteSelect(self.guild_id, self.group_name, rules, self.locale))
        
        # 戻るボタン
        back_btn = discord.ui.Button(label="🔙 昇格設定に戻る", style=discord.ButtonStyle.secondary)
        async def back_callback(back_interaction: discord.Interaction):
            rules_now = get_promotion_rules(self.guild_id, self.group_name)
            rules_str_now = "\n".join([f"• {r['emoji']} : {r['threshold']}個" for r in rules_now]) if rules_now else "設定なし"
            setup_view = PromotionSetupView(self.guild_id, self.group_name, self.locale, self.bot)
            await back_interaction.response.edit_message(
                content=f"⭐ **グループ: {self.group_name}** の自動昇格ルール設定\n\n**【現在の設定一覧】**\n{rules_str_now}",
                view=setup_view
            )
        back_btn.callback = back_callback
        view.add_item(back_btn)

        await interaction.response.edit_message(content="🗑️ **削除するルールを選択してください:**", view=view)

    @discord.ui.button(label="🔙 グループ編集に戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GroupActionView(self.guild_id, self.group_name, self.locale, self.bot)
        await interaction.response.edit_message(
            content=f"⚙️ グループ **{self.group_name}** の設定・編集を行います。操作を選択してください:",
            view=view
        )


# ==========================================
# 3. グループ詳細操作・編集UI
# ==========================================

class GroupActionView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale, bot=None):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale
        self.bot = bot

        # 保持期間選択ドロップダウンを追加
        self.add_item(RetentionSelect(group_name, guild_id, locale))
        # メインメニューに戻るボタンを追加
        if bot:
            self.add_item(BackToMainMenuButton(guild_id, locale, bot, row=2))

    @discord.ui.button(label="📥 転送元を追加", style=discord.ButtonStyle.primary, row=1)
    async def add_source(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GroupChannelSelectView(self.guild_id, self.group_name, "add_src", self.locale, interaction.client)
        await interaction.response.edit_message(content="📥 転送元に指定するチャンネルまたはスレッドを選択してください:", view=view)

    @discord.ui.button(label="📤 転送先を追加", style=discord.ButtonStyle.success, row=1)
    async def add_dest(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GroupChannelSelectView(self.guild_id, self.group_name, "add_dest", self.locale, interaction.client)
        await interaction.response.edit_message(content="📤 転送先に指定するチャンネルまたはスレッドを選択してください:", view=view)

    @discord.ui.button(label="⭐ 自動昇格設定", style=discord.ButtonStyle.secondary, row=1)
    async def config_promotion(self, interaction: discord.Interaction, button: discord.ui.Button):
        rules = get_promotion_rules(self.guild_id, self.group_name)
        rules_str = "\n".join([f"• {r['emoji']} : {r['threshold']}個" for r in rules]) if rules else "設定なし"
        
        view = PromotionSetupView(self.guild_id, self.group_name, self.locale, interaction.client)
        await interaction.response.edit_message(
            content=f"⭐ **グループ: {self.group_name}** の自動昇格ルール設定\n\n**【現在の設定一覧】**\n{rules_str}",
            view=view
        )

    @discord.ui.button(label="🗑️ このグループを削除", style=discord.ButtonStyle.danger, row=1)
    async def delete_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        delete_group_channel(self.guild_id, self.group_name)
        
        # 削除後はメインメニューへ戻す
        view = OperationSelectView(self.guild_id, self.locale, interaction.client)
        updated_text = build_group_map_text(self.guild_id, self.locale, interaction.client)
        msg_content = f"🗑️ グループ **{self.group_name}** を削除しました。\n\n{updated_text}"
        
        await interaction.response.edit_message(content=msg_content, view=view)


# ==========================================
# 4. グループ選択・新規作成モーダル
# ==========================================

class NewGroupModal(discord.ui.Modal, title="新規グループ作成"):
    group_name_input = discord.ui.TextInput(
        label="グループ名",
        placeholder="例: main-group, art-forward",
        required=True,
        max_length=30
    )

    def __init__(self, guild_id: int, locale):
        super().__init__()
        self.guild_id = guild_id
        self.locale = locale

    async def on_submit(self, interaction: discord.Interaction):
        g_name = self.group_name_input.value.strip()
        view = GroupActionView(self.guild_id, g_name, self.locale, interaction.client)
        
        # モーダル送信時のレスポンスを上書き編集し、画面増加を防止
        await interaction.response.edit_message(
            content=f"✨ 新規グループ **{g_name}** を作成しました。続いて設定を行ってください:",
            view=view
        )


class GroupSelectMenu(discord.ui.Select):
    def __init__(self, guild_id: int, groups: list, locale):
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label=f"📁 {g}", value=g) for g in groups]
        options.append(discord.SelectOption(label="➕ 新しいグループを作成", value="__new__"))
        
        super().__init__(placeholder="編集するグループを選択してください...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0]
        if selected_val == "__new__":
            modal = NewGroupModal(self.guild_id, self.locale)
            await interaction.response.send_modal(modal)
        else:
            view = GroupActionView(self.guild_id, selected_val, self.locale, interaction.client)
            # 前の画面を消去せずに上書き編集
            await interaction.response.edit_message(
                content=f"⚙️ グループ **{selected_val}** の設定・編集を行います。操作を選択してください:",
                view=view
            )


class GroupDeleteSelectMenu(discord.ui.Select):
    def __init__(self, guild_id: int, groups: list, locale):
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label=f"🗑️ {g}", value=g) for g in groups]
        super().__init__(placeholder="削除するグループを選択してください...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0]
        delete_group_channel(self.guild_id, selected_val)
        
        # 削除後、メインメニュー画面へ上書き復帰
        view = OperationSelectView(self.guild_id, self.locale, interaction.client)
        updated_text = build_group_map_text(self.guild_id, self.locale, interaction.client)
        msg_content = f"🗑️ グループ **{selected_val}** を削除しました。\n\n{updated_text}"
        
        await interaction.response.edit_message(content=msg_content, view=view)


# ==========================================
# 5. トップレベル操作選択UI（Main Menu）
# ==========================================

class OperationSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale, bot):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.locale = locale
        self.bot = bot

    @discord.ui.button(label="📋 設定一覧を表示", style=discord.ButtonStyle.secondary, row=0)
    async def show_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        text = build_group_map_text(self.guild_id, self.locale, self.bot)
        # 既存画面を保持したまま最新一覧に表示を切り替え
        await interaction.response.edit_message(content=text, view=self)

    @discord.ui.button(label="⚙️ グループ編集・追加", style=discord.ButtonStyle.primary, row=0)
    async def edit_group(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing_groups = get_all_group_names(self.guild_id)
        
        view = discord.ui.View()
        view.add_item(GroupSelectMenu(self.guild_id, existing_groups, self.locale))
        view.add_item(BackToMainMenuButton(self.guild_id, self.locale, self.bot, row=1))
        
        prompt_text = get_text(self.locale, "select_group_to_edit")
        await interaction.response.edit_message(content=prompt_text, view=view)

    @discord.ui.button(label="🗑️ グループ削除", style=discord.ButtonStyle.danger, row=0)
    async def delete_group_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing_groups = get_all_group_names(self.guild_id)
        
        if not existing_groups:
            await interaction.response.send_message("❌ 削除できるグループが存在しません。", ephemeral=True, delete_after=5)
            return

        view = discord.ui.View()
        view.add_item(GroupDeleteSelectMenu(self.guild_id, existing_groups, self.locale))
        view.add_item(BackToMainMenuButton(self.guild_id, self.locale, self.bot, row=1))
        
        prompt_text = get_text(self.locale, "select_group_to_delete")
        await interaction.response.edit_message(content=prompt_text, view=view)


async def send_group_management_menu(interaction: discord.Interaction, guild_id: int, locale):
    prompt_text = get_text(locale, "menu_prompt")
    view = OperationSelectView(guild_id, locale, interaction.client)
    await interaction.response.send_message(f"📁 **{prompt_text}**", view=view, ephemeral=True)
