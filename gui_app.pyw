# gui_app.pyw
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import queue
import io
from PIL import Image, ImageTk

# 配置 matplotlib 支持中文
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['axes.unicode_minus'] = False  
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from datetime import datetime

# 自定义模块
import roblox_crawler
from session import register_cookie_prompt
from db_helper import query_records, analyze_playing_growth

# 可选的间隔（分钟）和运行时长（小时）
INTERVAL_OPTIONS = [5, 10, 30, 60]
DURATION_OPTIONS = [1, 5, 10, 24]

# 全局停止事件
stop_event = threading.Event()

def main():
    """创建爬虫控制面板 GUI"""

    root = tk.Tk()
    root.title("Roblox 赞助游戏爬虫控制面板")
    root.geometry("1280x660")
    style = ttk.Style(root)
    style.configure("Treeview", rowheight=48)

    # ---------- 顶部控制区 ----------
    ctrl_frame = tk.Frame(root)
    ctrl_frame.pack(fill=tk.X, pady=8)

    tk.Label(ctrl_frame, text="抓取间隔(分钟)").grid(row=0, column=0, padx=6)
    interval_var = tk.StringVar(value=str(INTERVAL_OPTIONS[0]))
    ttk.Combobox(ctrl_frame, textvariable=interval_var,
                 values=[str(i) for i in INTERVAL_OPTIONS], state="readonly", width=6)\
        .grid(row=0, column=1, padx=(0,15))

    tk.Label(ctrl_frame, text="运行时长(小时)").grid(row=0, column=2, padx=6)
    duration_var = tk.StringVar(value=str(DURATION_OPTIONS[0]))
    ttk.Combobox(ctrl_frame, textvariable=duration_var,
                 values=[str(h) for h in DURATION_OPTIONS], state="readonly", width=6)\
        .grid(row=0, column=3, padx=(0,15))

    def on_start():
        try:
            interval = int(interval_var.get()); duration = int(duration_var.get())
        except ValueError:
            messagebox.showerror("参数错误","请选择有效数字"); return
        space_time = interval*60; cycles = duration*60//interval
        start_btn.config(state=tk.DISABLED); custom_btn.config(state=tk.DISABLED); stop_btn.config(state=tk.NORMAL)
        stop_event.clear()
        messagebox.showinfo("已启动",f"脚本将运行 {duration} 小时，间隔 {interval} 分钟。")
        def run_loop():
            try:
                for _ in range(cycles):
                    if stop_event.is_set(): break
                    roblox_crawler.workflow(cycles, space_time)
            finally:
                root.after(0, lambda: (
                    start_btn.config(state=tk.NORMAL),
                    custom_btn.config(state=tk.NORMAL),
                    stop_btn.config(state=tk.DISABLED)
                ))
        threading.Thread(target=run_loop, daemon=True).start()

    start_btn = tk.Button(ctrl_frame, text="网页提取", width=10, command=on_start)
    start_btn.grid(row=0, column=4, padx=10)

    tk.Label(ctrl_frame, text="自定义ID列表(≤20，逗号分隔)").grid(row=0, column=5, padx=6)
    ids_var = tk.StringVar()
    ids_entry = tk.Entry(ctrl_frame, textvariable=ids_var, width=28)
    ids_entry.grid(row=0, column=6, padx=(0,10))

    def on_custom():
        raw = ids_var.get().strip()
        if not raw:
            messagebox.showerror("参数错误","请输入至少一个 Universe ID"); return
        try:
            ids = [int(s) for s in raw.replace("；",",").split(",") if s.strip()]
        except:
            messagebox.showerror("参数错误","ID 列表中只能包含整数和逗号"); return
        if len(ids) > 20:
            messagebox.showerror("参数错误","ID 数量不能超过 20 个"); return
        try:
            interval = int(interval_var.get()); duration = int(duration_var.get())
        except:
            messagebox.showerror("参数错误","请选择有效数字"); return
        space_time = interval*60; cycles = duration*60//interval
        start_btn.config(state=tk.DISABLED); custom_btn.config(state=tk.DISABLED); stop_btn.config(state=tk.NORMAL)
        stop_event.clear()
        messagebox.showinfo("已启动",f"自定义提取已启动：{len(ids)} 个 ID\n运行 {duration} 小时，间隔 {interval} 分钟。")
        def run_loop():
            try:
                for _ in range(cycles):
                    if stop_event.is_set(): break
                    roblox_crawler.workflow_2(ids, cycles, space_time)
            finally:
                root.after(0, lambda: (
                    start_btn.config(state=tk.NORMAL),
                    custom_btn.config(state=tk.NORMAL),
                    stop_btn.config(state=tk.DISABLED)
                ))
        threading.Thread(target=run_loop, daemon=True).start()

    custom_btn = tk.Button(ctrl_frame, text="自定义提取", width=10, command=on_custom)
    custom_btn.grid(row=0, column=7)

    def on_stop():
        stop_event.set()
        messagebox.showinfo("已停止","当前周期结束后停止。")
    stop_btn = tk.Button(ctrl_frame, text="停止脚本", width=10, command=on_stop, state=tk.DISABLED)
    stop_btn.grid(row=0, column=8, padx=10)


    # ---------- 查询条件区 ----------
    cond_frame = tk.Frame(root)
    cond_frame.pack(fill=tk.X, padx=8, pady=4)

    # --- 第一行：名称 & 时间范围 ---
    tk.Label(cond_frame, text="游戏名包含").grid(row=0, column=0, padx=5, sticky="e")
    name_var = tk.StringVar()
    entry_name = tk.Entry(cond_frame, textvariable=name_var, width=18)
    entry_name.grid(row=0, column=1)

    tk.Label(cond_frame, text="创建时间 从").grid(row=0, column=2, padx=5, sticky="e")
    created_from_var = tk.StringVar()
    entry_created_from = tk.Entry(cond_frame, textvariable=created_from_var, width=20)
    entry_created_from.grid(row=0, column=3)
    tk.Label(cond_frame, text="到").grid(row=0, column=4, padx=5, sticky="e")
    created_to_var = tk.StringVar()
    entry_created_to = tk.Entry(cond_frame, textvariable=created_to_var, width=14)
    entry_created_to.grid(row=0, column=5)

    tk.Label(cond_frame, text="保存时间 从").grid(row=0, column=6, padx=5, sticky="e")
    from_var = tk.StringVar()
    entry_from = tk.Entry(cond_frame, textvariable=from_var, width=14)
    entry_from.grid(row=0, column=7)
    tk.Label(cond_frame, text="到").grid(row=0, column=8, padx=5, sticky="e")
    to_var = tk.StringVar()
    entry_to = tk.Entry(cond_frame, textvariable=to_var, width=14)
    entry_to.grid(row=0, column=9)

    # --- 第二行：数值筛选 & 操作按钮 ---
    tk.Label(cond_frame, text="活跃玩家 ≥").grid(row=1, column=0, padx=(0,1), sticky="e")
    playing_min_var = tk.StringVar(value="0")
    entry_playing_min = tk.Entry(cond_frame, textvariable=playing_min_var, width=15)
    entry_playing_min.grid(row=1, column=1, padx=(0,2))
    tk.Label(cond_frame, text="≤").grid(row=1, column=2, padx=(0,2))
    playing_max_var = tk.StringVar(value="")
    entry_playing_max = tk.Entry(cond_frame, textvariable=playing_max_var, width=15)
    entry_playing_max.grid(row=1, column=3, padx=(0,2))

    tk.Label(cond_frame, text="访问量 ≥").grid(row=1, column=4, padx=(0,1), sticky="e")
    visits_min_var = tk.StringVar(value="0")
    entry_visits_min = tk.Entry(cond_frame, textvariable=visits_min_var, width=15)
    entry_visits_min.grid(row=1, column=5, padx=(0,2))
    tk.Label(cond_frame, text="≤").grid(row=1, column=6, padx=(0,2))
    visits_max_var = tk.StringVar(value="")
    entry_visits_max = tk.Entry(cond_frame, textvariable=visits_max_var, width=15)
    entry_visits_max.grid(row=1, column=7, padx=(0,2))

    tk.Label(cond_frame, text="显示数量").grid(row=1, column=8, padx=(5,2), sticky="e")
    limit_var = tk.StringVar(value="20")
    limit_entry = tk.Entry(cond_frame, textvariable=limit_var, width=6)
    limit_entry.grid(row=1, column=9, padx=1)

    distinct_var = tk.BooleanVar(value=True)
    distinct_cb = tk.Checkbutton(cond_frame, text="去重", variable=distinct_var)
    distinct_cb.grid(row=1, column=10, padx=1)

    tk.Label(cond_frame, text="在线涨幅(%)").grid(row=1, column=11, padx=(1,2), sticky="e")
    percent_var = tk.StringVar(value="10")
    percent_entry = tk.Entry(cond_frame, textvariable=percent_var, width=6)
    percent_entry.grid(row=1, column=12, padx=1)

    def on_query():
        try:
            limit = int(limit_var.get())
            playing_min = int(playing_min_var.get())
            visits_min = int(visits_min_var.get())
            if limit <= 0 or playing_min < 0 or visits_min < 0:
                raise ValueError
            # 最大值可选
            pmax = playing_max_var.get().strip()
            vmax = visits_max_var.get().strip()
            playing_max = int(pmax) if pmax else None
            visits_max = int(vmax) if vmax else None
            if (playing_max is not None and playing_max < playing_min) or (visits_max is not None and visits_max < visits_min):
                raise ValueError
        except ValueError:
            messagebox.showerror("参数错误", "显示数量、活跃玩家/访问量必须为非负整数，且最大值不小于最小值")
            return
        tv.delete(*tv.get_children())
        rows = query_records(
            name_like=name_var.get().strip() or None,
            created_from=created_from_var.get().strip() or None,
            created_to=created_to_var.get().strip() or None,
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None,
            playing_min=playing_min,
            playing_max=playing_max,
            visits_min=visits_min,
            visits_max=visits_max,
            limit=limit,
            distinct=distinct_var.get()
        )
        for r in rows:
            key = str(r.get("universe_id"))
            blob = r.get("icon_blob")
            icon = fetch_blob_photo(blob, key)
            vals = tuple(r.get(c, "") for c in cols)
            item_id = tv.insert("", "end", values=vals)
            if icon:
                tv.item(item_id, image=icon)

    def on_growth_query():
        try:
            limit = int(limit_var.get())
            playing_min = int(playing_min_var.get())
            visits_min = int(visits_min_var.get())
            percent = float(percent_var.get())
            if limit <= 0 or playing_min < 0 or visits_min < 0:
                raise ValueError
            pmax = playing_max_var.get().strip()
            vmax = visits_max_var.get().strip()
            playing_max = int(pmax) if pmax else None
            visits_max = int(vmax) if vmax else None
            if (playing_max is not None and playing_max < playing_min) or (visits_max is not None and visits_max < visits_min):
                raise ValueError
        except ValueError:
            messagebox.showerror("参数错误", "请输入正确的筛选值（非负整数、数字，且最大值不小于最小值）")
            return
        tv.delete(*tv.get_children())
        rows = analyze_playing_growth(
            percent_threshold=percent,
            name_like=name_var.get().strip() or None,
            created_from=created_from_var.get().strip() or None,
            created_to=created_to_var.get().strip() or None,
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None,
            playing_min=playing_min,
            playing_max=playing_max,
            visits_min=visits_min,
            visits_max=visits_max,
            distinct=distinct_var.get(),
            limit=limit
        )
        for r in rows:
            key = str(r.get("universe_id"))
            blob = r.get("icon_blob")
            icon = fetch_blob_photo(blob, key)
            vals = tuple(r.get(c, "") for c in cols)
            item_id = tv.insert("", "end", values=vals)
            if icon:
                tv.item(item_id, image=icon)

    tk.Button(cond_frame, text="普通查询", width=8, command=on_query)\
        .grid(row=1, column=13, padx=(12,4))
    tk.Button(cond_frame, text="增量查询", width=8, command=on_growth_query)\
        .grid(row=1, column=14, padx=(0,4))
    tk.Button(cond_frame, text="清空", width=8, command=lambda: (
        name_var.set(""),
        created_from_var.set(""),
        created_to_var.set(""),
        from_var.set(""),
        to_var.set(""),
        playing_min_var.set("0"),
        playing_max_var.set(""),
        visits_min_var.set("0"),
        visits_max_var.set(""),
        limit_var.set("20"),
        distinct_var.set(False),
        percent_var.set("10"),
        on_query()
    )).grid(row=1, column=15)

    # ---------- 缓存图片 ----------
    _icon_cache: dict[str, ImageTk.PhotoImage] = {}
    def fetch_blob_photo(blob: bytes, key: str) -> ImageTk.PhotoImage | None:
        if not blob:
            return None
        if key in _icon_cache:
            return _icon_cache[key]
        try:
            img = Image.open(io.BytesIO(blob)).resize((48, 48), Image.LANCZOS)
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
    tv = ttk.Treeview(table_frame, columns=cols, show="tree headings")
    tv.column("#0", width=64, anchor="center")
    tv.heading("#0", text="Icon")

    HEADERS = {
        "universe_id": "游戏ID", "name": "游戏名", "created_at": "创建时间",
        "genre_l1": "游戏类型", "saved_at": "保存时间", "playing": "活跃玩家",
        "visits": "访问量", "favorited": "收藏数", "like_ratio": "好评率"
    }
    for key in cols:
        tv.heading(key, text=HEADERS[key])
        tv.column(key, width=(180 if key == "name" else 100), anchor="center")
    tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    # ---- 数据可视化函数 ----
    def show_chart(universe_id: int, game_name: str = ""):
        rows = query_records(universe_id=universe_id)
        if not rows:
            messagebox.showinfo("无数据", f"宇宙 ID {universe_id} 没有历史记录")
            return
        data = sorted(rows, key=lambda r: r['saved_at'])
        times = [datetime.fromisoformat(r['saved_at']) for r in data]
        playing = [r['playing'] for r in data]
        visits = [r['visits'] for r in data]
        favorited = [r['favorited'] for r in data]

        win = tk.Toplevel(root)
        win.title(f"{game_name or universe_id} 图表")
        win.geometry("900x800")

        # 创建 3x1 子图
        fig, axes = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
        axes[0].plot(times, playing, marker='.')
        axes[0].set_ylabel("活跃玩家")
        axes[1].plot(times, visits, marker='.')
        axes[1].set_ylabel("访问量")
        axes[2].plot(times, favorited, marker='.')
        axes[2].set_ylabel("收藏数")
        axes[2].set_xlabel("保存时间")
        for ax in axes:
            # x轴主刻度定位：自动选择合适的时间间隔
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            # x轴主刻度格式：固定“月-日 小时:分”
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
            # x轴文本旋转得更平缓些
            for label in ax.get_xticklabels():
                label.set_rotation(30)
                label.set_ha('right')
        fig.autofmt_xdate()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # 绑定双击和右键菜单显示图表
    def on_double(event):
        item = tv.focus()
        if not item:
            return
        vals = tv.item(item, "values")
        uid = int(vals[cols.index("universe_id")])
        name = vals[cols.index("name")]
        show_chart(uid, name)

    tv.bind("<Double-1>", on_double)
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="显示图表", command=lambda: on_double(None))
    def on_right_click(event):
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
            menu.post(event.x_root, event.y_root)
    tv.bind("<Button-3>", on_right_click)

    # 绑定回车查询
    for widget in (entry_name, entry_created_from, entry_created_to,
                   entry_from, entry_to, entry_playing_min,
                   entry_visits_min, limit_entry, percent_entry,
                   entry_playing_max, entry_visits_max):
        widget.bind("<Return>", lambda e: on_query())

    # 初次显示
    on_query()

    # ---------- Cookie 失效弹窗回调 ----------
    def cookie_prompt_gui() -> str:
        q = queue.Queue()
        def ask():
            val = simpledialog.askstring(
                title="Cookie 失效", prompt="请输入新的 .ROBLOSECURITY：", parent=root, show="*"
            )
            q.put(val or "")
        root.after(0, ask)
        return q.get()

    register_cookie_prompt(cookie_prompt_gui)

    root.mainloop()


if __name__ == "__main__":
    main()
