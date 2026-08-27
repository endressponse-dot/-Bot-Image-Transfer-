import sqlite3
import discord
from config import DB_FILE, DEFAULT_DELETE_AFTER_DAYS

# ==========================================
# 1. データベース初期化
# ==========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 転送グループのチャンネルマッピング
    c.execute('''
    CREATE TABLE IF NOT EXISTS group_channels (
        guild_id INTEGER,
        group_name TEXT,
        channel_id INTEGER,
        type TEXT
    )
    ''')
    
    # グループごとの個別設定（説明文・保持日数）
    c.execute('''
    CREATE TABLE IF NOT EXISTS group_settings (
        guild_id INTEGER,
        group_name TEXT,
        description TEXT,
        retention_days INTEGER DEFAULT 7,
        PRIMARY KEY (guild_id, group_name)
    )
    ''')
    
    # サーバーごとの言語設定 (メイン言語 + カンマ区切りのサブ言語リスト)
    c.execute('''
    CREATE TABLE IF NOT EXISTS guild_languages (
        guild_id INTEGER PRIMARY KEY,
        main_lang TEXT,
        sub_langs TEXT
    )
    ''')

    # 自動昇格ルール（リアクション数による昇格閾値設定）
    c.execute('''
    CREATE TABLE IF NOT EXISTS promotion_rules (
        guild_id INTEGER,
        group_name TEXT,
        emoji TEXT,
        threshold INTEGER,
        PRIMARY KEY (guild_id, group_name, emoji)
    )
    ''')

    # 既存DBへの安全策：promotion_rules に emoji カラムが存在しない古い構造の場合、自動追加
    c.execute("PRAGMA table_info(promotion_rules)")
    columns = [column[1] for column in c.fetchall()]
    if columns and "emoji" not in columns:
        c.execute("ALTER TABLE promotion_rules ADD COLUMN emoji TEXT DEFAULT '⭐'")

    # 二重転送防止・記録用（メッセージ転送履歴）
    c.execute('''
    CREATE TABLE IF NOT EXISTS forwarded_messages (
        original_message_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        group_name TEXT,
        forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 自動昇格メッセージ・作成されたスレッドの記録用テーブル
    c.execute('''
    CREATE TABLE IF NOT EXISTS promoted_messages (
        original_message_id INTEGER PRIMARY KEY,
        promoted_message_id INTEGER,
        thread_id INTEGER,
        guild_id INTEGER,
        group_name TEXT,
        promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


# ==========================================
# 2. 設定テキスト構築・一覧取得関数
# ==========================================

def build_group_map_text(guild_id: int, locale) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT group_name, channel_id, type FROM group_channels WHERE guild_id = ?', (guild_id,))
    rows = c.fetchall()
    
    c.execute('SELECT group_name, description, retention_days FROM group_settings WHERE guild_id = ?', (guild_id,))
    settings_rows = c.fetchall()

    # サーバー言語設定の取得
    c.execute('SELECT main_lang, sub_langs FROM guild_languages WHERE guild_id = ?', (guild_id,))
    lang_row = c.fetchone()
    conn.close()

    main_lang = lang_row[0] if lang_row and lang_row[0] else "ja"
    sub_langs = lang_row[1] if lang_row and lang_row[1] else "なし"

    settings_map = {
        r[0]: {
            "desc": r[1] if r[1] else "",
            "days": r[2] if r[2] is not None else DEFAULT_DELETE_AFTER_DAYS
        }
        for r in settings_rows
    }

    groups = {}
    for g_name, ch_id, ch_type in rows:
        if g_name not in groups:
            groups[g_name] = {"src": [], "dest": []}
        groups[g_name][ch_type].append(ch_id)

    lines = [f"🌐 **サーバー言語設定**: メイン: `{main_lang}` / サブ: `{sub_langs}`\n"]

    if not groups:
        lines.append("📋 **転送グループ設定一覧**: 設定されているグループはありません。")
        return "\n".join(lines)

    lines.append("📋 **転送グループ設定一覧**:")
    for g_name, data in groups.items():
        desc = settings_map.get(g_name, {}).get("desc", "")
        days = settings_map.get(g_name, {}).get("days", DEFAULT_DELETE_AFTER_DAYS)
        
        desc_str = f" (*{desc}*)" if desc else ""
        days_str = f" ⏳ 保持: {days}日間" if days > 0 else " ⏳ 保持: 無制限"
        lines.append(f"\n🔹 **グループ: {g_name}**{desc_str}{days_str}")
        
        src_names = [f"<#{cid}>" for cid in data["src"]]
        dest_names = [f"<#{cid}>" for cid in data["dest"]]
        
        src_str = ', '.join(src_names) if src_names else '未設定'
        dest_str = ', '.join(dest_names) if dest_names else '未設定'
        
        lines.append(f" ├ 転送元 (Source): {src_str}")
        lines.append(f" └ 転送先 (Dest): {dest_str}")

    return "\n".join(lines)


def get_all_group_names(guild_id: int) -> list[str]:
    """
    ui_group.py のドロップダウンメニュー構築用。
    group_channels および group_settings から重複しないグループ名一覧を取得します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    SELECT DISTINCT group_name FROM (
        SELECT group_name FROM group_channels WHERE guild_id = ?
        UNION
        SELECT group_name FROM group_settings WHERE guild_id = ?
    )
    ''', (guild_id, guild_id))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


# ==========================================
# 3. チャンネル・グループ追加・削除
# ==========================================

def add_group_channel(guild_id: int, group_name: str, channel_id: int, ch_type: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO group_channels (guild_id, group_name, channel_id, type) VALUES (?, ?, ?, ?)',
              (guild_id, group_name, channel_id, ch_type))
    conn.commit()
    conn.close()

def delete_group_channel(guild_id: int, group_name: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    c.execute('DELETE FROM group_settings WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    c.execute('DELETE FROM promotion_rules WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    conn.commit()
    conn.close()


# ==========================================
# 4. グループ個別設定（説明文・保持期間）
# ==========================================

def set_group_description(guild_id: int, group_name: str, description: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT INTO group_settings (guild_id, group_name, description)
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id, group_name) DO UPDATE SET description = excluded.description
    ''', (guild_id, group_name, description))
    conn.commit()
    conn.close()

def set_group_retention_days(guild_id: int, group_name: str, days: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT INTO group_settings (guild_id, group_name, retention_days)
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id, group_name) DO UPDATE SET retention_days = excluded.retention_days
    ''', (guild_id, group_name, days))
    conn.commit()
    conn.close()

def get_group_retention_days(guild_id: int, group_name: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT retention_days FROM group_settings WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    row = c.fetchone()
    conn.close()
    if row and row[0] is not None:
        return row[0]
    return DEFAULT_DELETE_AFTER_DAYS


# ==========================================
# 5. 言語設定（メイン言語・複数サブ言語）追加関数
# ==========================================

def set_guild_languages(guild_id: int, main_lang: str, sub_langs: list):
    """
    サーバーのメイン言語とサブ言語のリストをDBに保存します。
    """
    sub_langs_str = ",".join(sub_langs) if sub_langs else ""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT INTO guild_languages (guild_id, main_lang, sub_langs)
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET 
        main_lang = excluded.main_lang,
        sub_langs = excluded.sub_langs
    ''', (guild_id, main_lang, sub_langs_str))
    conn.commit()
    conn.close()

def get_guild_language_setting(guild_id: int):
    """
    サーバーの言語設定を取得します。
    返り値: (メイン言語str, サブ言語のリストlist) 例: ("ja", ["en", "zh-cn"])
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT main_lang, sub_langs FROM guild_languages WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        main_lang = row[0] if row[0] else "ja"
        sub_langs = [s.strip() for s in row[1].split(",") if s.strip()] if row[1] else []
        return main_lang, sub_langs
    return "ja", []


# ==========================================
# 6. 自動昇格ルール管理関数
# ==========================================

def set_promotion_rule(guild_id: int, group_name: str, emoji: str, threshold: int):
    """
    指定されたグループに昇格用のリアクション絵文字と閾値を設定します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT INTO promotion_rules (guild_id, group_name, emoji, threshold)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(guild_id, group_name, emoji) DO UPDATE SET threshold = excluded.threshold
    ''', (guild_id, group_name, emoji, threshold))
    conn.commit()
    conn.close()

def get_promotion_rules(guild_id: int, group_name: str) -> list[dict]:
    """
    グループに紐づく昇格ルールの一覧を取得します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT emoji, threshold FROM promotion_rules WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    rows = c.fetchall()
    conn.close()
    return [{"emoji": r[0], "threshold": r[1]} for r in rows]

def remove_promotion_rule(guild_id: int, group_name: str, emoji: str):
    """
    指定された昇格ルールを削除します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM promotion_rules WHERE guild_id = ? AND group_name = ? AND emoji = ?', (guild_id, group_name, emoji))
    conn.commit()
    conn.close()


# ==========================================
# 7. 二重転送防止（転送済みメッセージ記録）関数
# ==========================================

def is_message_forwarded(original_message_id: int) -> bool:
    """
    メッセージがすでに転送済みかどうかを確認します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM forwarded_messages WHERE original_message_id = ?', (original_message_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def record_forwarded_message(original_message_id: int, guild_id: int, group_name: str):
    """
    転送処理を実行したメッセージIDを記録して重複を防ぎます。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT OR IGNORE INTO forwarded_messages (original_message_id, guild_id, group_name)
    VALUES (?, ?, ?)
    ''', (original_message_id, guild_id, group_name))
    conn.commit()
    conn.close()


# ==========================================
# 8. 昇格メッセージ・スレッド履歴管理関数
# ==========================================

def is_message_promoted(original_message_id: int) -> bool:
    """
    メッセージがすでに昇格（画展等へ転送）済みかチェックします。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM promoted_messages WHERE original_message_id = ?', (original_message_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def record_promoted_message(original_message_id: int, promoted_message_id: int, thread_id: int, guild_id: int, group_name: str):
    """
    昇格処理を行ったメッセージID、転送先メッセージID、作成したスレッドIDを記録します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    INSERT OR REPLACE INTO promoted_messages (original_message_id, promoted_message_id, thread_id, guild_id, group_name)
    VALUES (?, ?, ?, ?, ?)
    ''', (original_message_id, promoted_message_id, thread_id, guild_id, group_name))
    conn.commit()
    conn.close()

def get_promoted_message_info(original_message_id: int) -> dict | None:
    """
    元のメッセージIDから、昇格先メッセージIDやスレッドIDを取得します。
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
    SELECT promoted_message_id, thread_id, group_name 
    FROM promoted_messages 
    WHERE original_message_id = ?
    ''', (original_message_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "promoted_message_id": row[0],
            "thread_id": row[1],
            "group_name": row[2]
        }
    return None
