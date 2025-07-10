# db_helper.py
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
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
    name_like: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    limit:     Optional[int] = None,
    universe_id: Optional[int] = None,
    distinct:  bool = False
) -> List[Dict[str, Any]]:
    """
    根据条件查询记录。
    - name_like, date_from, date_to, universe_id 均可选
    - limit 为 None 时不限制条数
    - distinct=True 时按 universe_id 去重，只保留最新一条
    """
    # 构造基础 SQL 和参数（不含 LIMIT）
    sql_parts: List[str] = ["SELECT * FROM sponsored_games"]
    params: List[Any] = []
    where_clauses: List[str] = []

    if name_like:
        where_clauses.append("name LIKE ?")
        params.append(f"%{name_like}%")
    if date_from:
        where_clauses.append("saved_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("saved_at <= ?")
        params.append(date_to)
    if universe_id is not None:
        where_clauses.append("universe_id = ?")
        params.append(universe_id)

    if where_clauses:
        sql_parts.append("WHERE " + " AND ".join(where_clauses))

    # 最新优先
    sql_parts.append("ORDER BY saved_at DESC")

    # 如果不去重，直接加 LIMIT
    if not distinct and limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(limit)

    sql_query = " ".join(sql_parts)

    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        all_rows = [dict(r) for r in conn.execute(sql_query, params).fetchall()]

    # 如果不去重，直接返回
    if not distinct:
        return all_rows

    # 去重逻辑：按 universe_id 保留第一条（即最新的一条），再应用 limit
    seen = set()
    distinct_rows: List[Dict[str, Any]] = []
    for row in all_rows:
        uid = row.get("universe_id")
        if uid not in seen:
            seen.add(uid)
            distinct_rows.append(row)
            if limit is not None and len(distinct_rows) >= limit:
                break

    return distinct_rows