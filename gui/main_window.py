# GUI 主窗口

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import os
import sys

# 确保路径正确
sys.path.insert(0, os.path.dirname(__file__))

from .navigation import NavigationPanel
from .theme import Theme, Colors


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LW Stock 智能股票管理系统")
        self.root.geometry("1500x900")
        self.root.minsize(1200, 700)

        # 配置全局字体
        self.default_font = ('Microsoft YaHei', 10)
        self.header_font = ('Microsoft YaHei', 12, 'bold')
        self.root.option_add("*Font", self.default_font)

        # 设置样式（浅色暖金主题）
        self.setup_style()

        # 配置
        self.config_file = Path('config/gui_state.json')
        self.config = self.load_config()

        # 窗口位置和大小
        if self.config.get('geometry'):
            self.root.geometry(self.config['geometry'])

        # 布局
        self.setup_menu()
        self.setup_layout()
        self.setup_statusbar()

        # 绑定事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 加载 Tab 页面
        self.load_tabs()

        # 初始化系统状态显示
        self.refresh_system_status()

    def refresh_system_status(self):
        """刷新左侧导航栏的系统状态（行情、财务、股票总数）"""
        try:
            from core.financial_data import FinancialDataManager
            from core.daily_data import DailyDataManager
            from core.stock_manager import StockManager

            fdm = FinancialDataManager()
            ddm = DailyDataManager()
            sm = StockManager()

            fin_period = fdm.get_latest_period() or "无数据"
            trade_date = ddm.get_overall_latest_date() or "无数据"
            
            # 统计股票数量
            import sqlite3
            with sqlite3.connect(sm.db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM stocks_basic").fetchone()[0]

            self.navigation.update_status('行情日期', trade_date)
            self.navigation.update_status('股票总数', f"{count:,}")
            
            self.set_status(f"系统就绪 | 数据同步完成")
        except Exception as e:
            print(f"刷新系统状态失败: {e}")
            self.set_status("系统就绪（部分数据未加载）")

    def setup_style(self):
        """配置 TTK 样式 - 浅色暖金主题"""
        style = ttk.Style()
        # 使用浅色暖金主题
        Theme.configure_light(style)

    def load_config(self):
        """加载 GUI 配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_config(self):
        """保存 GUI 配置"""
        self.config['geometry'] = self.root.geometry()
        if hasattr(self, 'notebook'):
            self.config['current_tab'] = self.notebook.index(self.notebook.select())
        
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def setup_menu(self):
        """菜单栏"""
        menubar = tk.Menu(self.root)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="退出", command=self.on_closing)
        menubar.add_cascade(label="文件", menu=file_menu)
        
        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="更新数据", command=self.on_update_data)
        tools_menu.add_separator()
        from gui.utils import generate_stock_report
        tools_menu.add_command(label="📊 生成个股深度报告", command=lambda: generate_stock_report(self.root, None))
        tools_menu.add_separator()
        tools_menu.add_command(label="导入自选股", command=self.on_import_watchlist)
        tools_menu.add_command(label="导出自选股", command=self.on_export_watchlist)
        menubar.add_cascade(label="工具", menu=tools_menu)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用帮助", command=self.on_help)
        help_menu.add_command(label="关于", command=self.on_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def setup_layout(self):
        """主布局"""
        # 主容器
        main_container = tk.Frame(self.root, bg=Colors.BG_DARK)
        main_container.pack(fill=tk.BOTH, expand=True)

        # 左侧导航（固定宽度 220）
        self.nav_frame = tk.Frame(main_container, bg=Colors.BG_NAV, width=220)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.nav_frame.pack_propagate(False)

        self.navigation = NavigationPanel(self.nav_frame, self.on_nav_clicked)

        # 右侧内容区
        content_frame = tk.Frame(main_container, bg=Colors.BG_DARK)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 内容容器
        content_bg = tk.Frame(content_frame, bg=Colors.BG_DARK)
        content_bg.pack(fill=tk.BOTH, expand=True)

        # Notebook（标签页）
        self.notebook = ttk.Notebook(content_bg)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 绑定切换事件
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)

        # 标签页容器
        self.tabs = {}
    
    def load_tabs(self):
        """动态加载所有 Tab 页面"""
        # 先清空 notebook
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        
        try:
            # 导入所有 Tab
            from gui.tabs.financial_tab import FinancialTab
            from gui.tabs.watchlist_tab import AllStocksTab
            from gui.tabs.strategy_tab import StrategyTab
            from gui.tabs.filter_tab import FilterTab
            from gui.tabs.positions_tab import PositionsTab
            from gui.tabs.reports_tab import ReportsTab
            from gui.tabs.settings_tab import SettingsTab
            
            # Tab定义：ID, 显示名称, 图标
            tab_defs = [
                ('watchlist', '📋 全部股票', AllStocksTab),
                ('filter', '🔍 智能筛选', FilterTab),
                ('strategy', '⚙️ 策略方案', StrategyTab),
                ('financial', '💰 财务数据', FinancialTab),
                ('positions', '📈 持仓管理', PositionsTab),
                ('reports', '📊 报告中心', ReportsTab),
                ('settings', '🔧 系统设置', SettingsTab)
            ]
            
            for tab_id, tab_name, tab_class in tab_defs:
                frame = tk.Frame(self.notebook, bg=Colors.BG_DARK)

                if tab_class:
                    try:
                        tab_instance = tab_class(frame)
                        self.tabs[tab_id] = tab_instance
                    except Exception as e:
                        print(f"加载 Tab '{tab_name}' 失败: {e}")
                        import traceback
                        traceback.print_exc()
                        # 显示错误
                        err_label = tk.Label(frame, text=f"{tab_name}\n加载失败\n{str(e)[:80]}",
                                           fg=Colors.ACCENT_RED, bg=Colors.BG_DARK,
                                           font=("Microsoft YaHei", 12), anchor=tk.CENTER)
                        err_label.pack(expand=True)
                else:
                    tk.Label(frame, text=f"{tab_name} - 开发中...",
                            bg=Colors.BG_DARK, fg=Colors.TEXT_SECONDARY,
                            font=("Microsoft YaHei", 14)).pack(expand=True)
                    self.tabs[tab_id] = None

                self.notebook.add(frame, text=tab_name)

            # 恢复上次选中的标签页
            if self.config.get('current_tab', 0) < self.notebook.index('end'):
                self.notebook.select(self.config.get('current_tab', 0))
            elif self.notebook.index('end') > 0:
                self.notebook.select(0)

        except Exception as e:
            print(f"加载 Tabs 时发生严重错误: {e}")
            import traceback
            traceback.print_exc()
            frame = tk.Frame(self.notebook, bg=Colors.BG_DARK)
            tk.Label(frame, text=f"加载失败:\n{e}", fg=Colors.ACCENT_RED, bg=Colors.BG_DARK).pack(expand=True)
            self.notebook.add(frame, text="错误")
    
    def setup_statusbar(self):
        """状态栏 - 浅色暖金主题"""
        self.statusbar = tk.Frame(self.root, bg=Colors.BG_CARD, height=28)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.statusbar.pack_propagate(False)

        status_inner = tk.Frame(self.statusbar, bg=Colors.BG_CARD)
        status_inner.pack(fill=tk.BOTH, expand=True, padx=15)

        # 左侧状态
        self.status_label = tk.Label(status_inner, text="✓ 系统就绪",
                                    bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                                    font=("Microsoft YaHei", 9))
        self.status_label.pack(side=tk.LEFT, anchor=tk.W)

        # 右侧版本信息
        version_frame = tk.Frame(status_inner, bg=Colors.BG_CARD)
        version_frame.pack(side=tk.RIGHT)

        tk.Label(version_frame, text="LW Stock System",
                bg=Colors.BG_CARD, fg=Colors.TEXT_MUTED,
                font=("Microsoft YaHei", 8)).pack(side=tk.RIGHT)

        version_badge = tk.Label(version_frame, text="v2.0",
                               bg=Colors.PRIMARY, fg="white",
                               font=("Microsoft YaHei", 8, "bold"),
                               padx=6, pady=1)
        version_badge.pack(side=tk.RIGHT, padx=(10, 0))
    
    def set_status(self, message):
        """更新状态栏"""
        self.status_label.config(text=f"🚀 {message}")
        self.root.update()
    
    # === 事件处理 ===
    
    def on_nav_clicked(self, item_id):
        """导航点击事件"""
        # 动态映射
        tab_ids = list(self.tabs.keys())
        if item_id in self.tabs:
            index = tab_ids.index(item_id)
            self.notebook.select(index)
            # 更新导航激活状态
            self.navigation.set_active(item_id)
        else:
            print(f"警告: 找不到 tab '{item_id}'")
    
    def on_tab_changed(self, event):
        """标签页切换"""
        current = self.notebook.select()
        tab_text = self.notebook.tab(current, 'text')
        self.set_status(f"当前页面: {tab_text}")
        
        # 同步导航激活状态
        current_index = self.notebook.index(current)
        tab_ids = list(self.tabs.keys())
        if current_index < len(tab_ids):
            self.navigation.set_active(tab_ids[current_index])
    
    def on_update_data(self):
        """菜单：更新数据"""
        from core.config import config
        token = config.get_tushare_token()
        if not token:
            messagebox.showwarning("提示", "未找到 TUSHARE_TOKEN，请先设置")
            return
            
        def update_thread():
            self.set_status("🔄 正在更新基础股票列表...")
            from core.stock_manager import StockManager
            from core.financial_data import FinancialDataManager
            from core.daily_data import DailyDataManager
            from core.positions import PositionManager

            try:
                sm = StockManager()
                sm.update_stocks_list(token)

                self.set_status("🔄 正在更新行情数据 (持仓股票)...")
                ddm = DailyDataManager()
                pm = PositionManager()
                df_pos = pm.get_all()
                if not df_pos.empty:
                    codes = df_pos['ts_code'].unique().tolist()
                    ddm.sync_daily_data(token, codes)

                self.set_status("🔄 正在更新财务数据...")
                fdm = FinancialDataManager()
                count = fdm.update_latest(token)
                self.set_status(f"✅ 更新完成！新增 {count} 条财务记录")
                messagebox.showinfo("成功", f"数据更新完成！\n新增财务记录: {count}")
            except Exception as e:
                self.set_status(f"❌ 更新失败: {e}")
                messagebox.showerror("错误", f"更新过程中发生错误:\n{e}")
        
        import threading
        threading.Thread(target=update_thread, daemon=True).start()
    
    def on_import_watchlist(self):
        """菜单：导入自选股"""
        if 'watchlist' in self.tabs and hasattr(self.tabs['watchlist'], 'on_import_clicked'):
            self.tabs['watchlist'].on_import_clicked()
    
    def on_export_watchlist(self):
        """菜单：导出自选股"""
        if 'watchlist' in self.tabs and hasattr(self.tabs['watchlist'], 'on_export_clicked'):
            self.tabs['watchlist'].on_export_clicked()
    
    def on_help(self):
        """菜单：帮助"""
        help_win = tk.Toplevel(self.root)
        help_win.title("📖 使用帮助")
        help_win.geometry("600x500")
        help_win.configure(bg=Colors.BG_DARK)
        
        text = tk.Text(help_win, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                      font=("Microsoft YaHei", 10), wrap=tk.WORD, padx=20, pady=20)
        text.pack(fill=tk.BOTH, expand=True)
        
        help_content = """
📖 LW Stock 智能股票管理系统 使用指南

【快速开始】
1. 在「🔧 系统设置」中填入 Tushare Token
2. 在「📋 全部股票」页面更新全市场行情
3. 在「💰 财务数据」页面同步财务指标
4. 使用「🔍 智能筛选」发现投资机会
5. 在「📈 持仓管理」跟踪你的投资

【核心功能】
• 📋 全部股票 - 全市场5000+股票管理，支持自选标记
• 🔍 智能筛选 - 多维度财务+技术指标筛选
• ⚙️ 策略方案 - 保存和加载筛选条件组合
• 💰 财务数据 - 深度基本面分析
• 📈 持仓管理 - 资产动态跟踪，支持动态止盈止损
• 📊 报告中心 - AI智能分析报告

【快捷键】
• 右键菜单 - 查看更多操作选项
• 双击持仓 - 快速卖出
• 标签页点击 - 切换功能模块
        """
        text.insert("1.0", help_content)
        text.config(state=tk.DISABLED)
    
    def on_about(self):
        """菜单：关于"""
        about_win = tk.Toplevel(self.root)
        about_win.title("关于")
        about_win.geometry("400x350")
        about_win.configure(bg=Colors.BG_DARK)
        about_win.transient(self.root)
        about_win.grab_set()
        
        # Logo
        logo_frame = tk.Frame(about_win, bg=Colors.BG_DARK, height=100)
        logo_frame.pack(fill=tk.X, pady=30)
        
        logo_icon = tk.Label(logo_frame, text="📈", bg=Colors.BG_DARK,
                           font=("Arial", 48), fg=Colors.PRIMARY_LIGHT)
        logo_icon.pack()
        
        tk.Label(logo_frame, text="LW Stock", bg=Colors.BG_DARK,
                fg=Colors.TEXT_PRIMARY, font=("Microsoft YaHei", 20, "bold")).pack()
        
        tk.Label(logo_frame, text="智能股票管理系统", bg=Colors.BG_DARK,
                fg=Colors.TEXT_SECONDARY, font=("Microsoft YaHei", 10)).pack()
        
        # 版本信息
        version_frame = tk.Frame(about_win, bg=Colors.BG_CARD, padx=30, pady=20)
        version_frame.pack(fill=tk.X, padx=40)
        
        info = [
            ("版本", "v2.0.0"),
            ("主题", "深色科技风"),
            ("目标", "年化收益率 200%"),
            ("作者", "OpenClaw AI Assistant")
        ]
        
        for label, value in info:
            row = tk.Frame(version_frame, bg=Colors.BG_CARD)
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label, bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                    font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=Colors.BG_CARD, fg=Colors.PRIMARY_LIGHT,
                    font=("Microsoft YaHei", 10, "bold")).pack(side=tk.RIGHT)
    
    def on_closing(self):
        """窗口关闭"""
        self.save_config()
        self.root.destroy()
    
    def run(self):
        """运行主循环"""
        self.root.mainloop()

if __name__ == '__main__':
    app = MainWindow()
    app.run()
