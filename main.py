import os
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands, tasks

# ==========================================
# ⚙️ 設定 & Render用 Web サーバー設定
# ==========================================

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

keep_alive()

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DB_FILE = "bot_database.db"
DELETE_AFTER_DAYS = 3  # 自動削除する経過日数

# ==========================================
# 🗄️ データベースの初期化
# ==========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_channels (
            guild_id INTEGER,
            group_name TEXT,
            channel_id INTEGER,
            type TEXT,
            PRIMARY KEY (guild_id, group_name, channel_id, type)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS guild_languages (
            guild_id INTEGER PRIMARY KEY,
            main_lang TEXT,
            sub_langs TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🌐 多言語ローカライズ用テキスト辞書
# ==========================================
TEXTS = {
    "ja": {
        "map_title": "🗺️ **現在の全体マップ:**",
        "no_groups": "（設定されているグループはありません）",
        "source": "転送元",
        "dest": "転送先",
        "none": "なし",
        "menu_prompt": "操作を選択してください：",
        "btn_add": "グループの追加・編集",
        "btn_del": "グループの削除",
        "select_edit_group": "追加・編集するグループを選択してください：",
        "select_del_group": "削除するグループを選択してください：",
        "new_group_option": "➕ 新しいグループを作成",
        "modal_new_title": "新規グループ作成",
        "modal_gname_label": "グループ名",
        "modal_src_label": "転送元 チャンネルID",
        "modal_dest_label": "転送先 チャンネルID",
        "invalid_id": "⚠️ チャンネルIDは数字で入力してください。",
        "created_msg": "✅ グループ **[{name}]** を作成しました！",
        "select_target_type": "グループ **[{name}]** に追加する対象を選択し、チャンネルIDを入力してください。",
        "btn_add_src": "転送元として追加",
        "btn_add_dest": "転送先として追加",
        "modal_add_title": "{type}チャンネルの追加",
        "modal_cid_label": "追加する チャンネルID",
        "added_msg": "✅ グループ **[{name}]** の **{type}** に {channel} を追加しました！",
        "group_deleted": "🗑️ グループ **[{name}]** を削除しました。",
        "reset_warning": "⚠️ **本当にすべての設定をリセットしますか？**",
        "btn_confirm_reset": "全設定を削除する",
        "btn_cancel": "キャンセル",
        "reset_complete": "💥 **すべてのグループ設定を削除（全リセット）しました。**",
        "reset_cancelled": "リセットをキャンセルしました。",
        "embed_title": "🔗 元の投稿（スレッド）を開く",
        "embed_desc": "📷 **{author}** さんの投稿（#{channel} より）"
    },
    "en": {
        "map_title": "🗺️ **Current Overview Map:**",
        "no_groups": "(No groups configured)",
        "source": "Source",
        "dest": "Destination",
        "none": "None",
        "menu_prompt": "Please select an action:",
        "btn_add": "Add / Edit Group",
        "btn_del": "Delete Group",
        "select_edit_group": "Select a group to add or edit:",
        "select_del_group": "Select a group to delete:",
        "new_group_option": "➕ Create New Group",
        "modal_new_title": "Create New Group",
        "modal_gname_label": "Group Name",
        "modal_src_label": "Source Channel ID",
        "modal_dest_label": "Destination Channel ID",
        "invalid_id": "⚠️ Channel IDs must be numbers.",
        "created_msg": "✅ Created group **[{name}]**!",
        "select_target_type": "Select target type to add for **[{name}]** and enter Channel ID.",
        "btn_add_src": "Add as Source",
        "btn_add_dest": "Add as Destination",
        "modal_add_title": "Add {type} Channel",
        "modal_cid_label": "Channel ID to Add",
        "added_msg": "✅ Added {channel} to **{type}** of group **[{name}]**!",
        "group_deleted": "🗑️ Deleted group **[{name}]**.",
        "reset_warning": "⚠️ **Are you sure you want to reset all settings?**",
        "btn_confirm_reset": "Reset All Settings",
        "btn_cancel": "Cancel",
        "reset_complete": "💥 **All group settings have been reset.**",
        "reset_cancelled": "Reset cancelled.",
        "embed_title": "🔗 Open Original Post (Thread)",
        "embed_desc": "📷 Posted by **{author}** (from #{channel})"
    },
    "zh-CN": {
        "map_title": "🗺️ **当前整体地图：**",
        "no_groups": "（暂未配置组）",
        "source": "来源",
        "dest": "目标",
        "none": "无",
        "menu_prompt": "请选择操作：",
        "btn_add": "添加/编辑组",
        "btn_del": "删除组",
        "select_edit_group": "请选择要添加或编辑的组：",
        "select_del_group": "请选择要删除的组：",
        "new_group_option": "➕ 新增组",
        "modal_new_title": "创建新组",
        "modal_gname_label": "组名称",
        "modal_src_label": "来源 频道ID",
        "modal_dest_label": "目标 频道ID",
        "invalid_id": "⚠️ 频道ID必须是数字。",
        "created_msg": "✅ 已创建组 **[{name}]**！",
        "select_target_type": "请选择要为 **[{name}]** 添加的类型并输入频道ID。",
        "btn_add_src": "添加为来源",
        "btn_add_dest": "添加为目标",
        "modal_add_title": "添加 {type} 频道",
        "modal_cid_label": "要添加的频道ID",
        "added_msg": "✅ 已将 {channel} 添加到 **[{name}]** 的 **{type}**！",
        "group_deleted": "🗑️ 已删除组 **[{name}]**。",
        "reset_warning": "⚠️ **确定要重置所有设置吗？**",
        "btn_confirm_reset": "删除所有设置",
        "btn_cancel": "取消",
        "reset_complete": "💥 **已删除所有组设置（全重置）。**",
        "reset_cancelled": "已取消重置。",
        "embed_title": "🔗 打开原始帖子（子频道/线程）",
        "embed_desc": "📷 **{author}** 发送的动态（来自 #{channel}）"
    },
    "zh-TW": {
        "map_title": "🗺️ **目前整體地圖：**",
        "no_groups": "（尚未設定群組）",
        "source": "來源",
        "dest": "目標",
        "none": "無",
        "menu_prompt": "請選擇操作：",
        "btn_add": "新增/編輯群組",
        "btn_del": "刪除群組",
        "select_edit_group": "請選擇要新增或編輯的群組：",
        "select_del_group": "請選擇要刪除的群組：",
        "new_group_option": "➕ 建立新群組",
        "modal_new_title": "建立新群組",
        "modal_gname_label": "群組名稱",
        "modal_src_label": "來源 頻道ID",
        "modal_dest_label": "目標 頻道ID",
        "invalid_id": "⚠️ 頻道ID必須是數字。",
        "created_msg": "✅ 已建立群組 **[{name}]**！",
        "select_target_type": "請選擇要為 **[{name}]** 新增的類型並輸入頻道ID。",
        "btn_add_src": "新增為來源",
        "btn_add_dest": "新增為目標",
        "modal_add_title": "新增 {type} 頻道",
        "modal_cid_label": "要新增的頻道ID",
        "added_msg": "✅ 已將 {channel} 新增至 **[{name}]** 的 **{type}**！",
        "group_deleted": "🗑️ 已刪除群組 **[{name}]**。",
        "reset_warning": "⚠️ **確定要重設所有設定嗎？**",
        "btn_confirm_reset": "刪除所有設定",
        "btn_cancel": "取消",
        "reset_complete": "💥 **已刪除所有群組設定（全重設）。**",
        "reset_cancelled": "已取消重設。",
        "embed_title": "🔗 開啟原始貼文（討論串）",
        "embed_desc": "📷 **{author}** 發送的貼文（來自 #{channel}）"
    },
    "ko": {
        "map_title": "🗺️ **현재 전체 맵:**",
        "no_groups": "(설정된 그룹이 없습니다)",
        "source": "전송 원본",
        "dest": "전송 대상",
        "none": "없음",
        "menu_prompt": "작업을 선택하세요:",
        "btn_add": "그룹 추가/편집",
        "btn_del": "그룹 삭제",
        "select_edit_group": "추가 또는 편집할 그룹을 선택하세요:",
        "select_del_group": "삭제할 그룹을 선택하세요:",
        "new_group_option": "➕ 새 그룹 생성",
        "modal_new_title": "새 그룹 생성",
        "modal_gname_label": "그룹 이름",
        "modal_src_label": "전송 원본 채널 ID",
        "modal_dest_label": "전송 대상 채널 ID",
        "invalid_id": "⚠️ 채널 ID는 숫자여야 합니다.",
        "created_msg": "✅ **[{name}]** 그룹을 생성했습니다!",
        "select_target_type": "**[{name}]** 그룹에 추가할 유형을 선택하고 채널 ID를 입력하세요.",
        "btn_add_src": "전송 원본으로 추가",
        "btn_add_dest": "전송 대상으로 추가",
        "modal_add_title": "{type} 채널 추가",
        "modal_cid_label": "추가할 채널 ID",
        "added_msg": "✅ **[{name}]** 그룹의 **{type}**에 {channel}을(를) 추가했습니다!",
        "group_deleted": "🗑️ **[{name}]** 그룹을 삭제했습니다.",
        "reset_warning": "⚠️ **정말로 모든 설정을 초기화하시겠습니까?**",
        "btn_confirm_reset": "모든 설정 삭제",
        "btn_cancel": "취소",
        "reset_complete": "💥 **모든 그룹 설정을 삭제(초기화)했습니다.**",
        "reset_cancelled": "초기화를 취소했습니다.",
        "embed_title": "🔗 원본 게시글(스레드) 열기",
        "embed_desc": "📷 **{author}** 님의 게시글 (#{channel} 에서)"
    },
    "es": {
        "map_title": "🗺️ **Mapa General Actual:**",
        "no_groups": "(No hay grupos configurados)",
        "source": "Origen",
        "dest": "Destino",
        "none": "Ninguno",
        "menu_prompt": "Seleccione una acción:",
        "btn_add": "Añadir / Editar Grupo",
        "btn_del": "Eliminar Grupo",
        "select_edit_group": "Seleccione un grupo para añadir o editar:",
        "select_del_group": "Seleccione un grupo para eliminar:",
        "new_group_option": "➕ Crear Nuevo Grupo",
        "modal_new_title": "Crear Nuevo Grupo",
        "modal_gname_label": "Nombre del Grupo",
        "modal_src_label": "ID de Canal Origen",
        "modal_dest_label": "ID de Canal Destino",
        "invalid_id": "⚠️ Los ID de canal deben ser números.",
        "created_msg": "✅ ¡Grupo **[{name}]** creado!",
        "select_target_type": "Seleccione el tipo para **[{name}]** e ingrese el ID de canal.",
        "btn_add_src": "Añadir como Origen",
        "btn_add_dest": "Añadir como Destino",
        "modal_add_title": "Añadir Canal de {type}",
        "modal_cid_label": "ID de Canal a Añadir",
        "added_msg": "✅ ¡Se añadió {channel} a **{type}** del grupo **[{name}]**!",
        "group_deleted": "🗑️ Se eliminó el grupo **[{name}]**.",
        "reset_warning": "⚠️ **¿Está seguro de que desea restablecer todas las configuraciones?**",
        "btn_confirm_reset": "Restablecer Todo",
        "btn_cancel": "Cancelar",
        "reset_complete": "💥 **Se han restablecido todas las configuraciones.**",
        "reset_cancelled": "Restablecimiento cancelado.",
        "embed_title": "🔗 Abrir publicación original (Hilo)",
        "embed_desc": "📷 Publicado por **{author}** (desde #{channel})"
    },
    "fr": {
        "map_title": "🗺️ **Carte Globale Actuelle :**",
        "no_groups": "(Aucun groupe configuré)",
        "source": "Source",
        "dest": "Destination",
        "none": "Aucun",
        "menu_prompt": "Veuillez sélectionner une action :",
        "btn_add": "Ajouter / Modifier un Groupe",
        "btn_del": "Supprimer un Groupe",
        "select_edit_group": "Sélectionnez un groupe à ajouter ou modifier :",
        "select_del_group": "Sélectionnez un groupe à supprimer :",
        "new_group_option": "➕ Créer un Nouveau Groupe",
        "modal_new_title": "Créer un Nouveau Groupe",
        "modal_gname_label": "Nom du Groupe",
        "modal_src_label": "ID du Canal Source",
        "modal_dest_label": "ID du Canal Destination",
        "invalid_id": "⚠️ Les ID de canal doivent être des chiffres.",
        "created_msg": "✅ Groupe **[{name}]** créé !",
        "select_target_type": "Sélectionnez le type pour **[{name}]** et entrez l'ID du canal.",
        "btn_add_src": "Ajouter comme Source",
        "btn_add_dest": "Ajouter comme Destination",
        "modal_add_title": "Ajouter un Canal {type}",
        "modal_cid_label": "ID du Canal à Ajouter",
        "added_msg": "✅ {channel} ajouté à **{type}** pour le groupe **[{name}]** !",
        "group_deleted": "🗑️ Groupe **[{name}]** supprimé.",
        "reset_warning": "⚠️ **Voulez-vous vraiment réinitialiser tous les paramètres ?**",
        "btn_confirm_reset": "Tout Réinitialiser",
        "btn_cancel": "Annuler",
        "reset_complete": "💥 **Tous les paramètres du groupe ont été réinitialisés.**",
        "reset_cancelled": "Réinitialisation annulée.",
        "embed_title": "🔗 Ouvrir le message d'origine (Fil)",
        "embed_desc": "📷 Publié par **{author}** (depuis #{channel})"
    },
    "de": {
        "map_title": "🗺️ **Aktuelle Gesamtübersicht:**",
        "no_groups": "(Keine Gruppen konfiguriert)",
        "source": "Quelle",
        "dest": "Ziel",
        "none": "Keine",
        "menu_prompt": "Bitte wählen Sie eine Aktion:",
        "btn_add": "Gruppe Hinzufügen / Bearbeiten",
        "btn_del": "Gruppe Löschen",
        "select_edit_group": "Gruppe zum Hinzufügen oder Bearbeiten auswählen:",
        "select_del_group": "Gruppe zum Löschen auswählen:",
        "new_group_option": "➕ Neue Gruppe Erstellen",
        "modal_new_title": "Neue Gruppe Erstellen",
        "modal_gname_label": "Gruppenname",
        "modal_src_label": "Quell-Kanal-ID",
        "modal_dest_label": "Ziel-Kanal-ID",
        "invalid_id": "⚠️ Kanal-IDs müssen Zahlen sein.",
        "created_msg": "✅ Gruppe **[{name}]** erstellt!",
        "select_target_type": "Typ für **[{name}]** auswählen und Kanal-ID eingeben.",
        "btn_add_src": "Als Quelle Hinzufügen",
        "btn_add_dest": "Als Ziel Hinzufügen",
        "modal_add_title": "{type}-Kanal Hinzufügen",
        "modal_cid_label": "Hinzuzufügende Kanal-ID",
        "added_msg": "✅ {channel} zu **{type}** der Gruppe **[{name}]** hinzugefügt!",
        "group_deleted": "🗑️ Gruppe **[{name}]** gelöscht.",
        "reset_warning": "⚠️ **Möchten Sie wirklich alle Einstellungen zurücksetzen?**",
        "btn_confirm_reset": "Alles Zurücksetzen",
        "btn_cancel": "Abbrechen",
        "reset_complete": "💥 **Alle Gruppeneinstellungen wurden zurückgesetzt.**",
        "reset_cancelled": "Zurücksetzen abgebrochen.",
        "embed_title": "🔗 Originalbeitrag (Thread) öffnen",
        "embed_desc": "📷 Gepostet von **{author}** (aus #{channel})"
    },
    "it": {
        "map_title": "🗺️ **Mappa Generale Attuale:**",
        "no_groups": "(Nessun gruppo configurato)",
        "source": "Sorgente",
        "dest": "Destinazione",
        "none": "Nessuno",
        "menu_prompt": "Seleziona un'azione:",
        "btn_add": "Aggiungi / Modifica Gruppo",
        "btn_del": "Elimina Gruppo",
        "select_edit_group": "Seleziona un gruppo da aggiungere o modificare:",
        "select_del_group": "Seleziona un gruppo da eliminare:",
        "new_group_option": "➕ Crea Nuovo Gruppo",
        "modal_new_title": "Crea Nuovo Gruppo",
        "modal_gname_label": "Nome del Gruppo",
        "modal_src_label": "ID Canale Sorgente",
        "modal_dest_label": "ID Canale Destinazione",
        "invalid_id": "⚠️ Gli ID canale devono essere numeri.",
        "created_msg": "✅ Gruppo **[{name}]** creato!",
        "select_target_type": "Seleziona tipo per **[{name}]** e inserisci l'ID canale.",
        "btn_add_src": "Aggiungi come Sorgente",
        "btn_add_dest": "Aggiungi come Destinazione",
        "modal_add_title": "Aggiungi Canale {type}",
        "modal_cid_label": "ID Canale da Aggiungere",
        "added_msg": "✅ Aggiunto {channel} a **{type}** del gruppo **[{name}]**!",
        "group_deleted": "🗑️ Gruppo **[{name}]** eliminato.",
        "reset_warning": "⚠️ **Sei sicuro di voler ripristinare tutte le impostazioni?**",
        "btn_confirm_reset": "Ripristina Tutto",
        "btn_cancel": "Annulla",
        "reset_complete": "💥 **Tutte le impostazioni del gruppo sono state ripristinate.**",
        "reset_cancelled": "Ripristino annullato.",
        "embed_title": "🔗 Apri post originale (Thread)",
        "embed_desc": "📷 Pubblicato da **{author}** (da #{channel})"
    },
    "ru": {
        "map_title": "🗺️ **Текущая общая карта:**",
        "no_groups": "(Группы не настроены)",
        "source": "Источник",
        "dest": "Назначение",
        "none": "Нет",
        "menu_prompt": "Выберите действие:",
        "btn_add": "Добавить / Изменить группу",
        "btn_del": "Удалить группу",
        "select_edit_group": "Выберите группу для добавления или изменения:",
        "select_del_group": "Выберите группу для удаления:",
        "new_group_option": "➕ Создать новую группу",
        "modal_new_title": "Создание новой группы",
        "modal_gname_label": "Название группы",
        "modal_src_label": "ID канала-источника",
        "modal_dest_label": "ID канала-назначения",
        "invalid_id": "⚠️ ID каналов должны быть числами.",
        "created_msg": "✅ Группа **[{name}]** создана!",
        "select_target_type": "Выберите тип для **[{name}]** и введите ID канала.",
        "btn_add_src": "Добавить как источник",
        "btn_add_dest": "Добавить как назначение",
        "modal_add_title": "Добавить канал ({type})",
        "modal_cid_label": "ID добавляемого канала",
        "added_msg": "✅ {channel} добавлен в **{type}** группы **[{name}]**!",
        "group_deleted": "🗑️ Группа **[{name}]** удалена.",
        "reset_warning": "⚠️ **Вы уверены, что хотите сбросить все настройки?**",
        "btn_confirm_reset": "Сбросить все",
        "btn_cancel": "Отмена",
        "reset_complete": "💥 **Все настройки групп сброшены.**",
        "reset_cancelled": "Сброс отменен.",
        "embed_title": "🔗 Открыть исходную публикацию (ветку)",
        "embed_desc": "📷 Опубликовал **{author}** (из #{channel})"
    },
    "pt": {
        "map_title": "🗺️ **Mapa Geral Atual:**",
        "no_groups": "(Nenhum grupo configurado)",
        "source": "Origem",
        "dest": "Destino",
        "none": "Nenhum",
        "menu_prompt": "Selecione uma ação:",
        "btn_add": "Adicionar / Editar Grupo",
        "btn_del": "Excluir Grupo",
        "select_edit_group": "Selecione um grupo para adicionar ou editar:",
        "select_del_group": "Selecione um grupo para excluir:",
        "new_group_option": "➕ Criar Novo Grupo",
        "modal_new_title": "Criar Novo Grupo",
        "modal_gname_label": "Nome do Grupo",
        "modal_src_label": "ID do Canal de Origem",
        "modal_dest_label": "ID do Canal de Destino",
        "invalid_id": "⚠️ Os IDs dos canais devem ser números.",
        "created_msg": "✅ Grupo **[{name}]** criado!",
        "select_target_type": "Selecione o tipo para **[{name}]** e insira o ID do canal.",
        "btn_add_src": "Adicionar como Origem",
        "btn_add_dest": "Adicionar como Destino",
        "modal_add_title": "Adicionar Canal de {type}",
        "modal_cid_label": "ID do Canal a Adicionar",
        "added_msg": "✅ Adicionado {channel} a **{type}** do grupo **[{name}]**!",
        "group_deleted": "🗑️ Grupo **[{name}]** excluído.",
        "reset_warning": "⚠️ **Tem certeza de que deseja redefinir todas as configurações?**",
        "btn_confirm_reset": "Redefinir Tudo",
        "btn_cancel": "Cancelar",
        "reset_complete": "💥 **Todas as configurações do grupo foram redefinidas.**",
        "reset_cancelled": "Redefinição cancelada.",
        "embed_title": "🔗 Abrir publicação original (Tópico)",
        "embed_desc": "📷 Postado por **{author}** (de #{channel})"
    },
    "th": {
        "map_title": "🗺️ **แผนผังภาพรวมปัจจุบัน:**",
        "no_groups": "(ยังไม่ได้ตั้งค่ากลุ่ม)",
        "source": "ต้นทาง",
        "dest": "ปลายทาง",
        "none": "ไม่มี",
        "menu_prompt": "โปรดเลือกดำเนินการ:",
        "btn_add": "เพิ่ม / แก้ไขกลุ่ม",
        "btn_del": "ลบกลุ่ม",
        "select_edit_group": "เลือกกลุ่มที่ต้องการเพิ่มหรือแก้ไข:",
        "select_del_group": "เลือกกลุ่มที่ต้องการลบ:",
        "new_group_option": "➕ สร้างกลุ่มใหม่",
        "modal_new_title": "สร้างกลุ่มใหม่",
        "modal_gname_label": "ชื่อกลุ่ม",
        "modal_src_label": "ID ช่องต้นทาง",
        "modal_dest_label": "ID ช่องปลายทาง",
        "invalid_id": "⚠️ ID ช่องต้องเป็นตัวเลขเท่านั้น",
        "created_msg": "✅ สร้างกลุ่ม **[{name}]** เรียบร้อยแล้ว!",
        "select_target_type": "เลือกประเภทที่จะเพิ่มสำหรับ **[{name}]** และกรอก ID ช่อง",
        "btn_add_src": "เพิ่มเป็นต้นทาง",
        "btn_add_dest": "เพิ่มเป็นปลายทาง",
        "modal_add_title": "เพิ่มช่อง{type}",
        "modal_cid_label": "ID ช่องที่ต้องการเพิ่ม",
        "added_msg": "✅ เพิ่ม {channel} เข้าใน **{type}** ของกลุ่ม **[{name}]** เรียบร้อยแล้ว!",
        "group_deleted": "🗑️ ลบกลุ่ม **[{name}]** เรียบร้อยแล้ว",
        "reset_warning": "⚠️ **คุณแน่ใจหรือไม่ว่าต้องการรีเซ็ตการตั้งค่าทั้งหมด?**",
        "btn_confirm_reset": "ลบการตั้งค่าทั้งหมด",
        "btn_cancel": "ยกเลิก",
        "reset_complete": "💥 **รีเซ็ตการตั้งค่ากลุ่มทั้งหมดเรียบร้อยแล้ว**",
        "reset_cancelled": "ยกเลิกการรีเซ็ตเรียบร้อยแล้ว",
        "embed_title": "🔗 เปิดโพสต์ดั้งเดิม (ไธรด)",
        "embed_desc": "📷 โพสต์โดย **{author}** (จาก #{channel})"
    },
    "vi": {
        "map_title": "🗺️ **Bản đồ tổng thể hiện tại:**",
        "no_groups": "(Chưa có nhóm nào được cấu hình)",
        "source": "Nguồn",
        "dest": "Đích",
        "none": "Không có",
        "menu_prompt": "Vui lòng chọn một thao tác:",
        "btn_add": "Thêm / Sửa Nhóm",
        "btn_del": "Xóa Nhóm",
        "select_edit_group": "Chọn nhóm để thêm hoặc sửa:",
        "select_del_group": "Chọn nhóm để xóa:",
        "new_group_option": "➕ Tạo Nhóm Mới",
        "modal_new_title": "Tạo Nhóm Mới",
        "modal_gname_label": "Tên Nhóm",
        "modal_src_label": "ID Kênh Nguồn",
        "modal_dest_label": "ID Kênh Đích",
        "invalid_id": "⚠️ ID kênh phải là chữ số.",
        "created_msg": "✅ Đã tạo nhóm **[{name}]**!",
        "select_target_type": "Chọn loại mục tiêu cho **[{name}]** và nhập ID kênh.",
        "btn_add_src": "Thêm làm Nguồn",
        "btn_add_dest": "Thêm làm Đích",
        "modal_add_title": "Thêm Kênh {type}",
        "modal_cid_label": "ID Kênh Cần Thêm",
        "added_msg": "✅ Đã thêm {channel} vào **{type}** của nhóm **[{name}]**!",
        "group_deleted": "🗑️ Đã xóa nhóm **[{name}]**.",
        "reset_warning": "⚠️ **Bạn có chắc chắn muốn đặt lại tất cả cài đặt không?**",
        "btn_confirm_reset": "Đặt Lại Tất Cả",
        "btn_cancel": "Hủy",
        "reset_complete": "💥 **Đã xóa tất cả cài đặt nhóm.**",
        "reset_cancelled": "Đã hủy đặt lại.",
        "embed_title": "🔗 Mở bài viết gốc (Luồng)",
        "embed_desc": "📷 Đăng bởi **{author}** (từ #{channel})"
    }
}

# 表示用：言語コードと国旗・言語名のマッピング
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
    lang = locale_str.split('-')[0].lower() if locale_str else "en"
    if lang not in TEXTS:
        lang = "en"
    return TEXTS[lang].get(key, TEXTS["en"].get(key, key))

def get_lang_display(lang_code: str, guild_locale: str) -> str:
    if not lang_code or lang_code == "default":
        actual_lang = guild_locale.split('-')[0].lower()
        base_str = LANG_MAP.get(actual_lang, f"🌐 {actual_lang}")
        return f"{base_str} (サーバー設定)"
    return LANG_MAP.get(lang_code, f"🌐 {lang_code}")

def get_guild_language_setting(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT main_lang, sub_langs FROM guild_languages WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0] or "default", row[1] or ""
    return "default", ""

# ==========================================
# 🤖 Discord Bot の初期化
# ==========================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def build_group_map_text(guild_id: int, locale: discord.Locale) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT group_name, channel_id, type FROM group_channels WHERE guild_id = ? ORDER BY group_name', (guild_id,))
    rows = c.fetchall()
    conn.close()

    map_title = get_text(str(locale), "map_title")
    if not rows:
        return f"{map_title}\n{get_text(str(locale), 'no_groups')}"

    groups = {}
    for gname, cid, ctype in rows:
        if gname not in groups:
            groups[gname] = {"source": [], "dest": []}
        groups[gname][ctype].append(cid)

    map_text = f"{map_title}\n"
    for gname, data in groups.items():
        map_text += f"\n📁 **[{gname}]**\n"
        src_list = [bot.get_channel(cid).mention if bot.get_channel(cid) else f"ID:{cid}" for cid in data["source"]]
        src_str = ", ".join(src_list) if src_list else get_text(str(locale), "none")
        map_text += f"  ├ 📥 **{get_text(str(locale), 'source')}**: {src_str}\n"
        dest_list = [bot.get_channel(cid).mention if bot.get_channel(cid) else f"ID:{cid}" for cid in data["dest"]]
        dest_str = ", ".join(dest_list) if dest_list else get_text(str(locale), "none")
        map_text += f"  └ 📤 **{get_text(str(locale), 'dest')}**: {dest_str}\n"

    return map_text

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    clean_old_messages.start()

# ==========================================
# 🗣️ UIパーツ（言語設定 /set_language フロー）
# ==========================================

class LanguageSettingView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale

    @discord.ui.button(label="メイン言語を変更する", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="edit_main")
    async def edit_main_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainLangSelectView(self.guild_id, self.locale)
        await interaction.response.edit_message(content="変更するメイン言語を選択してください：\n(※選択すると即座に反映されます)", view=view)

    @discord.ui.button(label="サブ言語を追加・編集する", style=discord.ButtonStyle.success, emoji="🌍", custom_id="edit_sub")
    async def edit_sub_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = SubLangSelectView(self.guild_id, self.locale)
        await interaction.response.edit_message(content="追加するサブ言語を選択してください（複数選択可）。\n※「サブ言語なし」を選ぶとクリアされます。\n※選んだ順番で表示されます。", view=view)

class MainLangSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label=f"{label}", value=code) for code, label in LANG_MAP.items()]
        select = discord.ui.Select(placeholder="メイン言語を選択してください", min_values=1, max_values=1, options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_lang = interaction.data["values"][0]
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO guild_languages (guild_id, main_lang) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET main_lang = ?', (self.guild_id, selected_lang, selected_lang))
        conn.commit()
        conn.close()

        await send_language_menu(interaction, self.guild_id, self.locale, edit=True)

class SubLangSelectView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.locale = locale
        
        options = [discord.SelectOption(label="🚫 サブ言語なし (クリア)", value="none", description="追加の言語表示をオフにします")]
        options.extend([discord.SelectOption(label=f"{label}", value=code) for code, label in LANG_MAP.items()])
        
        # Discordのセレクトメニューは何も選ばないと送信できないため、「サブ言語なし」を含める
        select = discord.ui.Select(placeholder="サブ言語を選択（複数選択可）", min_values=1, max_values=len(LANG_MAP), options=options[:25])
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_langs = interaction.data["values"]
        if "none" in selected_langs:
            sub_langs_str = ""
        else:
            sub_langs_str = ",".join(selected_langs)

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO guild_languages (guild_id, sub_langs) 
            VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET sub_langs = ?
        ''', (self.guild_id, sub_langs_str, sub_langs_str))
        conn.commit()
        conn.close()

        await send_language_menu(interaction, self.guild_id, self.locale, edit=True)

async def send_language_menu(interaction: discord.Interaction, guild_id: int, locale: discord.Locale, edit=False):
    main_lang, sub_langs = get_guild_language_setting(guild_id)
    server_locale_str = str(interaction.guild.preferred_locale) if interaction.guild else "en"
    
    main_display = get_lang_display(main_lang, server_locale_str)
    
    if sub_langs:
        sub_list = [LANG_MAP.get(l, l) for l in sub_langs.split(',')]
        sub_display = "\n".join([f"  ・{sl}" for sl in sub_list])
    else:
        sub_display = "  ・(なし)"

    msg = (
        f"**【現在の転送先表示言語設定】**\n\n"
        f"👑 **メイン言語**: {main_display}\n"
        f"🌍 **サブ言語**:\n{sub_display}\n\n"
        f"設定を変更する場合は、下のボタンを選択してください。"
    )
    
    view = LanguageSettingView(guild_id, locale)
    if edit:
        await interaction.response.edit_message(content=msg, view=view)
    else:
        await interaction.response.send_message(content=msg, view=view, ephemeral=True)

# ==========================================
# 🛠️ UIパーツ（/set_group フロー）
# ==========================================

class SetGroupOpView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.locale = locale

        self.add_btn.label = get_text(str(locale), "btn_add")
        self.del_btn.label = get_text(str(locale), "btn_del")

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="✏️", custom_id="add_btn")
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        groups = [row[0] for row in c.fetchall()]
        conn.close()

        view = GroupSelectForEditView(self.guild_id, groups, self.locale)
        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_edit_group')}"
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="del_btn")
    async def del_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        groups = [row[0] for row in c.fetchall()]
        conn.close()

        if not groups:
            map_text = build_group_map_text(self.guild_id, self.locale)
            await interaction.response.edit_message(content=map_text, view=None)
            return

        view = GroupSelectForDeleteView(self.guild_id, groups, self.locale)
        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_del_group')}"
        await interaction.response.edit_message(content=msg, view=view)


class GroupSelectForEditView(discord.ui.View):
    def __init__(self, guild_id: int, groups: list, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.locale = locale

        options = [discord.SelectOption(label=get_text(str(locale), "new_group_option"), value="__NEW__", emoji="➕")]
        # Max 25 個の制約に収めるためグループ数は最大 24 個に絞り込み
        options.extend([discord.SelectOption(label=g, value=g, emoji="📁") for g in groups[:24]])

        select = discord.ui.Select(placeholder="...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        if selected == "__NEW__":
            modal = NewGroupModal(self.guild_id, self.locale)
            await interaction.response.send_modal(modal)
        else:
            view = AddTypeTargetView(self.guild_id, selected, self.locale)
            map_text = build_group_map_text(self.guild_id, self.locale)
            msg = f"{map_text}\n\n{get_text(str(self.locale), 'select_target_type').format(name=selected)}"
            await interaction.response.edit_message(content=msg, view=view)


class NewGroupModal(discord.ui.Modal):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(title=get_text(str(locale), "modal_new_title"))
        self.guild_id = guild_id
        self.locale = locale

        self.group_name_input = discord.ui.TextInput(
            label=get_text(str(locale), "modal_gname_label"),
            placeholder="Ex: Group-A",
            required=True
        )
        self.source_id_input = discord.ui.TextInput(
            label=get_text(str(locale), "modal_src_label"),
            placeholder="Ex: 123456789...",
            required=True
        )
        self.dest_id_input = discord.ui.TextInput(
            label=get_text(str(locale), "modal_dest_label"),
            placeholder="Ex: 987654321...",
            required=True
        )
        self.add_item(self.group_name_input)
        self.add_item(self.source_id_input)
        self.add_item(self.dest_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        gname = self.group_name_input.value.strip()
        try:
            src_id = int(self.source_id_input.value.strip())
            dest_id = int(self.dest_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message(get_text(str(self.locale), "invalid_id"), ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, "source")', (self.guild_id, gname, src_id))
        c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, "dest")', (self.guild_id, gname, dest_id))
        conn.commit()
        conn.close()

        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'created_msg').format(name=gname)}"
        
        # Modal 応答時は defer して元のメッセージを編集するのが安全
        await interaction.response.defer()
        await interaction.message.edit(content=msg, view=None)


class AddTypeTargetView(discord.ui.View):
    def __init__(self, guild_id: int, group_name: str, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.group_name = group_name
        self.locale = locale

        self.src_btn.label = get_text(str(locale), "btn_add_src")
        self.dest_btn.label = get_text(str(locale), "btn_add_dest")

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="📥", custom_id="src_btn")
    async def src_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelAddModal(self.guild_id, self.group_name, "source", self.locale)
        await interaction.response.send_modal(modal)

    @discord.ui.button(style=discord.ButtonStyle.success, emoji="📤", custom_id="dest_btn")
    async def dest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelAddModal(self.guild_id, self.group_name, "dest", self.locale)
        await interaction.response.send_modal(modal)


class ChannelAddModal(discord.ui.Modal):
    def __init__(self, guild_id: int, group_name: str, channel_type: str, locale: discord.Locale):
        t_label = get_text(str(locale), "source" if channel_type == "source" else "dest")
        super().__init__(title=get_text(str(locale), "modal_add_title").format(type=t_label))
        
        self.guild_id = guild_id
        self.group_name = group_name
        self.channel_type = channel_type
        self.locale = locale

        self.cid_input = discord.ui.TextInput(
            label=get_text(str(locale), "modal_cid_label"),
            placeholder="Ex: 123456789...",
            required=True
        )
        self.add_item(self.cid_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cid = int(self.cid_input.value.strip())
        except ValueError:
            await interaction.response.send_message(get_text(str(self.locale), "invalid_id"), ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, ?)', (self.guild_id, self.group_name, cid, self.channel_type))
        conn.commit()
        conn.close()

        chan = interaction.client.get_channel(cid)
        c_mention = chan.mention if chan else f"ID:{cid}"
        t_label = get_text(str(self.locale), "source" if self.channel_type == "source" else "dest")

        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'added_msg').format(name=self.group_name, type=t_label, channel=c_mention)}"
        
        # Modal 応答時は defer して元のメッセージを編集
        await interaction.response.defer()
        await interaction.message.edit(content=msg, view=None)


class GroupSelectForDeleteView(discord.ui.View):
    def __init__(self, guild_id: int, groups: list, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.locale = locale

        # 最大 25 個の制限を適用
        options = [discord.SelectOption(label=g, value=g, emoji="💥") for g in groups[:25]]
        select = discord.ui.Select(placeholder="...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        group_name = interaction.data["values"][0]

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ?', (self.guild_id, group_name))
        conn.commit()
        conn.close()

        map_text = build_group_map_text(self.guild_id, self.locale)
        msg = f"{map_text}\n\n{get_text(str(self.locale), 'group_deleted').format(name=group_name)}"
        await interaction.response.edit_message(content=msg, view=None)

# ==========================================
# 🚀 スラッシュコマンド
# ==========================================

@bot.tree.command(name="set_group", description="グループの確認・追加編集・削除を行います")
@app_commands.checks.has_permissions(administrator=True)
async def set_group(interaction: discord.Interaction):
    map_text = build_group_map_text(interaction.guild_id, interaction.locale)
    view = SetGroupOpView(interaction.guild_id, interaction.locale)
    msg = f"{map_text}\n\n{get_text(str(interaction.locale), 'menu_prompt')}"
    await interaction.response.send_message(msg, view=view, ephemeral=True)

@bot.tree.command(name="set_language", description="転送先で表示されるメッセージの言語（メイン・サブ）を設定します")
@app_commands.checks.has_permissions(administrator=True)
async def set_language(interaction: discord.Interaction):
    await send_language_menu(interaction, interaction.guild_id, interaction.locale)

@bot.tree.command(name="reset_all_settings", description="【危険】このサーバーのすべての転送グループ設定をリセットします")
@app_commands.checks.has_permissions(administrator=True)
async def reset_all_settings(interaction: discord.Interaction):
    view = ResetConfirmView(interaction.guild_id, interaction.locale)
    msg = get_text(str(interaction.locale), "reset_warning")
    await interaction.response.send_message(msg, view=view, ephemeral=True)

class ResetConfirmView(discord.ui.View):
    def __init__(self, guild_id: int, locale: discord.Locale):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.locale = locale

        self.confirm.label = get_text(str(locale), "btn_confirm_reset")
        self.cancel.label = get_text(str(locale), "btn_cancel")

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM group_channels WHERE guild_id = ?', (self.guild_id,))
        conn.commit()
        conn.close()

        msg = get_text(str(self.locale), "reset_complete")
        await interaction.response.edit_message(content=msg, view=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = get_text(str(self.locale), "reset_cancelled")
        await interaction.response.edit_message(content=msg, view=None)

# ==========================================
# 🔄 転送処理 ＆ 自動削除
# ==========================================

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    channel = message.channel
    parent_id = getattr(channel, "parent_id", None)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT group_name, channel_id FROM group_channels WHERE guild_id = ? AND type = "source"', (message.guild.id,))
    source_rows = c.fetchall()

    dest_ids = []
    image_attachments = []

    for group_name, src_id in source_rows:
        if channel.id == src_id or parent_id == src_id:
            image_attachments = [
                att for att in message.attachments 
                if att.content_type and att.content_type.startswith("image/")
            ]

            if image_attachments:
                c.execute('SELECT channel_id FROM group_channels WHERE guild_id = ? AND group_name = ? AND type = "dest"', (message.guild.id, group_name))
                dest_ids = [row[0] for row in c.fetchall()]
            break

    conn.close()

    if image_attachments and dest_ids:
        # DBから言語設定を取得
        main_lang_code, sub_langs_str = get_guild_language_setting(message.guild.id)
        
        # 実際のメイン言語を決定
        server_locale_str = str(message.guild.preferred_locale)
        actual_main = main_lang_code if main_lang_code != "default" else server_locale_str.split('-')[0].lower()
        
        # メイン言語によるタイトル生成
        title_text = get_text(actual_main, "embed_title")
        
        # メイン言語の説明文生成
        desc_lines = []
        main_desc = get_text(actual_main, "embed_desc").format(
            author=message.author.display_name,
            channel=channel.name
        )
        desc_lines.append(main_desc)
        
        # サブ言語の説明文を追加（設定されている場合）
        if sub_langs_str:
            sub_langs = sub_langs_str.split(',')
            for sl in sub_langs:
                if sl and sl != "none":
                    sl_desc = get_text(sl, "embed_desc").format(
                        author=message.author.display_name,
                        channel=channel.name
                    )
                    # メイン言語の下に並べて表示
                    desc_lines.append(sl_desc)

        final_desc = "\n\n".join(desc_lines)

        for dest_id in dest_ids:
            dest_channel = bot.get_channel(dest_id)
            if dest_channel:
                jump_url = message.jump_url
                for att in image_attachments:
                    file = await att.to_file()
                    embed = discord.Embed(
                        title=title_text,
                        url=jump_url,
                        description=final_desc,
                        color=discord.Color.blue()
                    )
                    embed.set_image(url=f"attachment://{file.filename}")
                    await dest_channel.send(embed=embed, file=file)

@tasks.loop(hours=12)
async def clean_old_messages():
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DELETE_AFTER_DAYS)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT DISTINCT channel_id FROM group_channels WHERE type = "dest"')
    dest_ids = [row[0] for row in c.fetchall()]
    conn.close()

    for dest_id in dest_ids:
        dest_channel = bot.get_channel(dest_id)
        if not dest_channel:
            continue

        async for message in dest_channel.history(limit=None):
            if message.created_at < cutoff:
                try:
                    if (now - message.created_at).days < 14:
                        await dest_channel.purge(limit=100, check=lambda m: m.created_at < cutoff)
                        break
                    else:
                        await message.delete()
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"削除エラー: {e}")

bot.run(BOT_TOKEN)
