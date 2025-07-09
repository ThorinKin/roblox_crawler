# gui_app.pyw
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import queue
import io
from PIL import Image, ImageTk

# 自定义模块
import roblox_crawler
from session import register_cookie_prompt
from db_helper import query_records

# 可选的间隔（分钟）和运行时长（小时）
INTERVAL_OPTIONS = [5, 10, 30, 60]
DURATION_OPTIONS = [1, 5, 10, 24]

# 创建主窗口
def main():
    # ========== 基础窗口 ==========
    root = tk.Tk()
    root.title("Roblox 赞助游戏爬虫控制面板")
    root.geometry("1280x660")                 # 整体尺寸

    # 样式：行高 48px，容纳 48x48 图标
    style = ttk.Style(root)
    style.configure("Treeview", rowheight=48)

    # ---------- 顶部控制区 ----------
    ctrl_frame = tk.Frame(root)
    ctrl_frame.pack(fill=tk.X, pady=8)

    tk.Label(ctrl_frame, text="抓取间隔(分钟)").grid(row=0, column=0, padx=6)
    interval_var = tk.StringVar(value=str(INTERVAL_OPTIONS[0]))
    ttk.Combobox(
        ctrl_frame,
        textvariable=interval_var,
        values=[str(i) for i in INTERVAL_OPTIONS],
        state="readonly",
        width=6
    ).grid(row=0, column=1, padx=(0, 15))

    tk.Label(ctrl_frame, text="运行时长(小时)").grid(row=0, column=2, padx=6)
    duration_var = tk.StringVar(value=str(DURATION_OPTIONS[0]))
    ttk.Combobox(
        ctrl_frame,
        textvariable=duration_var,
        values=[str(h) for h in DURATION_OPTIONS],
        state="readonly",
        width=6
    ).grid(row=0, column=3, padx=(0, 15))

    def on_start():
        try:
            interval = int(interval_var.get())
            duration = int(duration_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "请选择有效数字")
            return
        space_time = interval * 60
        cycles = duration * 60 // interval
        # 禁用按钮直到任务完成
        start_btn.config(state=tk.DISABLED)
        messagebox.showinfo(
            "已启动",
            f"脚本将运行 {duration} 小时，间隔 {interval} 分钟。"
        )

        # 包装 workflow 以在结束后重新启用按钮
        def run_and_reset():
            try:
                roblox_crawler.workflow(cycles, space_time)
            finally:
                # 使用 after 切回主线程操作 UI
                root.after(0, lambda: start_btn.config(state=tk.NORMAL))

        threading.Thread(
            target=run_and_reset,
            daemon=True
        ).start()

        # 声明并放置开始按钮，绑定 on_start
    start_btn = tk.Button(
        ctrl_frame,
        text="开始爬取",
        width=10,
        command=on_start
    )
    start_btn.grid(row=0, column=4, padx=10)

    # ---------- 分隔线 ----------
    ttk.Separator(root, orient="horizontal").pack(fill=tk.X, pady=6)

    # ---------- 查询条件区 ----------
    cond_frame = tk.Frame(root)
    cond_frame.pack(fill=tk.X, padx=8, pady=4)

    tk.Label(cond_frame, text="游戏名包含").grid(row=0, column=0, padx=5, sticky="e")
    name_var = tk.StringVar()
    entry_name = tk.Entry(cond_frame, textvariable=name_var, width=18)
    entry_name.grid(row=0, column=1)

    tk.Label(cond_frame, text="保存时间 从").grid(row=0, column=2, padx=5, sticky="e")
    from_var = tk.StringVar()
    entry_from = tk.Entry(cond_frame, textvariable=from_var, width=14)
    entry_from.grid(row=0, column=3)

    tk.Label(cond_frame, text="到").grid(row=0, column=4, padx=5, sticky="e")
    to_var = tk.StringVar()
    entry_to = tk.Entry(cond_frame, textvariable=to_var, width=14)
    entry_to.grid(row=0, column=5)

    # 查询 / 清空按钮
    tk.Button(cond_frame, text="查询", width=8, command=lambda ev=None: do_query()).grid(row=0, column=6, padx=(12,4))
    tk.Button(
        cond_frame, text="清空", width=8,
        command=lambda: (
            name_var.set(""),
            from_var.set(""),
            to_var.set(""),
            do_query()
        )
    ).grid(row=0, column=7, padx=4)

    # 缓存图片，避免重复解码
    _icon_cache: dict[str, ImageTk.PhotoImage] = {}
    def fetch_blob_photo(blob: bytes, key: str) -> ImageTk.PhotoImage | None:
        if not blob:
            return None
        if key in _icon_cache:
            return _icon_cache[key]
        try:
            img = Image.open(io.BytesIO(blob)).resize((48,48), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            _icon_cache[key] = photo
            return photo
        except Exception:
            return None

    # ---------- 表格区 ----------
    table_frame = tk.Frame(root)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    cols = (
        "universe_id", "name", "created_at", "genre_l1",
        "saved_at", "playing", "visits", "favorited", "like_ratio"
    )
    tv = ttk.Treeview(
        table_frame,
        columns=cols,
        show="tree headings"
    )
    tv.column('#0', width=64, anchor='center')
    tv.heading('#0', text='Icon')

    HEADERS = {
      "universe_id": "游戏ID",
      "name":        "游戏名",
      "created_at":  "创建时间",
      "genre_l1":    "游戏类型",
      "saved_at":    "保存时间",
      "playing":     "活跃玩家",
      "visits":      "访问量",
      "favorited":   "收藏数",
      "like_ratio":  "好评率",
    }
    for key in cols:
        tv.heading(key, text=HEADERS[key])
        tv.column(key, width=(180 if key=='name' else 100), anchor='center')
    tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    # ---------- 查询 / 渲染逻辑 ----------
    def do_query(_=None):
        tv.delete(*tv.get_children())
        rows = query_records(
            name_like = name_var.get().strip() or None,
            date_from = from_var.get().strip() or None,
            date_to   = to_var.get().strip() or None,
            limit     = 20
        )
        for r in rows:
            key = str(r.get('universe_id'))
            blob = r.get('icon_blob')
            icon = fetch_blob_photo(blob, key)
            vals = tuple(r.get(c, '') for c in cols)
            item_id = tv.insert('', 'end', values=vals)
            if icon:
                tv.item(item_id, image=icon)

    # 绑定回车查询
    for entry in (entry_name, entry_from, entry_to):
        entry.bind('<Return>', do_query)

    # 初次显示最新 20 条
    do_query()

    # ---------- Cookie 失效弹窗回调 ----------
    def cookie_prompt_gui() -> str:
        q = queue.Queue()
        def ask():
            val = simpledialog.askstring(
                title="Cookie 失效",
                prompt="请输入新的 .ROBLOSECURITY：",
                parent=root,
                show="*"
            )
            q.put(val or "")
        root.after(0, ask)
        return q.get()
    register_cookie_prompt(cookie_prompt_gui)

    root.mainloop()

if __name__ == '__main__':
    main()
