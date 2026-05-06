# gui/theme.py
# 统一样式主题配置 - 浅色暖金风格

import tkinter as tk
from tkinter import ttk

# ============================================================
# 字体配置 - 清晰可读
# ============================================================
class Fonts:
    """统一字体方案"""
    # Windows 原生字体
    UI = ("Segoe UI", 10)           # 界面正文
    UI_SMALL = ("Segoe UI", 9)      # 次要文字
    UI_LARGE = ("Segoe UI", 12)     # 标题
    UI_BOLD = ("Segoe UI", 10, "bold")

    # 等宽字体（数字对齐）
    MONO = ("Consolas", 10)         # 数字列
    MONO_BOLD = ("Consolas", 10, "bold")

    # 中文友好字体（正文/按钮）
    CN = ("Microsoft YaHei", 10)
    CN_SMALL = ("Microsoft YaHei", 9)
    CN_BOLD = ("Microsoft YaHei", 10, "bold")
    CN_TITLE = ("Microsoft YaHei", 13, "bold")
    CN_LARGE = ("Microsoft YaHei", 12, "bold")

    # Treeview 专用
    TREE = ("Consolas", 10)
    TREE_HEAD = ("Segoe UI", 10, "bold")


# ============================================================
# 颜色系统 - 浅色暖金主题
# ============================================================
class Colors:
    """浅色暖金配色"""

    # 主色调 - 暖金色系
    PRIMARY = "#D4A843"
    PRIMARY_DARK = "#B8922E"
    PRIMARY_LIGHT = "#E8C36B"
    PRIMARY_BG = "#FDF6E3"

    # 背景色
    BG_DARK = "#F5F3EF"
    BG_CARD = "#FFFFFF"
    BG_NAV = "#EAE6DF"
    BG_INPUT = "#FAFAFA"

    # 边框
    BORDER = "#E0DCD4"
    BORDER_LIGHT = "#F0EDE8"

    # 强调色 - 红涨绿跌（符合中国股市习惯）
    ACCENT_RED = "#DC3545"
    ACCENT_GREEN = "#28A745"
    ACCENT_ORANGE = "#FD7E14"
    ACCENT_BLUE = "#0D6EFD"

    # 文字色
    TEXT_PRIMARY = "#2C2C2C"
    TEXT_SECONDARY = "#7A7A7A"
    TEXT_LIGHT = "#FFFFFF"
    TEXT_MUTED = "#A0A0A0"


