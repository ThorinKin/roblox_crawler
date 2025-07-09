# session.py
import os
import json
import requests
import logging

# 自定义模块
from app_paths import app_dir

# 全局配置
SESSION_FILE = app_dir() / 'session.json' # pathlib.Path 类型重载运算符，用来拼接路径。
CSRF_URL = "https://auth.roblox.com/v2/login"
AUTH_USER_URL = "https://users.roblox.com/v1/users/authenticated"
# 全局保存回调
_cookie_prompt_cb = None          

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

def register_cookie_prompt(func):
    """GUI 程序在主线程里调用，把弹窗函数塞进来"""
    global _cookie_prompt_cb
    _cookie_prompt_cb = func

def refresh_cookie() -> str:
    """
    返回新的 .ROBLOSECURITY
    - 如果 GUI 回调已注册：调用之
    - 否则：退回 console input
    """
    if callable(_cookie_prompt_cb):
        try:
            return _cookie_prompt_cb().strip()
        except Exception as e:
            logging.warning("GUI 输入 Cookie 失败，将回退到 console：%s", e)

    # ---- console fallback ----
    return input("请输入新的 .ROBLOSECURITY 值: ").strip()

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
    # 读取会话数据，已弃用token
    sess_data = load_session()
    cookie = sess_data.get('cookie')

    # 使 cookie 生效或刷新
    if not cookie or not check_cookie_valid(cookie):
        logging.warning("检测到 Cookie 无效，需要输入新的 .ROBLOSECURITY")
        print("\n（警告）检测到 Cookie 无效，需要输入新的 .ROBLOSECURITY \n")
        # 触发重新输入 .ROBLOSECURITY
        cookie = refresh_cookie()
        sess_data['cookie'] = cookie

    save_session(sess_data)

    # 创建 requests.Session 对象
    s = requests.Session()
    s.headers.update({
        "Cookie": f".ROBLOSECURITY={cookie}",
    })
    return s

if __name__ == "__main__":
    session = ensure_session()