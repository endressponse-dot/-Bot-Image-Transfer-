# 国旗絵文字と言語名のマッピング
LANG_MAP = {
    "ja": ("🇯🇵", "日本語", "Japanese"),
    "en": ("🇺🇸", "English", "English (US)"),
    "zh-CN": ("🇨🇳", "简体中文", "Chinese Simplified"),
    "zh-TW": ("🇹🇼", "繁體中文", "Chinese Traditional"),
    "ko": ("🇰🇷", "한국어", "Korean"),
    "es": ("🇪🇸", "Español", "Spanish"),
    "fr": ("🇫🇷", "Français", "French"),
    "de": ("🇩🇪", "Deutsch", "German"),
    "it": ("🇮🇹", "Italiano", "Italian"),
    "pt": ("🇵🇹", "Português", "Portuguese"),
    "ru": ("🇷🇺", "Русский", "Russian"),
    "th": ("🇹🇭", "ไทย", "Thai")
}

LOCALES = {
    "ja": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\n{author} さんの投稿（#{channel} より）",
        "menu_prompt": "設定する操作を選択してください:",
        "select_group_to_edit": "編集・追加するグループを選択してください:",
        "select_group_to_delete": "削除するグループを選択してください:",
        "reset_warning": "⚠️ **警告**: サーバー内のすべての転送グループ設定を初期化します。よろしいですか？",
        "clear_confirm": "⚠️ **警告**: このチャンネル内のメッセージをすべて削除します。よろしいですか？",
        "retention_prompt": "このグループの画像保持期間（自動削除までの日数）を設定してください:"
    },
    "en": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})",
        "menu_prompt": "Select an operation:",
        "select_group_to_edit": "Select a group to edit/add:",
        "select_group_to_delete": "Select a group to delete:",
        "reset_warning": "⚠️ **Warning**: This will reset all forwarding settings for this server. Continue?",
        "clear_confirm": "⚠️ **Warning**: This will delete ALL messages in this channel. Continue?",
        "retention_prompt": "Select retention period (days before auto-deletion) for this group:"
    },
    "zh-CN": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\n{author} 发送的帖子（来自 #{channel}）",
        "menu_prompt": "请选择要执行的操作：",
        "select_group_to_edit": "请选择要编辑/添加的分组：",
        "select_group_to_delete": "请选择要删除的分组：",
        "reset_warning": "⚠️ **警告**：这将重置此服务器的所有转发设置。确定要继续吗？",
        "clear_confirm": "⚠️ **警告**：这将删除此频道中的所有消息。确定要继续吗？",
        "retention_prompt": "请选择此分组的保留期限（自动删除前的天数）："
    },
    "zh-TW": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\n{author} 貼文（來自 #{channel}）",
        "menu_prompt": "請選擇操作：",
        "select_group_to_edit": "請選擇要編輯/新增的群組：",
        "select_group_to_delete": "請選擇要刪除的群組：",
        "reset_warning": "⚠️ **警告**：這將重置此伺服器的所有轉發設定。確定要繼續嗎？",
        "clear_confirm": "⚠️ **警告**：這將刪除此頻道中的所有訊息。確定要繼續嗎？",
        "retention_prompt": "請選擇此群組的保留期限（自動刪除前的天數）："
    },
    "ko": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\n{author} 님의 게시물 (#{channel} 에서)",
        "menu_prompt": "작업을 선택하십시오:",
        "select_group_to_edit": "편집/추가할 그룹을 선택하십시오:",
        "select_group_to_delete": "삭제할 그룹을 선택하십시오:",
        "reset_warning": "⚠️ **경고**: 이 서버의 모든 전송 설정이 초기화됩니다. 계속하시겠습니까?",
        "clear_confirm": "⚠️ **경고**: 이 채널의 모든 메시지가 삭제됩니다. 계속하시겠습니까?",
        "retention_prompt": "이 그룹의 자동 삭제 기간(일)을 설정하십시오:"
    },
    "es": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nPublicado por {author} (desde #{channel})",
        "menu_prompt": "Seleccione una operación:",
        "select_group_to_edit": "Seleccione un grupo para editar/añadir:",
        "select_group_to_delete": "Seleccione un grupo para eliminar:",
        "reset_warning": "⚠️ **Advertencia**: Esto restablecerá todas las configuraciones de reenvío. ¿Continuar?",
        "clear_confirm": "⚠️ **Advertencia**: Esto eliminará TODOS los mensajes en este canal. ¿Continuar?",
        "retention_prompt": "Seleccione el período de retención (días antes del borrado automático):"
    },
    "fr": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nPublié par {author} (depuis #{channel})",
        "menu_prompt": "Sélectionnez une opération :",
        "select_group_to_edit": "Sélectionnez un groupe à modifier/ajouter :",
        "select_group_to_delete": "Sélectionnez un groupe à supprimer :",
        "reset_warning": "⚠️ **Avertissement** : Cela réinitialisera tous les paramètres de redirection. Continuer ?",
        "clear_confirm": "⚠️ **Avertissement** : Cela supprimera TOUS les messages de ce salon. Continuer ?",
        "retention_prompt": "Sélectionnez la période de conservation (jours avant suppression automatique) :"
    },
    "de": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nGepostet von {author} (aus #{channel})",
        "menu_prompt": "Wählen Sie eine Option:",
        "select_group_to_edit": "Gruppe zum Bearbeiten/Hinzufügen auswählen:",
        "select_group_to_delete": "Gruppe zum Löschen auswählen:",
        "reset_warning": "⚠️ **Warnung**: Dies setzt alle Weiterleitungseinstellungen zurück. Fortfahren?",
        "clear_confirm": "⚠️ **Warnung**: Dies löscht ALLE Nachrichten in diesem Kanal. Fortfahren?",
        "retention_prompt": "Aufbewahrungsfrist (Tage bis zur automatischen Löschung) auswählen:"
    },
    "it": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nPubblicato da {author} (da #{channel})",
        "menu_prompt": "Seleziona un'operazione:",
        "select_group_to_edit": "Seleziona un gruppo da modificare/aggiungere:",
        "select_group_to_delete": "Seleziona un gruppo da eliminare:",
        "reset_warning": "⚠️ **Avviso**: Questo ripristinerà tutte le impostazioni di inoltro. Continuare?",
        "clear_confirm": "⚠️ **Avviso**: Questo eliminerà TUTTI i messaggi in questo canale. Continuare?",
        "retention_prompt": "Seleziona il periodo di conservazione (giorni prima dell'eliminazione automatica):"
    },
    "pt": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nPostado por {author} (de #{channel})",
        "menu_prompt": "Selecione uma operação:",
        "select_group_to_edit": "Selecione um grupo para editar/adicionar:",
        "select_group_to_delete": "Selecione um grupo para deletar:",
        "reset_warning": "⚠️ **Aviso**: Isso redefinirá todas as configurações de reencaminhamento. Continuar?",
        "clear_confirm": "⚠️ **Aviso**: Isso deletará TODAS as mensagens neste canal. Continuar?",
        "retention_prompt": "Selecione o período de retenção (dias antes da exclusão automática):"
    },
    "ru": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nОпубликовано {author} (из #{channel})",
        "menu_prompt": "Выберите действие:",
        "select_group_to_edit": "Выберите группу для редактирования/добавления:",
        "select_group_to_delete": "Выберите группу для удаления:",
        "reset_warning": "⚠️ **Предупреждение**: Все настройки пересылки будут сброшены. Продолжить?",
        "clear_confirm": "⚠️ **Предупреждение**: Все сообщения в этом канале будут удалены. Продолжить?",
        "retention_prompt": "Выберите срок хранения (дни до автоматического удаления):"
    },
    "th": {
        "embed_title": "📌 Open Original Post (Thread)",
        "embed_desc": "👤 **Posted by {author}** (from #{channel})\nโพสต์โดย {author} (จาก #{channel})",
        "menu_prompt": "เลือกการดำเนินการ:",
        "select_group_to_edit": "เลือกกลุ่มที่จะแก้ไข/เพิ่ม:",
        "select_group_to_delete": "เลือกกลุ่มที่จะลบ:",
        "reset_warning": "⚠️ **คำเตือน**: ระบบจะรีเซ็ตการตั้งค่าการส่งต่อทั้งหมด ดำเนินการต่อหรือไม่?",
        "clear_confirm": "⚠️ **คำเตือน**: ข้อความทั้งหมดในช่องนี้จะถูกลบ ดำเนินการต่อหรือไม่?",
        "retention_prompt": "เลือกระยะเวลาการเก็บรักษา (วันก่อนลบอัตโนมัติ):"
    }
}

def get_text(locale_str: str, key: str) -> str:
    lang = str(locale_str).split("-")[0].lower()
    if "zh" in lang:
        lang = "zh-TW" if "tw" in str(locale_str).lower() or "hk" in str(locale_str).lower() else "zh-CN"
    
    if lang in LOCALES and key in LOCALES[lang]:
        return LOCALES[lang][key]
    return LOCALES["en"].get(key, key)
