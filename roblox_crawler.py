# roblox_crawler.py
import requests
from typing import List, Dict, Union, Iterable, Optional
import uuid
import time
import os
import logging
import random
import json

# 自定义模块
import session 
import db_helper
from app_paths import app_dir

EXCEL_PATH = r'D:\热门数据.xlsx'
OMNI_RECO_URL = "https://apis.roblox.com/discovery-api/omni-recommendation"

def logging_init():
    """
    初始化日志记录配置。
    示例：
        logging.debug("调试信息")
        logging.info("普通信息")
        logging.warning("警告信息")
        logging.error("错误信息")
        logging.critical("严重错误")
    """
    # 找到脚本所在目录
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    script_dir = app_dir()

    # 定义日志文件路径
    log_path = os.path.join(script_dir, 'debug.log')

    # 配置 logging 
    logging.basicConfig(
        level=logging.DEBUG,               # 输出级别
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filename=log_path,                 # 日志文件
        filemode='a',                      # 追加模式
    )

def fetch_omni_recommendation(
    sess: requests.Session,
    *,
    page_type: str = "Home",
    supported_treatments: list[str] = ["SortlessGrid"],
    cpu_cores: int = 12,
    max_resolution: str = "2560x1440",
    max_memory: int = 8192,
    network_type: str = "4g",
    timeout: int = 10,
) -> list:
    """
    调用 /omni-recommendation，非官方api。更新于20250709 10:25

    参数
    ----
    sess                已准备好的 requests.Session 登录会话
    page_type           目前网页只用 Home
    supported_treatments 试验开关，如 ["SortlessGrid"]
    cpu_cores           本机cpu物理核数，可选
    max_resolution      本机分辨率 "2560x1440"
    max_memory          本机物理内存单位 MB
    network_type        "4g" / "wifi" / …

    返回
    ----
    前20个赞助游戏id列表。
    """
    # 已弃用token

    payload = {
        "pageType": page_type,
        "sessionId": str(uuid.uuid4()),
        "supportedTreatmentTypes": supported_treatments,
        "cpuCores": cpu_cores,
        "maxResolution": max_resolution,
        "maxMemory": max_memory,
        "networkType": network_type,
    }

    logging.info("请求 discovery-api/omni-recommendation 入参: %s",
                 json.dumps(payload, ensure_ascii=False))

    r = sess.post(
        OMNI_RECO_URL,
        json=payload,
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Referer":      "https://www.roblox.com/",
            "Origin":       "https://www.roblox.com",
            "User-Agent":   (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            )
        },
        timeout=10
    )
    r.raise_for_status()           # 4xx / 5xx → 抛异常
    data = r.json().get("sorts", [])
    # print(f"（测试）接口返回：{data}")
    result = []
    for sort in data:
        if (sort.get("topic") or "").lower() in {"赞助", "sponsored", "sponsoredgame"}:
            for item in sort.get("recommendationList", []):
                for key in ("contentId","placeId","universeId"):
                    if key in item: result.append(item[key]); break

    if not result:
        logging.critical(f"omni-recommendation接口未返回赞助游戏的推荐列表：{r.text[:500]}")
        raise ValueError(f"\n（错误）未找到赞助游戏的推荐列表：{r.text[:500]}\n")

    logging.info(f"获取赞助游戏，前20个id：{result[:20]}")
    return result[:20]  # 只取前20个

def get_game_icons(
    universe_ids: List[Union[int, str]],
    size: str   = "256x256",
    img_format: str = "webp",
    timeout: float  = 5.0
) -> Dict[int, str]:
    """
    批量获取 GameIcon 缩略图 URL。

    入参：
        universe_ids 指定需要查询的 universeId 列表（最多 20 个）。
        size 指定缩略图大小，一般是 '128x128' '256x256' '512x512' …
        img_format 指定图片格式，支持 'png' 或 'webp'。

    返回字典格式为 { universeId: imageUrl }
    
    """
    url = "https://thumbnails.roblox.com/v1/batch"
    
    # 构造请求体：每个元素都是一个 dict
    payload = []
    for uid in universe_ids:
        body ={
                "requestId": f"{uid}::GameIcon:{size}:{img_format}:regular:0",
                "type":      "GameIcon",
                "targetId":  int(uid),
                "format":    img_format,
                "size":      size,
                "token":     ""
            }
        payload.append(body)
    
    headers = {
        "User-Agent":      "Mozilla/5.0 (compatible; IconBot/1.0)",
        "Accept":          "application/json",
        "Content-Type":    "application/json"
    }
    
    logging.info(f"接口调用，icon图片查询....")
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    # 返回值
    results = resp.json().get("data", [])
    
    # 组装 {universeId: imageUrl}
    icon_map: Dict[str, str] = {}
    for item in results:
        uid = str(item.get("targetId"))
        url  = item.get("imageUrl")
        if uid and url:
            icon_map[uid] = url
  
    logging.info(f"获取 {len(icon_map)} 个游戏图标，大小：{size}，格式：{img_format}")
    return icon_map

def get_game_info(
    universe_ids: Union[int, str, List[Union[int, str]]],
    timeout: float = 5.0
) -> dict:
    """
    获取一个或多个 universe 的详细信息。
    入参：
        universe_ids: id 列表

    返回详细信息。
    """
    # 构造 comma-separated 字符串
    if isinstance(universe_ids, (list, tuple)):
        universe_ids_str = ",".join(str(uid) for uid in universe_ids)
    else:
        universe_ids_str = str(universe_ids)

    url = "https://games.roblox.com/v1/games"
    params = {"universeIds": universe_ids_str}
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)",
        "Accept": "application/json"
    }

    logging.info(f"接口调用，获取游戏信息，universeIds: {universe_ids_str}")
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    logging.info(f"获取游戏信息成功，返回 {len(resp.json().get('data', []))} 条记录")
    return resp.json().get("data", [])
 
