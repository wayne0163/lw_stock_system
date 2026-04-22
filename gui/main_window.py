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
class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("聪明小爪股票筛选系统")
        self.root.geometry("1400x850")

        # 配置全局字体
        self.default_font = ('Microsoft YaHei', 10)
        self.header_font = ('Microsoft YaHei', 12, 'bold')
        self.root.option_add("*Font", self.default_font)

        # 设置样式
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
            
            # 这里简单统计 stocks_basic 数量
            import sqlite3
            with sqlite3.connect(sm.db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM stocks_basic").fetchone()[0]

            self.navigation.update_status('财务日期', fin_period)
            self.navigation.update_status('行情日期', trade_date)
            self.navigation.update_status('股票总数', str(count))
            
            self.set_status(f"系统就绪 | 财务截止: {fin_period} | 行情截止: {trade_date}")
        except Exception as e:
            print(f"刷新系统状态失败: {e}")
            self.set_status("系统就绪（部分数据未加载）")

    def setup_style(self):
        """配置 TTK 样式"""
        style = ttk.Style()
        # 使用 clam 主题作为基础，因为它更易于自定义
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # 全局颜色配置
        bg_color = "#f5f5f7"
        accent_color = "#007aff" # 经典蓝

        style.configure(".", font=self.default_font, background=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground="#333333")

        # Notebook 样式
        style.configure("TNotebook", background=bg_color, padding=5)
        style.configure("TNotebook.Tab", padding=[15, 5], font=self.default_font)
        style.map("TNotebook.Tab", 
                  background=[("selected", "#ffffff")],
                  foreground=[("selected", accent_color)])

        # 按钮样式
        style.configure("TButton", padding=6, font=self.default_font)
        style.configure("Accent.TButton", foreground="white", background=accent_color)
        style.map("Accent.TButton", 
                  background=[("active", "#005bb5"), ("pressed", "#004487")])

        # Treeview 样式
        style.configure("Treeview", rowheight=30, font=self.default_font)
        style.configure("Treeview.Heading", font=self.header_font, padding=5)

        # LabelFrame 样式
        style.configure("TLabelframe", background=bg_color, bordercolor="#dddddd")
        style.configure("TLabelframe.Label", font=self.header_font, background=bg_color, foreground=accent_color)

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
        """三栏布局"""
        # 主容器
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 左侧导航（固定宽度 200）
        self.nav_frame = ttk.Frame(main_container, width=200)
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.nav_frame.pack_propagate(False)
        
        self.navigation = NavigationPanel(self.nav_frame, self.on_nav_clicked)
        self.navigation.pack(fill=tk.BOTH, expand=True)
        
        # 右侧内容区
        content_frame = ttk.Frame(main_container)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Notebook（标签页）
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
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
            
            tab_defs = [
                ('watchlist', '📋 全部股票', AllStocksTab),
                ('financial', '💰 财务数据', FinancialTab),
                ('filter', '🔍 筛选器', FilterTab),
                ('strategy', '⚙️ 策略管理', StrategyTab),
                ('positions', '📈 持仓管理', PositionsTab),
                ('reports', '📊 报告查看', ReportsTab),
                ('settings', '🔧 设置', SettingsTab)
            ]
            
            for tab_id, tab_name, tab_class in tab_defs:
                frame = ttk.Frame(self.notebook)
                
                if tab_class:
                    try:
                        tab_instance = tab_class(frame)
                        self.tabs[tab_id] = tab_instance
                    except Exception as e:
                        print(f"加载 Tab '{tab_name}' 失败: {e}")
                        import traceback
                        traceback.print_exc()
                        # 显示错误
                        err_label = ttk.Label(frame, 
                                            text=f"{tab_name}\n加载失败\n{str(e)[:80]}", 
                                            foreground="red",
                                            anchor=tk.CENTER,
                                            justify=tk.CENTER)
                        err_label.pack(expand=True)
                else:
                    ttk.Label(frame, text=f"{tab_name} - 开发中...", 
                             font=('Microsoft YaHei', 14)).pack(expand=True)
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
            frame = ttk.Frame(self.notebook)
            ttk.Label(frame, text=f"加载失败:\n{e}", foreground="red").pack(expand=True)
            self.notebook.add(frame, text="错误")
    
    def setup_statusbar(self):
        """状态栏"""
        self.statusbar = ttk.Frame(self.root, height=25)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(self.statusbar, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.version_label = ttk.Label(self.statusbar, text="v0.1.0")
        self.version_label.pack(side=tk.RIGHT, padx=10)
    
    def set_status(self, message):
        """更新状态栏"""
        self.status_label.config(text=message)
        self.root.update()
    
    # === 事件处理 ===
    
    def on_nav_clicked(self, item_id):
        """导航点击事件"""
        # 动态映射
        tab_ids = list(self.tabs.keys())
        if item_id in self.tabs:
            index = tab_ids.index(item_id)
            self.notebook.select(index)
        else:
            print(f"警告: 找不到 tab '{item_id}'")
    
    def on_tab_changed(self, event):
        """标签页切换"""
        current = self.notebook.select()
        tab_text = self.notebook.tab(current, 'text')
        self.set_status(f"切换到: {tab_text}")
    
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
        messagebox.showinfo("帮助", "聪明小爪股票系统 v0.1.0\n\n"
                          "功能：\n"
                          "• 自选股管理\n"
                          "• 财务数据管理\n"
                          "• 股票筛选\n"
                          "• 策略管理\n\n"
                          "更多信息请查看文档。")
    
    def on_about(self):
        """菜单：关于"""
        messagebox.showinfo("关于", "聪明小爪股票系统\n"
                          "版本：v0.1.0\n"
                          "作者：OpenClaw\n"
                          "目标：年化收益率 200%")
    
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
