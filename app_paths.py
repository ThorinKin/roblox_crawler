# app_paths.py
from pathlib import Path
import sys

def app_dir() -> Path:
    """
    返回“项目运行目录”：
    - 未打包：当前 .py 文件所在目录
    - PyInstaller -F 打包后：exe 所在目录
    """
    if getattr(sys, 'frozen', False):      # 已冻结（打包）
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
