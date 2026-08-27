import sqlite3
from config import DB_FILE

def get_connection():
    """データベース接続オブジェクトを取得して返します"""
    return sqlite3.connect(DB_FILE)

# ---------------------------------------------------------
# 1. データベース初期化・テーブル作成処理
# ---------------------------------------------------------
def init_db():
    """アプリ起動時に必要な全テーブルを非破壊的に作成・初期化します"""
    conn = get_connection()
    c = conn.cursor()

    # ① グループごとのチャンネル関連付けテーブル (転送元: src / 転送先: dest)
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_channels (
            guild_id INTEGER,
            group_name TEXT,
            channel_id INTEGER,
            type TEXT,
            PRIMARY KEY (guild_id, group_name, channel_id, type)
        )
    ''')

    # ② グループごとの詳細設定テーブル (転送対象フィルタ・自動削除保持日数)
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_settings (
            guild_id INTEGER,
            group_name TEXT,
            target_content TEXT DEFAULT 'all',
            retention_days INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, group_name)
        )
    ''')

    # ③ リアクション自動昇格ルールテーブル (絵文字としきい値)
    c.execute('''
        CREATE TABLE IF NOT EXISTS promotion_rules (
            guild_id INTEGER,
            group_name TEXT,
            emoji TEXT,
            threshold INTEGER,
            PRIMARY KEY (guild_id, group_name, emoji)
        )
    ''')

    # ④ 転送済みメッセージ記録テーブル (二重転送の防止用)
    c.execute('''
        CREATE TABLE IF NOT EXISTS forwarded_messages (
            message_id INTEGER PRIMARY KEY,
            guild_id INTEGER,
            group_name TEXT,
            forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ⑤ 昇格済みメッセージ＆自動生成スレッド記録テーブル (二重昇格の防止用)
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

# ---------------------------------------------------------
# 2. グループ名一覧取得関数
# ---------------------------------------------------------
def get_all_group_names(guild_id: int) -> list[str]:
    """サーバー内に存在するすべての登録済みグループ名の一覧を重複なく取得します"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT DISTINCT group_name FROM (
            SELECT group_name FROM group_channels WHERE guild_id = ?
            UNION
            SELECT group_name FROM group_settings WHERE guild_id = ?
            UNION
            SELECT group_name FROM promotion_rules WHERE guild_id = ?
        ) ORDER BY group_name ASC
    ''', (guild_id, guild_id, guild_id))
    
    rows = c.fetchall()
    conn.close()
    
    return [row[0] for row in rows]

# ---------------------------------------------------------
# 3. メッセージ転送重複チェック＆記録関数
# ---------------------------------------------------------
def is_message_forwarded(message_id: int) -> bool:
    """指定されたメッセージが既に転送済みかどうかを判定します"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM forwarded_messages WHERE message_id = ?', (message_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def record_forwarded_message(message_id: int, guild_id: int, group_name: str):
    """転送完了したメッセージのIDをデータベースに記録します"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO forwarded_messages (message_id, guild_id, group_name)
        VALUES (?, ?, ?)
    ''', (message_id, guild_id, group_name))
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# 4. リアクション自動昇格重複チェック＆記録関数
# ---------------------------------------------------------
def is_message_promoted(original_message_id: int) -> bool:
    """指定された元メッセージが既に自動昇格済みかどうかを判定します"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM promoted_messages WHERE original_message_id = ?', (original_message_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def record_promoted_message(original_message_id: int, promoted_message_id: int, thread_id: int, guild_id: int, group_name: str):
    """自動昇格したメッセージおよび生成されたスレッドのIDをデータベースに記録します"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO promoted_messages (original_message_id, promoted_message_id, thread_id, guild_id, group_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (original_message_id, promoted_message_id, thread_id, guild_id, group_name))
    conn.commit()
    conn.close()