# ============================================================
# 样式配置
# ============================================================
class Theme:
    """统一样式配置"""

    @staticmethod
    def configure_light(style):
        """浅色暖金主题"""
        s = style
        s.theme_use("clam")

        bg = Colors.BG_DARK
        card_bg = Colors.BG_CARD
        nav_bg = Colors.BG_NAV

        # 全局
        s.configure(".", background=bg, foreground=Colors.TEXT_PRIMARY,
                   font=Fonts.UI)
        s.configure("TFrame", background=bg)
        s.configure("Card.TFrame", background=card_bg)

        # LabelFrame
        s.configure("TLabelframe", background=bg, bordercolor=Colors.BORDER, relief="flat")
        s.configure("TLabelframe.Label", background=bg,
                   foreground=Colors.PRIMARY_DARK, font=Fonts.CN_BOLD)

        # 标签
        s.configure("TLabel", background=bg, foreground=Colors.TEXT_PRIMARY, font=Fonts.UI)
        s.configure("Secondary.TLabel", foreground=Colors.TEXT_SECONDARY, font=Fonts.UI_SMALL)

        # 按钮
        s.configure("TButton", background=card_bg, foreground=Colors.TEXT_PRIMARY,
                   bordercolor=Colors.BORDER, padding=(12, 6),
                   relief="flat", font=Fonts.CN)

        s.configure("Primary.TButton", background=Colors.PRIMARY,
                   foreground=Colors.TEXT_LIGHT, bordercolor=Colors.PRIMARY_DARK,
                   padding=(12, 6), relief="flat", font=Fonts.CN_BOLD)

        s.configure("Success.TButton", background=Colors.ACCENT_GREEN,
                   foreground=Colors.TEXT_LIGHT, bordercolor=Colors.ACCENT_GREEN,
                   padding=(12, 6), relief="flat")

        s.configure("Danger.TButton", background=Colors.ACCENT_RED,
                   foreground=Colors.TEXT_LIGHT, bordercolor=Colors.ACCENT_RED,
                   padding=(12, 6), relief="flat")

        # 按钮 hover
        s.map("TButton", background=[("active", Colors.BG_NAV), ("pressed", Colors.BORDER)],
              foreground=[("active", Colors.PRIMARY_DARK)])
        s.map("Primary.TButton", background=[("active", Colors.PRIMARY_DARK), ("pressed", "#9A7A26")])
        s.map("Success.TButton", background=[("active", "#218838"), ("pressed", "#1e7e34")])
        s.map("Danger.TButton", background=[("active", "#C82333"), ("pressed", "#BD2D35")])

        # 输入框
        s.configure("TEntry", fieldbackground=card_bg, foreground=Colors.TEXT_PRIMARY,
                   bordercolor=Colors.BORDER, lightcolor=card_bg,
                   darkcolor=card_bg, relief="flat", font=Fonts.UI)
        s.configure("TCombobox", fieldbackground=card_bg, foreground=Colors.TEXT_PRIMARY,
                   bordercolor=Colors.BORDER, arrowcolor=Colors.TEXT_SECONDARY,
                   lightcolor=card_bg, darkcolor=card_bg, relief="flat")

        # Notebook
        s.configure("TNotebook", background=bg, bordercolor=Colors.BORDER, relief="flat")
        s.configure("TNotebook.Tab", background=Colors.BG_NAV,
                   foreground=Colors.TEXT_SECONDARY,
                   padding=[15, 8], font=Fonts.CN,
                   relief="flat")
        s.map("TNotebook.Tab",
              background=[("selected", Colors.BG_CARD), ("active", Colors.BORDER)],
              foreground=[("selected", Colors.PRIMARY_DARK)])

        # Treeview - 关键：增大字号
        s.configure("Treeview", background=card_bg, foreground=Colors.TEXT_PRIMARY,
                   fieldbackground=card_bg, bordercolor=Colors.BORDER,
                   rowheight=30, relief="flat", font=Fonts.TREE)
        s.configure("Treeview.Heading", background=Colors.BG_NAV,
                   foreground=Colors.TEXT_PRIMARY, bordercolor=Colors.BORDER,
                   font=Fonts.TREE_HEAD, relief="flat", anchor="center")
        s.map("Treeview",
              background=[("selected", Colors.PRIMARY_BG)],
              foreground=[("selected", Colors.PRIMARY_DARK)])

        # Panedwindow
        s.configure("TPanedwindow", background=bg)

        # Scrollbar
        s.configure("TScrollbar", background=Colors.BG_CARD,
                   troughcolor=Colors.BG_DARK,
                   bordercolor=Colors.BORDER, arrowcolor=Colors.TEXT_SECONDARY,
                   relief="flat")

        s.configure("Status.TFrame", background=Colors.BG_NAV)

    @staticmethod
    def configure_dark(style):
        """深色主题（备用）"""
        s = style
        s.theme_use("clam")
        bg = "#1E1E2E"
        s.configure(".", background=bg, foreground=Colors.TEXT_LIGHT, font=Fonts.UI)
        s.configure("TFrame", background=bg)
        s.configure("TLabelframe", background=bg, bordercolor="#3A3A4E")
        s.configure("TLabelframe.Label", background=bg, foreground=Colors.PRIMARY_LIGHT)
        s.configure("TLabel", background=bg, foreground=Colors.TEXT_LIGHT)
        s.configure("Secondary.TLabel", foreground="#9090A0")
        s.configure("TButton", background="#2A2A3E", foreground=Colors.TEXT_LIGHT,
                   bordercolor="#3A3A4E", padding=(12, 6))
        s.configure("Primary.TButton", background=Colors.PRIMARY,
                   foreground="white", bordercolor=Colors.PRIMARY, padding=(12, 6))
        s.map("TButton", background=[("active", "#3A3A4E")])
        s.map("Primary.TButton", background=[("active", Colors.PRIMARY_DARK)])
        s.configure("TEntry", fieldbackground="#2A2A3E", foreground=Colors.TEXT_LIGHT,
                   bordercolor="#3A3A4E")
        s.configure("TCombobox", fieldbackground="#2A2A3E", foreground=Colors.TEXT_LIGHT,
                   bordercolor="#3A3A4E", arrowcolor=Colors.TEXT_LIGHT)
        s.configure("TNotebook", background=bg, bordercolor="#3A3A4E")
        s.configure("TNotebook.Tab", background="#2A2A3E", foreground="#9090A0", padding=[15, 8])
        s.map("TNotebook.Tab", background=[("selected", Colors.PRIMARY), ("active", "#3A3A4E")],
              foreground=[("selected", "white")])
        s.configure("Treeview", background="#1E1E2E", foreground=Colors.TEXT_LIGHT,
                   fieldbackground="#1E1E2E", bordercolor="#3A3A4E", rowheight=30)
        s.configure("Treeview.Heading", background="#2A2A3E", foreground=Colors.TEXT_LIGHT,
                   bordercolor="#3A3A4E", font=Fonts.TREE_HEAD)
        s.map("Treeview", background=[("selected", Colors.PRIMARY)])
        s.configure("TScrollbar", background="#2A2A3E", troughcolor=bg,
                   bordercolor="#2A2A3E", arrowcolor="#9090A0")


# ============================================================
# 工具函数
# ============================================================
def set_treeview_style(tree, profit_color=None, loss_color=None):
    """设置Treeview颜色"""
    profit_c = profit_color or Colors.ACCENT_RED
    loss_c = loss_color or Colors.ACCENT_GREEN
    tree.tag_configure("profit", foreground=profit_c)
    tree.tag_configure("loss", foreground=loss_c)
    tree.tag_configure("hold", foreground=Colors.TEXT_SECONDARY)
    tree.tag_configure("header", background=Colors.BG_NAV, foreground=Colors.TEXT_PRIMARY)
