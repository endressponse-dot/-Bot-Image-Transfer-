import discord

TEXTS = {
    "en": {
        "map_title": "📊 **Forwarding Group Configuration List**",
        "no_groups": "No registered groups.",
        "none": "None",
        "source": "Source",
        "dest": "Destination",
        "menu_prompt": "Select an operation from the buttons below:",
        "btn_add": "Add / Edit Group",
        "btn_del": "Delete Group",
        "select_edit_group": "Select a group to edit, or create a new one:",
        "select_del_group": "Select a group to delete:",
        "new_group_option": "Create New Group",
        "modal_new_title": "Create New Group",
        "modal_gname_label": "Group Name",
        "created_msg": "✅ Group **[{name}]** has been saved.",
        "added_msg": "✅ Added {channel} as {type} to **[{name}]**.",
        "group_deleted": "🗑️ Group **[{name}]** has been deleted.",
        "select_target_type": "Select channel type to add to **[{name}]**:",
        "btn_add_src": "Add Source (📥)",
        "btn_add_dest": "Add Destination (📤)",
        "reset_warning": "⚠️ Are you sure you want to reset all settings for this server?",
        "btn_confirm_reset": "Reset All",
        "btn_cancel": "Cancel",
        "reset_complete": "✅ All group settings have been reset.",
        "reset_cancelled": "Cancelled.",
        "embed_title": "Open Original Post (Thread)",
        "embed_desc": "Posted by {author} (from #{channel})"
    },
    "ja": {
        "map_title": "📊 **転送グループ設定一覧**",
        "no_groups": "登録されているグループはありません。",
        "none": "なし",
        "source": "転送元",
        "dest": "転送先",
        "menu_prompt": "以下のボタンから操作を選択してください:",
        "btn_add": "グループの追加・編集",
        "btn_del": "グループの削除",
        "select_edit_group": "編集するグループを選択するか、新規作成してください:",
        "select_del_group": "削除するグループを選択してください:",
        "new_group_option": "新規グループを作成",
        "modal_new_title": "新規グループ作成",
        "modal_gname_label": "グループ名",
        "created_msg": "✅ グループ **[{name}]** を保存しました。",
        "added_msg": "✅ **[{name}]** の{type}に {channel} を追加しました。",
        "group_deleted": "🗑️ グループ **[{name}]** を削除しました。",
        "select_target_type": "**[{name}]** に追加するチャンネルの種類を選択してください:",
        "btn_add_src": "転送元を追加 (📥)",
        "btn_add_dest": "転送先を追加 (📤)",
        "reset_warning": "⚠️ このサーバーの全設定をリセットしてもよろしいですか？",
        "btn_confirm_reset": "すべてリセット",
        "btn_cancel": "キャンセル",
        "reset_complete": "✅ すべてのグループ設定をリセットしました。",
        "reset_cancelled": "キャンセルしました。",
        "embed_title": "元の投稿（スレッド）を開く",
        "embed_desc": "{author} さんの投稿（#{channel} より）"
    }
}

LANG_MAP = {
    "en": "🇺🇸 English",
    "ja": "🇯🇵 日本語",
    "ko": "🇰🇷 한국어",
    "zh-cn": "🇨🇳 简体中文",
    "zh-tw": "🇹🇼 繁體中文",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch",
    "es": "🇪🇸 Español",
    "it": "🇮🇹 Italiano",
    "ru": "🇷🇺 Русский",
    "pt": "🇵🇹 Português",
    "hi": "🇮🇳 हिन्दी"
}

def get_text(locale_str: str, key: str) -> str:
    """指定されたロケール文字列から該当する言語のテキストを安全に取得します。"""
    lang = locale_str.split('-')[0].lower() if locale_str else "en"
    if lang not in TEXTS:
        lang = "en"
    return TEXTS[lang].get(key, TEXTS["en"].get(key, key))

def get_lang_display(lang_code: str, server_locale_str: str) -> str:
    """設定言語の表示名称を返します。"""
    if lang_code == "default":
        s_lang = server_locale_str.split('-')[0].lower()
        disp_name = LANG_MAP.get(s_lang, f"Standard ({server_locale_str})")
        return f"⚙️ Server Default ({disp_name})"
    return LANG_MAP.get(lang_code, f"🌐 {lang_code}")