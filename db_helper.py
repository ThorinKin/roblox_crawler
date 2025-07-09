import os, sqlite3
from datetime import datetime
from typing import List, Dict, Any

_DB_NAME = "roblox_sponsored.db"

def _db_path() -> str:
    return os.path.join(os.path.dirname(__file__), _DB_NAME)

def upsert_records(records: List[Dict[str, Any]]) -> None:
    """
    C: 插入或更新

    插入或更新赞助游戏记录到数据库。
    """

    if not records:
        return
    rows = []
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    for rec in records:
        rows.append((
            rec.get("宇宙ID") or "", 
            rec.get("游戏名") or "",                
            rec.get("创建时间") or "",
            rec.get("游戏类型") or "",
            rec.get("活跃玩家数") or 0,
            rec.get("总访问")     or 0,
            rec.get("总喜欢数")   or 0,
            rec.get("好评率")     or "",
            rec.get("iconUrl")    or "",
            now
        ))

    sql = """
    INSERT INTO sponsored_games
    (universe_id, name, created_at, genre_l1, playing, visits,
     favorited, like_ratio, icon_url, saved_at)
    VALUES (?,?,?,?,?,?,?,?,?,?);
    """
    with sqlite3.connect(_db_path()) as conn:
        conn.executemany(sql, rows)
        conn.commit()

def fetch_latest(limit: int = 20):
    """
    R: 查询

    取得最新的20个赞助游戏记录。
    """
    sql = "SELECT * FROM sponsored_games ORDER BY saved_at DESC LIMIT ?"
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, (limit,))]

def delete_by_universe_id(uid: int):
    """
    D: 删除

    根据宇宙ID删除赞助游戏记录。
    """
    with sqlite3.connect(_db_path()) as conn:
        conn.execute("DELETE FROM sponsored_games WHERE universe_id = ?", (uid,))
        conn.commit()
