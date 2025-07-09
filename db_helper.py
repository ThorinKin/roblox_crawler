# db_helper.py
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import requests
# 自定义模块
from app_paths import app_dir

# 全局配置
_DB_NAME = "roblox_sponsored.db"

def _db_path() -> str:
    return str(app_dir() / _DB_NAME)

def upsert_records(records: List[Dict[str, Any]]) -> None:
    """
    C: 插入或更新

    插入或更新赞助游戏记录到数据库。
    把 icon_url 对应的图片下载下来存成 BLOB。
    """
    if not records:
        return

    rows: List[tuple] = []
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    for rec in records:
        universe_id = rec.get("宇宙ID") or ""
        name        = rec.get("游戏名") or ""
        created_at  = rec.get("创建时间") or ""
        genre_l1    = rec.get("游戏类型") or ""
        playing     = rec.get("活跃玩家数") or 0
        visits      = rec.get("总访问") or 0
        favorited   = rec.get("总喜欢数") or 0
        like_ratio  = rec.get("好评率") or ""
        icon_url    = rec.get("iconUrl") or ""

        # 拉取图标二进制
        icon_blob: bytes | None = None
        if icon_url:
            try:
                resp = requests.get(icon_url, timeout=6)
                resp.raise_for_status()
                icon_blob = resp.content
            except Exception as e:
                # 下载失败时保留 None，也不会抛，后续可用默认图或者留空
                print(f"警告：拉取图标失败 {icon_url} → {e}")
        rows.append((
            universe_id,
            name,
            created_at,
            genre_l1,
            playing,
            visits,
            favorited,
            like_ratio,
            icon_url,
            icon_blob,
            now
        ))

    sql = """
    INSERT INTO sponsored_games
      (universe_id, name, created_at, genre_l1, playing, visits,
       favorited, like_ratio, icon_url, icon_blob, saved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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

def query_records(
    name_like: str | None = None,
    date_from: str | None = None,   # 'YYYY-MM-DD' 或更精细到秒
    date_to:   str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    根据 name、saved_at 模糊查询记录。
    参数均可留空
    """
    sql = ["SELECT * FROM sponsored_games"]
    params: list[Any] = []

    # 动态拼 where
    where: list[str] = []
    if name_like:
        where.append("name LIKE ?")
        params.append(f"%{name_like}%")

    if date_from:
        where.append("saved_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("saved_at <= ?")
        params.append(date_to)

    if where:
        sql.append("WHERE " + " AND ".join(where))

    sql.append("ORDER BY saved_at DESC LIMIT ?")
    params.append(limit)

    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(" ".join(sql), params)
        return [dict(r) for r in cur.fetchall()]
