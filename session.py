import os
import json
import requests
import logging

# 全局配置
SESSION_FILE = os.path.join(os.path.dirname(__file__), 'session.json')
# CSRF_URL = "https://auth.roblox.com/v2/logout"
CSRF_URL = "https://auth.roblox.com/v2/login"
# CHECK_COOKIE_URL = "https://apis.roblox.com/discovery-api/omni-recommendation"
AUTH_USER_URL = "https://users.roblox.com/v1/users/authenticated"

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
    script_dir = os.path.dirname(os.path.abspath(__file__))

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

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            logging.info("加载现有会话数据")
            return json.load(f)
    logging.info("未找到会话文件，创建新的会话数据")
    return {}

def save_session(data):
    with open(SESSION_FILE, 'w') as f:
        json.dump(data, f, indent=2)
        logging.info("成功保存登录会话数据到文件")

def refresh_cookie():
    # 提示用户输入新的 .ROBLOSECURITY 值
    new_cookie = input("请输入新的 .ROBLOSECURITY 值: ").strip()
    return new_cookie

def get_csrf_token(cookie: str, cached_token: str | None = None) -> str:
    """
    先验证本地缓存的 x-csrf-token 是否可用，若失效则自动刷新。

    返回可用的 x-csrf-token
    """
    common_headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "SessionManager/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    def probe(token: str | None) -> tuple[int, str | None]:
        """带（或不带）token 发一次 probe，返回 (status_code, new_token_header)"""
        headers = common_headers.copy()
        if token:
            headers["x-csrf-token"] = token
        try:
            logging.info("接口调用，尝试获取/验证 x-csrf-token...")
            r = requests.post(CSRF_URL, headers=headers, timeout=10, json={})
            return r.status_code, r.headers.get("x-csrf-token")
        except requests.RequestException as e:
            logging.error("获取/验证 x-csrf-token 失败: %s", e)
            raise RuntimeError("网络错误，无法验证 x-csrf-token") from e

    # 有缓存情况下：验证缓存的 token 是否有效
    if cached_token:
        status, maybe_new = probe(cached_token)
        if status != 403:
            logging.info("沿用缓存的 x-csrf-token")
            return cached_token
        if maybe_new:
            logging.info("检测到缓存 token 失效，已获取服务器下发新 token")
            return maybe_new

    # 无缓存情况下，或 header 为空：不带 token 请求token
    status, maybe_new = probe(None)
    if maybe_new:
        logging.info("无缓存，成功刷新到新的 x-csrf-token")
        return maybe_new

    logging.error("未能获得新的 x-csrf-token，Cookie 可能无效")
    raise RuntimeError("无法获取 x-csrf-token；请检查 .ROBLOSECURITY")

def check_cookie_valid(cookie: str) -> bool:
    """使用官方替换端点验证 .ROBLOSECURITY 是否仍有效"""
    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "SessionManager/1.0",
        "Accept": "application/json"
    }
    try:
        # 只要 200 就视为有效；401/403 均视为失效
        logging.info("接口调用，尝试验证Cookie有效性...")
        r = requests.get(AUTH_USER_URL, headers=headers, timeout=10)
        logging.info("验证 Cookie 状态码: %s", r.status_code)
        return r.status_code == 200
    except requests.RequestException as e:
        logging.error("检查 Cookie 失败: %s", e)
        return False

def ensure_session():
    """
    核心模块

    检测并确保会话有效，返回一个带有会话的 requests.Session 对象。
    """
    # 读取会话数据
    sess_data = load_session()
    cookie = sess_data.get('cookie')
    # csrf = sess_data.get('csrf_token')

    # 使 cookie 生效或刷新
    if not cookie or not check_cookie_valid(cookie):
        logging.warning("检测到 Cookie 无效，需要输入新的 .ROBLOSECURITY")
        print("\n（警告）检测到 Cookie 无效，需要输入新的 .ROBLOSECURITY \n")
        # 触发重新输入 .ROBLOSECURITY
        cookie = refresh_cookie()
        sess_data['cookie'] = cookie

    # 使 CSRF token 生效或刷新
    """  
    try:
        csrf = get_csrf_token(cookie, cached_token=csrf)
        sess_data["csrf_token"] = csrf
    except RuntimeError as e:    
        print("（错误）刷新 x-csrf-token 失败：", e)
        logging.error(f"刷新 x-csrf-token 失败:{e}")
        print("需要二次确认 .ROBLOSECURITY 是否正确，再试一次....")
        logging.info("需要二次确认 .ROBLOSECURITY 是否正确，再试一次....")
        cookie = refresh_cookie()
        sess_data['cookie'] = cookie
        csrf = get_csrf_token(cookie)
        sess_data['csrf_token'] = csrf
    """

    save_session(sess_data)

    # 创建 requests.Session 对象
    s = requests.Session()
    s.headers.update({
        "Cookie": f".ROBLOSECURITY={cookie}",
    })
    return s

if __name__ == "__main__":
    session = ensure_session()
    # data = fetch_omni_recommendation(session)
    # print(json.dumps(data, indent=2))
