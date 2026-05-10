# gui/tabs/watchlist_tab.py
# 全部股票管理标签页 (由原自选股管理页面重构)

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from pathlib import Path
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.watchlist import WatchlistManager
from core.stock_manager import StockManager
from core.daily_data import DailyDataManager

class AllStocksTab:
    """全部股票管理页面 (支持全市场展示与自选标记)"""
    
    def __init__(self, parent):
        self.parent = parent
        self.watchlist_manager = WatchlistManager()
        self.stock_manager = StockManager()
        self.daily_manager = DailyDataManager()
        
        # 状态变量
        self.current_filter_group = '全部'
        self.current_filter_tag = '全部标签'  # 标签过滤
        self.sort_column = 'ts_code'
        self.sort_reverse = False
        self.all_stocks_df = pd.DataFrame() # 缓存全量数据
        
        self.setup_ui()
        # 延迟 100 毫秒加载数据，确保主循环已启动，避免线程冲突
        self.parent.after(100, self.refresh_data)
    
    def setup_ui(self):
        """构建界面"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.parent, padding=10)
        toolbar.pack(fill=tk.X)
        
        # 搜索框
        ttk.Label(toolbar, text="搜索 (代码/名称):").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_triggered)
        ttk.Entry(toolbar, textvariable=self.search_var, width=20).pack(side=tk.LEFT, padx=5)
        
        # 标签筛选下拉框（统一替代"展示范围"，直接用标签过滤）
        ttk.Label(toolbar, text="标签筛选:").pack(side=tk.LEFT, padx=5)
        self.tag_var = tk.StringVar(value='全部')
        self.tag_filter_combo = ttk.Combobox(toolbar, textvariable=self.tag_var, state='readonly', width=16)
        self._load_tag_combobox()  # 同步加载标签
        self.tag_filter_combo.pack(side=tk.LEFT, padx=5)
        self.tag_filter_combo.bind('<<ComboboxSelected>>', self.on_filter_changed)
        
        # 按钮区
        ttk.Button(toolbar, text="📈 更新全市场行情", command=self.on_update_market_prices).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="🔄 刷新列表", command=self.refresh_data).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="⭐ 设为自选/取消", command=self.on_toggle_watchlist).pack(side=tk.RIGHT, padx=2)
        
        # 主表格区域
        table_frame = ttk.Frame(self.parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 定义列 (新增 'no' 序号列)
        columns = ('no', 'is_fav', 'ts_code', 'name', 'price', 'pct_chg', 'industry', 'market')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # 列标题与排序功能
        column_names = {
            'no': '序号',
            'is_fav': '自选',
            'ts_code': '代码',
            'name': '名称',
            'price': '最新价',
            'pct_chg': '涨跌幅%',
            'industry': '我的版块',
            'market': '市场'
        }
        
        for col, name in column_names.items():
            self.tree.heading(col, text=name, command=lambda c=col: self.on_header_click(c))
            
        # 列宽与对齐方式
        self.tree.column('no', width=50, anchor=tk.CENTER)
        self.tree.column('is_fav', width=50, anchor=tk.CENTER)
        self.tree.column('ts_code', width=100)
        self.tree.column('name', width=100)
        self.tree.column('price', width=90, anchor=tk.E)
        self.tree.column('pct_chg', width=90, anchor=tk.E)
        # 核心优化：我的版块和市场文字均右对齐，拉开列间距
        self.tree.column('industry', width=130, anchor=tk.E)
        self.tree.column('market', width=80, anchor=tk.E)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定事件
        self.tree.bind('<Double-1>', self.on_item_double_clicked)
        self.tree.bind('<Button-3>', self.on_right_click)
        
        # 配置颜色
        self.tree.tag_configure('up', foreground='red')
        self.tree.tag_configure('down', foreground='green')
        self.tree.tag_configure('fav', background='#fff8e1') # 浅黄色背景标识自选股
        
        # 底部状态栏
        self.status_label = ttk.Label(self.parent, text="就绪")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

    def refresh_data(self):
        """从数据库加载全量基础信息并缓存"""
        self.update_status("正在加载股票基础数据...")
        
        def load_worker():
            import sqlite3
            with sqlite3.connect(self.stock_manager.db_path) as conn:
                df = pd.read_sql_query("SELECT ts_code, name, industry, market FROM stocks_basic", conn)
            
            # 2. 获取自选股名单
            watchlist_codes = set(self.watchlist_manager.get_all()['ts_code'].tolist())
            df['is_fav'] = df['ts_code'].apply(lambda x: '⭐' if x in watchlist_codes else '')
            
            # 3. 获取用户自定义标签（从 stock_tags 表，多个标签用逗号连接）
            with sqlite3.connect(self.stock_manager.db_path) as conn:
                tags_df = pd.read_sql_query(
                    """SELECT ts_code, GROUP_CONCAT(tag_name, ', ') as user_tags
                    FROM stock_tags GROUP BY ts_code""", conn
                )
            df = pd.merge(df, tags_df, on='ts_code', how='left')
            df['user_tags'] = df['user_tags'].fillna('')
            
            # 4. 获取最新行情日期
            latest_date = self.daily_manager.get_overall_latest_date()
            
            # 5. 批量获取最新行情
            if latest_date:
                with sqlite3.connect(self.daily_manager.db_path) as conn:
                    price_df = pd.read_sql_query(
                        "SELECT ts_code, close as price, pct_chg FROM daily_trade WHERE trade_date = ?", 
                        conn, params=(latest_date,)
                    )
                df = pd.merge(df, price_df, on='ts_code', how='left')
            else:
                df['price'] = None
                df['pct_chg'] = None
            
            self.all_stocks_df = df
            # 使用 after_idle 确保主循环已就绪，避免 RuntimeError
            try:
                self.parent.after_idle(self.display_data)
            except RuntimeError:
                # 主循环未就绪，丢弃（初始化完成会再次调用 refresh_data）
                pass
            
        threading.Thread(target=load_worker, daemon=True).start()

    def display_data(self):
        """根据搜索和过滤条件显示数据"""
        # 清空
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        df = self.all_stocks_df.copy()
        
        # 1. 搜索过滤
        keyword = self.search_var.get().strip().upper()
        if keyword:
            df = df[df['ts_code'].str.contains(keyword) | df['name'].str.contains(keyword)]
            
        # 2. 标签过滤（单一下拉框：全部 / 仅自选 / 各标签）
        selected = self.tag_var.get()
        if selected == '仅自选':
            df = df[df['is_fav'] == '⭐']
        elif selected != '全部':
            # 按标签过滤（user_tags 列包含该标签）
            df = df[df['user_tags'].str.contains(selected, na=False)]
            
        # 3. 排序
        if self.sort_column in df.columns:
            df = df.sort_values(by=self.sort_column, ascending=not self.sort_reverse)
            
        # 4. 填充 (加入序号计数)
        for i, (_, row) in enumerate(df.iterrows(), 1):
            pct_chg = row['pct_chg']
            tag = ''
            if pd.notnull(pct_chg):
                tag = 'up' if pct_chg > 0 else 'down' if pct_chg < 0 else ''
                pct_chg_str = f"{pct_chg:.2f}%"
            else:
                pct_chg_str = '-'
                
            price_str = f"{row['price']:.2f}" if pd.notnull(row['price']) else '-'
            
            tags = [tag]
            if row['is_fav'] == '⭐':
                tags.append('fav')
                
            self.tree.insert('', tk.END, values=(
                i, # 序号
                row['is_fav'],
                row['ts_code'],
                row['name'],
                price_str,
                pct_chg_str,
                row['user_tags'] or '-',  # 用户自定义标签
                row['market']
            ), tags=tuple(tags))
            
        count = len(df)
        self.update_status(f"共展示 {count} 只股票 (排序: {self.sort_column} {'降序' if self.sort_reverse else '升序'})")

    def on_header_click(self, col):
        """点击表头排序"""
        if col == 'no': return # 序号列不支持排序，它是动态生成的
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self.display_data()

    def on_search_triggered(self, *args):
        """搜索触发"""
        self.display_data()
        
    def on_filter_changed(self, event=None):
        """标签筛选切换"""
        self.display_data()
    
    def _load_tag_combobox(self):
        """同步加载标签下拉框（在主线程调用，避免 after_idle 线程冲突）"""
        try:
            import sqlite3
            with sqlite3.connect(self.stock_manager.db_path) as conn:
                tag_cursor = conn.execute("SELECT DISTINCT tag_name FROM stock_tags ORDER BY tag_name")
                all_tags = [r[0] for r in tag_cursor.fetchall()]
            # 选项：全部 / 仅自选 / 各标签
            self.tag_filter_combo['values'] = ['全部', '仅自选'] + all_tags
        except Exception:
            self.tag_filter_combo['values'] = ['全部', '仅自选']

    def on_toggle_watchlist(self):
        """切换自选状态"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先在列表中选择股票")
            return
            
        for item in selection:
            values = self.tree.item(item, 'values')
            # 索引偏移：no=0, is_fav=1, ts_code=2, name=3
            ts_code = values[2]
            name = values[3]
            is_fav = values[1] == '⭐'
            
            if is_fav:
                self.watchlist_manager.remove_stock(ts_code, '自选股')
            else:
                self.watchlist_manager.add_stock(ts_code, name=name, source='自选股')
        
        self.refresh_data()

    def on_update_market_prices(self):
        """全市场行情异步同步"""
        from core.config import config
        token = config.get_tushare_token()
        if not token:
            messagebox.showwarning("提示", "未找到 TUSHARE_TOKEN，请在设置中配置。")
            return
            
        def update_worker():
            self.update_status("🔄 正在从 Tushare 同步全市场最新行情 (按日期)...")
            try:
                count = self.daily_manager.sync_market_data(token)
                self.update_status(f"✅ 全市场行情同步完成，新增 {count} 条记录")
                self.parent.after(0, self.refresh_data)
                messagebox.showinfo("同步成功", f"全市场行情同步完成！\n新增记录: {count}")
            except Exception as e:
                self.update_status(f"❌ 同步失败: {e}")
                messagebox.showerror("错误", f"同步行情失败: {e}")
        
        threading.Thread(target=update_worker, daemon=True).start()

    def update_status(self, message):
        """更新状态栏"""
        latest_date = self.daily_manager.get_overall_latest_date()
        date_hint = f" | 数据截止日期: {latest_date}" if latest_date else " | 无行情数据"
        self.status_label.config(text=message + date_hint)

    def on_item_double_clicked(self, event):
        """双击查看K线图"""
        selection = self.tree.selection()
        if not selection: return
        item = selection[0]
        values = self.tree.item(item, 'values')
        from gui.stock_chart import show_stock_chart
        show_stock_chart(self.parent, values[2], values[3])

    def on_right_click(self, event):
        """右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self.parent, tearoff=0)
            values = self.tree.item(item, 'values')
            is_fav = values[1] == '⭐'
            
            label = "⭐ 取消自选" if is_fav else "⭐ 设为自选"
            menu.add_command(label=label, command=self.on_toggle_watchlist)
            menu.add_command(label="📋 复制代码", command=lambda: self.copy_to_clipboard(values[2]))
            menu.add_separator()
            
            # 标签管理子菜单
            tags_submenu = tk.Menu(menu, tearoff=0)
            current_tags = self.watchlist_manager.get_tags_for_stock(values[2])
            if current_tags:
                tags_submenu.add_command(
                    label=f"当前标签: {', '.join(current_tags)}", 
                    state='disabled'
                )
                tags_submenu.add_separator()
                for t in current_tags:
                    tags_submenu.add_command(
                        label=f"❌ 移除「{t}」",
                        command=lambda _t=t, _c=values[2]: self._do_remove_tag(_c, _t)
                    )
            else:
                tags_submenu.add_command(label="(暂无标签)", state='disabled')
            
            tags_submenu.add_separator()
            # 列出其他可用标签（尚未打上的）
            all_tags = self.watchlist_manager.get_all_tags()
            for t in all_tags:
                if t not in current_tags:
                    tags_submenu.add_command(
                        label=f"➕ 打标签「{t}」",
                        command=lambda _t=t, _c=values[2]: self._do_add_tag(_c, _t)
                    )
            tags_submenu.add_command(
                label="🏷️ 新建标签…",
                command=lambda _c=values[2]: self._do_new_tag(_c)
            )
            menu.add_cascade(label="🏷️ 标签管理", menu=tags_submenu)
            
            menu.add_separator()
            from gui.utils import generate_stock_report
            menu.add_command(label="📊 生成深度财务报告", command=lambda: generate_stock_report(self.parent, values[2], values[3]))
            menu.add_command(label="📈 查看基本详情", command=lambda: self.on_item_double_clicked(None))
            menu.post(event.x_root, event.y_root)

    def copy_to_clipboard(self, text):
        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)
        self.update_status(f"已复制代码: {text}")

    def _do_add_tag(self, ts_code, tag_name):
        """为股票添加标签"""
        self.watchlist_manager.add_tag(ts_code, tag_name)
        self.update_status(f"已为 {ts_code} 添加标签「{tag_name}」")
        self.refresh_data()

    def _do_remove_tag(self, ts_code, tag_name):
        """为股票移除标签"""
        self.watchlist_manager.remove_tag(ts_code, tag_name)
        self.update_status(f"已移除 {ts_code} 的标签「{tag_name}」")
        self.refresh_data()

    def _do_new_tag(self, ts_code):
        """弹出对话框新建标签并打到股票上"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("新建标签")
        dialog.geometry("300x120")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()

        ttk.Label(dialog, text="标签名称:", font=('Microsoft YaHei', 10)).pack(pady=(15, 5))
        entry_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=entry_var, width=30, font=('Microsoft YaHei', 10))
        entry.pack(pady=5)
        entry.focus()

        def on_confirm():
            tag = entry_var.get().strip()
            if tag:
                self.watchlist_manager.add_tag(ts_code, tag)
                # 同步刷新下拉框标签列表
                all_tags = self.watchlist_manager.get_all_tags()
                self.tag_filter_combo['values'] = ['全部', '仅自选'] + all_tags
                self.refresh_data()
                self.update_status(f"已为 {ts_code} 新建并打上标签「{tag}」")
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确认", command=on_confirm).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

        entry.bind('<Return>', lambda e: on_confirm())

if __name__ == '__main__':
    root = tk.Tk()
    tab = AllStocksTab(root)
    root.mainloop()
