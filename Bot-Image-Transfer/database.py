import sqlite3
from config import DB_FILE
from locales import get_text

def init_db():
    """データベーステーブルの初期化"""
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
            main_lang TEXT DEFAULT 'default',
            sub_langs TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()

def get_guild_language_setting(guild_id: int):
    """ギルドの言語設定（メイン言語, サブ言語文字列）を取得"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT main_lang, sub_langs FROM guild_languages WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0] or "default", row[1] or ""
    return "default", ""

def set_guild_main_lang(guild_id: int, main_lang: str):
    """ギルドのメイン言語を更新"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO guild_languages (guild_id, main_lang) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET main_lang = ?
    ''', (guild_id, main_lang, main_lang))
    conn.commit()
    conn.close()

def set_guild_sub_langs(guild_id: int, sub_langs_str: str):
    """ギルドのサブ言語を更新"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO guild_languages (guild_id, sub_langs) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET sub_langs = ?
    ''', (guild_id, sub_langs_str, sub_langs_str))
    conn.commit()
    conn.close()

def get_guild_groups(guild_id: int):
    """登録されているグループ名のリストを取得"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT DISTINCT group_name FROM group_channels WHERE guild_id = ?', (guild_id,))
    groups = [row[0] for row in c.fetchall()]
    conn.close()
    return groups

def add_group_channel(guild_id: int, group_name: str, channel_id: int, channel_type: str):
    """グループチャンネル設定を追加/置換"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO group_channels VALUES (?, ?, ?, ?)', (guild_id, group_name, channel_id, channel_type))
    conn.commit()
    conn.close()

def delete_group(guild_id: int, group_name: str):
    """グループを削除"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM group_channels WHERE guild_id = ? AND group_name = ?', (guild_id, group_name))
    conn.commit()
    conn.close()

def reset_guild_settings(guild_id: int):
    """全グループ設定のリセット"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM group_channels WHERE guild_id = ?', (guild_id,))
    conn.commit()
    conn.close()

def build_group_map_text(guild_id: int, locale, bot_client) -> str:
    """現在の転送マップ文字列を生成"""
    locale_str = str(locale)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT group_name, channel_id, type FROM group_channels WHERE guild_id = ?', (guild_id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return f"{get_text(locale_str, 'map_title')}\n\n{get_text(locale_str, 'no_groups')}"

    groups = {}
    for gname, cid, ctype in rows:
        if gname not in groups:
            groups[gname] = {"source": [], "dest": []}
        chan = bot_client.get_channel(cid)
        c_mention = chan.mention if chan else f"ID:{cid}"
        groups[gname][ctype].append(c_mention)

    lines = [get_text(locale_str, 'map_title')]
    for gname, data in groups.items():
        src_str = ", ".join(data["source"]) if data["source"] else get_text(locale_str, 'none')
        dest_str = ", ".join(data["dest"]) if data["dest"] else get_text(locale_str, 'none')
        lines.append(f"\n📁 **[{gname}]**")
        lines.append(f"  📥 {get_text(locale_str, 'source')}: {src_str}")
        lines.append(f"  📤 {get_text(locale_str, 'dest')}: {dest_str}")

    return "\n".join(lines)