def get_vote_stats(
    universe_ids: Iterable[int],
    *,
    use_roproxy: bool = True,
    timeout: int = 10,
) -> List[Optional[float]]:
    """
    https://games.roblox.com/v1/games/votes
    风险提示：此接口可能会被限流，返回 403 Forbidden。

    批量获取 Roblox 游戏的 upVotes / downVotes 并计算好评率。

    入参：
        universe_ids : 需要查询的 Universe ID 列表。
        chunk_size : 最大批量查询数。
        use_roproxy : 默认 ture 不带 .ROBLOSECURITY 和 Cookie
    返回：
        好评率列表，目前20个。

    """
    ids = [int(uid) for uid in universe_ids]
    if not ids:
        return []

    base = "https://games.roproxy.com" if use_roproxy else "https://games.roblox.com"
    headers = {"User-Agent": "VoteFetcher/0.4", "Accept": "application/json"}

    ratios: List[Optional[float]] = []
    for uid in ids:
        try:
            url = f"{base}/v1/games/{uid}/votes"
            logging.info(f"接口调用，获取此游戏的好评率：{uid}")
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 403:
                # 公共代理偶尔被限流——返回 None 占位
                ratios.append(None)
                continue

            resp.raise_for_status()
            data = resp.json()

            up, down = data.get("upVotes", 0), data.get("downVotes", 0)
            total = up + down

            if total:
                percent = up * 100 / total
                ratios.append(f"{percent:.2f}%")
            else:
                ratios.append(None)

        except Exception:
            ratios.append(None)

        # 随机延迟，友好对待公共代理
        time.sleep(random.uniform(0.8, 2))
    logging.info(f"获取好评率列表：{ratios}")
    return ratios

def workflow(cycles: int = 288, space_time: int = 300):
    """
    主工作流函数，获取热门趋势内容并查询游戏信息。

    入参默认间隔5分钟，持续24小时（288次）。
    """
    # 初始化日志功能
    logging_init()

    for i in range(cycles):
        print(f"\n（调试）开始第 {i+1} 次拉取数据...\n")
        logging.info(f"开始第 {i+1} 次拉取数据...")

        # 真正的主流程：
        try:
            # 初始化登录会话
            sess = session.ensure_session()
            time.sleep(random.uniform(1, 3))

            # 赞助 API 查询，返回前 20 个赞助游戏商的 universeId 列表
            top_ids = fetch_omni_recommendation(sess)
            time.sleep(random.uniform(1, 3))

            # 获取每个 universe 对应的图标 URL，返回 { str(id): url }
            top_id_and_icon = get_game_icons(top_ids)
            time.sleep(random.uniform(1, 3))

            # 获取每个 universe 的详细信息，返回一个字典列表
            multiple = get_game_info(top_ids)
            time.sleep(random.uniform(1, 3))

            # 获取每个 universe 的好评率，返回一个列表
            praise_rates = get_vote_stats(top_ids)

            # —— 组装存档的数据 ——
            # 1. 把 multiple 列表变成以 int(universeId) 为 key 的映射
            game_info_map = {
                int(g.get("universeId") or g.get("id")): g
                for g in multiple
            }

            # 2. 遍历前 20 个 id，按索引取 praise_rates，再从 icon_map、game_info_map 拿对应字段
            data_to_save = []
            for idx, uid in enumerate(top_ids):
                info = game_info_map.get(uid, {})
                data_to_save.append({
                    "宇宙ID":           uid,
                    "游戏名":           info.get("name"),
                    "创建时间":         info.get("created"),
                    "游戏类型":         info.get("genre_l1"),
                    "活跃玩家数":       info.get("playing"),
                    "总访问":           info.get("visits"),
                    "总喜欢数":         info.get("favoritedCount"),
                    "好评率":           praise_rates[idx],
                    "iconUrl":          top_id_and_icon.get(str(uid)),
                })

            # 现在 data_to_save 就是一个长度为 limit（默认 20）的列表，
            # 每个元素都是一个包含上述字段的 dict，可直接写入数据库或导出 CSV/JSON
            print(f"\n（调试）数据组装完成，准备存库....\n")
            logging.info("数据组装完成，准备存库....")
            
            # 存库
            db_helper.upsert_records(data_to_save)
            print(f"\n（调试）已将 {len(data_to_save)} 条记录存入数据库。\n")
            logging.info(f"已将 {len(data_to_save)} 条记录存入数据库。")

        except requests.RequestException as e:
            print(f"\n（错误）网络请求错误：{e}\n")
            logging.error(f"网络请求错误：{e}")
        except ValueError as e:
            print(f"\n（错误）值错误：{e}\n")
            logging.error(f"值错误：{e}")
        except Exception as e:
            print (f"\n（错误）其他错误：{e}\n")
            logging.error(f"其他错误：{e}")
        finally:
            print(f"\n（调试）第 {i+1} 次拉取数据结束...\n")
            logging.info(f"第 {i+1} 次拉取数据结束...")
            if i < cycles - 1:
                time.sleep(space_time)

if __name__ == "__main__":
    workflow()
    # 测试：