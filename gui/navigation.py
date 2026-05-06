# gui/navigation.py
# 左侧导航面板 - 浅色暖金风格

import tkinter as tk
from tkinter import ttk
from .theme import Colors


class NavigationPanel(ttk.Frame):
    """浅色暖金风格左侧导航"""

    def __init__(self, parent, click_callback, theme="light"):
        self.click_callback = click_callback
        self.theme = theme
        self.nav_items = {}
        self.active_item = None

        super().__init__(parent)
        self.configure(width=220)
        self.pack(side=tk.LEFT, fill=tk.Y)
        self.pack_propagate(False)

        self.setup_ui()

    def setup_ui(self):
        # 顶部Logo区域
        self.header_frame = tk.Frame(self, bg=Colors.PRIMARY, height=90)
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(self.header_frame, bg=Colors.PRIMARY)
        logo_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        logo_icon = tk.Label(logo_frame, text="📈", bg=Colors.PRIMARY, fg="white",
                            font=("Arial", 24))
        logo_icon.pack()

        logo_title = tk.Label(logo_frame, text="LW Stock", bg=Colors.PRIMARY, fg="white",
                             font=("Microsoft YaHei", 14, "bold"))
        logo_title.pack()

        logo_sub = tk.Label(logo_frame, text="智能股票管理系统", bg=Colors.PRIMARY_DARK,
                           fg="#E8D89B", font=("Microsoft YaHei", 8))
        logo_sub.pack()

        # 导航菜单
        self.nav_frame = tk.Frame(self, bg=Colors.BG_NAV)
        self.nav_frame.pack(fill=tk.Y, expand=True, pady=(8, 0))

        # 菜单配置
        menu_items = [
            ('watchlist', '📋', '全部股票', '自选股管理'),
            ('filter', '🔍', '智能筛选', '发现投资机会'),
            ('strategy', '⚙️', '策略方案', '条件组合管理'),
            ('financial', '💰', '财务数据', '深度基本面'),
            ('positions', '📈', '持仓管理', '资产动态跟踪'),
            ('reports', '📊', '报告中心', 'AI分析复盘'),
        ]

        for item_id, icon, title, desc in menu_items:
            self._create_nav_item(item_id, icon, title, desc)

        # 底部设置入口
        sep = tk.Frame(self.nav_frame, bg=Colors.BORDER, height=1)
        sep.pack(fill=tk.X, padx=15, pady=(10, 8))

        self._create_nav_item('settings', '🔧', '系统设置', '个性化配置', is_bottom=True)

        # 状态面板
        self.status_frame = tk.Frame(self, bg=Colors.BG_CARD, height=100)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_frame.pack_propagate(False)

        self._setup_status_panel()

    def _create_nav_item(self, item_id, icon, title, desc, is_bottom=False):
        """创建单个导航项"""
        btn_frame = tk.Frame(self.nav_frame, bg=Colors.BG_NAV, padx=8, pady=2)
        btn_frame.pack(fill=tk.X, pady=(0, 3))

        btn = tk.Frame(btn_frame, bg=Colors.BG_CARD, padx=10, pady=8,
                      relief=tk.FLAT, bd=0)
        btn.pack(fill=tk.X)
        btn.configure(highlightthickness=0, highlightbackground=Colors.BORDER)

        # 左侧图标
        icon_label = tk.Label(btn, text=icon, bg=Colors.BG_CARD, fg=Colors.PRIMARY,
                             font=("Arial", 14), width=3, anchor=tk.W)
        icon_label.pack(side=tk.LEFT)

        # 右侧文字
        text_frame = tk.Frame(btn, bg=Colors.BG_CARD)
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title_label = tk.Label(text_frame, text=title, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                              font=("Microsoft YaHei", 11, "bold"), anchor=tk.W)
        title_label.pack(anchor=tk.W)

        desc_label = tk.Label(text_frame, text=desc, bg=Colors.BG_CARD, fg=Colors.TEXT_MUTED,
                              font=("Microsoft YaHei", 8), anchor=tk.W)
        desc_label.pack(anchor=tk.W)

        # 存储引用
        self.nav_items[item_id] = {
            'frame': btn,
            'icon': icon_label,
            'title': title_label,
            'desc': desc_label,
            'default_bg': Colors.BG_CARD,
            'default_fg': Colors.TEXT_PRIMARY
        }

        # 绑定事件
        for widget in [btn, btn.winfo_children()[0], btn.winfo_children()[1]]:
            widget.bind("<Button-1>", lambda e, i=item_id: self._on_nav_click(i))
            widget.bind("<Enter>", lambda e, i=item_id: self._on_nav_hover(i, True))
            widget.bind("<Leave>", lambda e, i=item_id: self._on_nav_hover(i, False))

    def _on_nav_click(self, item_id):
        """导航项点击"""
        if self.click_callback:
            self.click_callback(item_id)
        self._set_active(item_id)

    def _on_nav_hover(self, item_id, is_hover):
        """导航项悬停效果"""
        if self.active_item == item_id:
            return
        item = self.nav_items.get(item_id)
        if item:
            if is_hover:
                item['frame'].configure(bg=Colors.PRIMARY_BG)
                for child in item['frame'].winfo_children():
                    child.configure(bg=Colors.PRIMARY_BG)
            else:
                item['frame'].configure(bg=item['default_bg'])
                for child in item['frame'].winfo_children():
                    child.configure(bg=item['default_bg'])

    def _set_active(self, item_id):
        """设置当前激活项"""
        # 恢复上一个
        if self.active_item and self.active_item in self.nav_items:
            item = self.nav_items[self.active_item]
            item['frame'].configure(bg=item['default_bg'])
            for child in item['frame'].winfo_children():
                child.configure(bg=item['default_bg'])
            item['title'].configure(fg=Colors.TEXT_PRIMARY)
            item['icon'].configure(fg=Colors.PRIMARY)

        # 设置新的激活项
        if item_id and item_id in self.nav_items:
            item = self.nav_items[item_id]
            item['frame'].configure(bg=Colors.PRIMARY)
            for child in item['frame'].winfo_children():
                child.configure(bg=Colors.PRIMARY)
            item['title'].configure(fg="white")
            item['icon'].configure(fg="white")
            self.active_item = item_id

    def _setup_status_panel(self):
        """设置状态面板"""
        status_inner = tk.Frame(self.status_frame, bg=Colors.BG_CARD)
        status_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # 标题
        title = tk.Label(status_inner, text="📊 系统状态", bg=Colors.BG_CARD,
                        fg=Colors.PRIMARY_DARK, font=("Microsoft YaHei", 9, "bold"))
        title.pack(anchor=tk.W, pady=(0, 6))

        # 状态项
        self.status_labels = {}
        status_items = [
            ('行情日期', 'loading...'),
            ('股票总数', '--'),
        ]

        for key, value in status_items:
            row = tk.Frame(status_inner, bg=Colors.BG_CARD)
            row.pack(fill=tk.X, pady=2)

            key_label = tk.Label(row, text=key, bg=Colors.BG_CARD, fg=Colors.TEXT_MUTED,
                                font=("Microsoft YaHei", 8))
            key_label.pack(side=tk.LEFT)

            val_label = tk.Label(row, text=value, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                                font=("Microsoft YaHei", 8, "bold"))
            val_label.pack(side=tk.RIGHT)

            self.status_labels[key] = val_label

    def update_status(self, key, value):
        """更新状态显示"""
        if key in self.status_labels:
            self.status_labels[key].config(text=value)

    def set_active(self, item_id):
        """程序化设置激活项"""
        self._set_active(item_id)
