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
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    playing_min: Optional[int] = None,
    playing_max: Optional[int] = None,
    visits_min: Optional[int] = None,
    visits_max: Optional[int] = None,
    limit:     Optional[int] = None,
    universe_id: Optional[int] = None,
    distinct:  bool = False
) -> List[Dict[str, Any]]:
    """
    根据条件查询记录。
    - 支持 name_like, date_from/ date_to(saved_at), created_from/created_to(created_at),
      playing_min/playing_max, visits_min/visits_max, universe_id
    - limit=None 不限制条数
    - distinct=True 时按 universe_id 去重，只保留最新一条
    """
    # 构造基础 SQL 和参数（不含 LIMIT）
    sql_parts: List[str] = ["SELECT * FROM sponsored_games"]
    params: List[Any] = []
    where_clauses: List[str] = []


    if name_like:
        where_clauses.append("name LIKE ?")
        params.append(f"%{name_like}%")
    if universe_id is not None:
        where_clauses.append("universe_id = ?")
        params.append(universe_id)
    if date_from:
        where_clauses.append("saved_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("saved_at <= ?")
        params.append(date_to)
    if created_from:
        where_clauses.append("created_at >= ?")
        params.append(created_from)
    if created_to:
        where_clauses.append("created_at <= ?")
        params.append(created_to)
    if playing_min is not None:
        where_clauses.append("playing >= ?")
        params.append(playing_min)
    if playing_max is not None:
        where_clauses.append("playing <= ?")
        params.append(playing_max)
    if visits_min is not None:
        where_clauses.append("visits >= ?")
        params.append(visits_min)
    if visits_max is not None:
        where_clauses.append("visits <= ?")
        params.append(visits_max)

    if where_clauses:
        sql_parts.append("WHERE " + " AND ".join(where_clauses))

    # 最新优先
    sql_parts.append("ORDER BY saved_at DESC")

    # 如果不去重，直接加 LIMIT
    if not distinct and limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(limit)

    sql = " ".join(sql_parts)
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    if not distinct:
        return rows

    seen = set()
    distinct_rows: List[Dict[str, Any]] = []
    for row in rows:
        uid = row.get("universe_id")
        if uid not in seen:
            seen.add(uid)
            distinct_rows.append(row)
            if limit is not None and len(distinct_rows) >= limit:
                break
    return distinct_rows

def analyze_playing_growth(
    percent_threshold: float,
    name_like: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    playing_min: Optional[int] = None,
    playing_max: Optional[int] = None,
    visits_min: Optional[int] = None,
    visits_max: Optional[int] = None,
    universe_id: Optional[int] = None,
    distinct: bool = False,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    分析在指定时间范围内在线人数增长超过给定百分比的记录，并支持更多筛选条件。
    参数:
      percent_threshold: 增长百分比阈值，如10表示10%
      name_like, date_from/date_to(saved_at),
      created_from/created_to(created_at), playing_min/playing_max, visits_min/visits_max,
      universe_id, distinct, limit
    返回: 包含原表字段及growth_percent字段的记录列表
    """
    sql_parts = ["SELECT * FROM sponsored_games"]
    where_clauses: List[str] = []
    params: List[Any] = []

    if name_like:
        where_clauses.append("name LIKE ?")
        params.append(f"%{name_like}%")
    if universe_id is not None:
        where_clauses.append("universe_id = ?")
        params.append(universe_id)
    if date_from:
        where_clauses.append("saved_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("saved_at <= ?")
        params.append(date_to)
    if created_from:
        where_clauses.append("created_at >= ?")
        params.append(created_from)
    if created_to:
        where_clauses.append("created_at <= ?")
        params.append(created_to)
    if playing_min is not None:
        where_clauses.append("playing >= ?")
        params.append(playing_min)
    if playing_max is not None:
        where_clauses.append("playing <= ?")
        params.append(playing_max)
    if visits_min is not None:
        where_clauses.append("visits >= ?")
        params.append(visits_min)
    if visits_max is not None:
        where_clauses.append("visits <= ?")
        params.append(visits_max)

    if where_clauses:
        sql_parts.append("WHERE " + " AND ".join(where_clauses))
    sql_parts.append("ORDER BY universe_id, saved_at")

    sql = " ".join(sql_parts)
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    prev_playing: Dict[Any, int] = {}
    growth_events: List[Dict[str, Any]] = []
    for row in rows:
        uid = row.get("universe_id")
        playing = row.get("playing", 0)
        prev = prev_playing.get(uid)
        if prev and prev > 0:
            growth = (playing - prev) / prev * 100
            if growth >= percent_threshold:
                ev = row.copy()
                ev['growth_percent'] = growth
                growth_events.append(ev)
        prev_playing[uid] = playing

    if distinct:
        seen = set()
        result: List[Dict[str, Any]] = []
        for ev in sorted(growth_events, key=lambda x: x['saved_at'], reverse=True):
            uid = ev.get('universe_id')
            if uid not in seen:
                seen.add(uid)
                result.append(ev)
                if limit and len(result) >= limit:
                    break
        return result

    result = sorted(growth_events, key=lambda x: x['saved_at'], reverse=True)
    if limit:
        result = result[:limit]
    return result

if __name__ == "__main__": 
    pass
    # 测试：
    test = analyze_playing_growth(1, "Build An Island!", distinct = True)
    print(f"测试：{test}")