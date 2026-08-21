import sqlite3
from config import DB_FILE, DEFAULT_DELETE_AFTER_DAYS
from locales import get_text

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_channels (
            guild_id INTEGER,
            group_name TEXT,
            channel_id INTEGER,
            type TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_settings (
            guild_id INTEGER,
            group_name TEXT,
            description TEXT,
            retention_days INTEGER DEFAULT 7,
            PRIMARY KEY (guild_id, group_name)
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

def build_group_map_text(guild_id: int, locale, bot) -> str:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT group_name, channel_id, type FROM group_channels WHERE guild_id = ?', (guild_id,))
    rows = c.fetchall()
    
    c.execute('SELECT group_name, description, retention_days FROM group_settings WHERE guild_id = ?', (guild_id,))
    settings_rows = c.fetchall()
    conn.close()

    settings_map = {r[0]: {"desc": r[1], "days": r[2] if r[2] is not None else DEFAULT_DELETE_AFTER_DAYS} for r in settings_rows}

    groups = {}
    for g_name, ch_id, ch_type in rows:
        if g_name not in groups:
            groups[g_name] = {"src": [], "dest": []}
        groups[g_name][ch_type].append(ch_id)

    if not groups:
        return "📋 **現在の転送設定**: なし"

    lines = ["📋 **現在のグループ設定一覧**:"]
    for g_name, data in groups.items():
        desc = settings_map.get(g_name, {}).get("desc", "")
        days = settings_map.get(g_name, {}).get("days", DEFAULT_DELETE_AFTER_DAYS)
        
        desc_str = f" (*{desc}*)" if desc else ""
        days_str = f" ⏳ 保持: {days}日間" if days > 0 else " ⏳ 保持: 無制限"
        lines.append(f"\n🔹 **グループ: {g_name}**{desc_str}{days_str}")
        
        src_names = [f"<#{cid}>" for cid in data["src"]]
        dest_names = [f"<#{cid}>" for cid in data["dest"]]
        
        lines.append(f"  ├ 転送元 (Source): {', '.join(src_names) if src_names else '未設定'}")
        lines.append(f"  └ 転送先 (Dest): {', '.join(dest_names) if dest_names else '未設定'}")

    return "\n".join(lines)

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
    conn.commit()
    conn.close()

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

def get_guild_language_setting(guild_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT main_lang, sub_langs FROM guild_languages WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return "default", ""
