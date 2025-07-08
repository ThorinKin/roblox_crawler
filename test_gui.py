import threading
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

# 自定义模块
import roblox_crawler

# 可选的间隔（分钟）和运行时长（小时）
INTERVAL_OPTIONS = [5, 10, 15, 20]
DURATION_OPTIONS = [1, 5, 10, 24]

# 创建主窗口
def main():
    root = tk.Tk()
    root.title("Roblox 赞助游戏爬虫控制面板")
    root.geometry("350x180")
    
    # 间隔时间下拉
    tk.Label(root, text="选择抓取间隔 (分钟)").pack(pady=(10, 0))
    interval_var = tk.StringVar(value=str(INTERVAL_OPTIONS[0]))
    interval_menu = ttk.Combobox(root, textvariable=interval_var, values=[str(i) for i in INTERVAL_OPTIONS], state="readonly")
    interval_menu.pack(pady=5)

    # 运行时长下拉
    tk.Label(root, text="选择运行时长 (小时)").pack(pady=(10, 0))
    duration_var = tk.StringVar(value=str(DURATION_OPTIONS[0]))
    duration_menu = ttk.Combobox(root, textvariable=duration_var, values=[str(h) for h in DURATION_OPTIONS], state="readonly")
    duration_menu.pack(pady=5)

    # 启动按钮回调
    def on_start():
        try:
            interval = int(interval_var.get())
            duration = int(duration_var.get())
        except ValueError:
            tk.messagebox.showerror("参数错误", "请选择有效的数字")
            return
        space_time = interval * 60
        # 计算循环次数：duration 小时 / interval 分钟
        cycles = duration * 60 // interval
        # 使用线程避免阻塞 GUI
        t = threading.Thread(target=roblox_crawler.workflow, args=(cycles, space_time), daemon=True)
        t.start()
        start_btn.config(state=tk.DISABLED)
        messagebox.showinfo("已启动", f"脚本将运行 {duration} 小时，间隔 {interval} 分钟。")

    start_btn = tk.Button(root, text="开始爬取", command=on_start)
    start_btn.pack(pady=15)

    root.mainloop()

if __name__ == '__main__':
    main()
