# 左侧导航面板

import tkinter as tk
from tkinter import ttk

class NavigationPanel(ttk.Frame):
    """左侧导航树"""
    
    def __init__(self, parent, click_callback):
        """
        Args:
            parent: 父容器
            click_callback: 点击回调函数，参数为 item_id
        """
        super().__init__(parent)
        self.click_callback = click_callback
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置 UI"""
        # 顶部 Logo/标题区
        header_frame = ttk.Frame(self, padding=(0, 20, 0, 30))
        header_frame.pack(fill=tk.X)
        
        title = ttk.Label(header_frame, text="聪明小爪", font=('Microsoft YaHei', 16, 'bold'), foreground="#007aff")
        title.pack()
        ttk.Label(header_frame, text="股票筛选系统", font=('Microsoft YaHei', 9), foreground="gray").pack()
        
        # 导航菜单项
        items = [
            ('filter', '🔍 扫描筛选'),
            ('watchlist', '📋 全部股票'),
            ('strategy', '⚙️ 策略方案'),
            ('reports', '📊 复盘报告'),
            ('positions', '📈 持仓看板'),
            ('settings', '🔧 系统设置')
        ]
        
        self.btns = {}
        for item_id, text in items:
            btn = ttk.Button(self, text=text, command=lambda i=item_id: self.on_click(i), padding=10)
            btn.pack(fill=tk.X, padx=15, pady=4)
            self.btns[item_id] = btn
        
        # 底部状态区域
        status_container = ttk.Frame(self)
        status_container.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        status_frame = ttk.LabelFrame(status_container, text="系统状态", padding=15)
        status_frame.pack(fill=tk.X, padx=15)
        
        self.status_labels = {}
        status_items = [
            ('财务日期', '未加载'),
            ('行情日期', '未加载'),
            ('股票总数', '0')
        ]
        
        for key, value in status_items:
            row = ttk.Frame(status_frame)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=key, font=('Microsoft YaHei', 9), foreground="gray").pack(side=tk.LEFT)
            lbl = ttk.Label(row, text=value, font=('Microsoft YaHei', 9, 'bold'))
            lbl.pack(side=tk.RIGHT)
            self.status_labels[key] = lbl
    
    def on_click(self, item_id):
        """按钮点击"""
        if self.click_callback:
            self.click_callback(item_id)
    
    def update_status(self, key, value):
        """更新状态显示"""
        if key in self.status_labels:
            self.status_labels[key].config(text=value)
