# 财务数据管理标签页

import tkinter as tk
from tkinter import ttk
from threading import Thread
from pathlib import Path
from datetime import datetime

# 确保能导入 core 模块
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.financial_data import FinancialDataManager
from core.config import config

class FinancialTab:
    """财务数据管理页面"""
    
    def __init__(self, parent):
        self.parent = parent
        self.manager = FinancialDataManager()
        self.setup_ui()
        self.refresh_stats()
    
    def setup_ui(self):
        """构建界面"""
        # 主容器（滚动）
        canvas = tk.Canvas(self.parent)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 内容区域
        self.build_content(scrollable_frame)
        
        # 初始加载统计信息
        self.refresh_stats()
    
    def build_content(self, parent):
        """构建内容组件"""
        # 1. 数据状态卡片
        self.create_status_card(parent)
        
        # 2. 操作按钮区
        self.create_action_card(parent)
        
        # 3. 日志区域
        self.create_log_card(parent)
    
    def create_status_card(self, parent):
        """状态显示卡片"""
        card = ttk.LabelFrame(parent, text="📊 数据状态", padding=20)
        card.pack(fill=tk.X, padx=10, pady=10)
        
        # 状态标签
        self.status_labels = {}
        
        items = [
            ("股票数量", "0 支"),
            ("记录总数", "0 条"),
            ("数据期间", "无"),
            ("最后更新", "未更新"),
            ("数据库大小", "0 MB")
        ]
        
        for i, (key, default) in enumerate(items):
            row = ttk.Frame(card)
            row.pack(fill=tk.X, pady=5)
            
            ttk.Label(row, text=f"{key}:", width=15, font=('Microsoft YaHei', 10)).pack(side=tk.LEFT)
            lbl = ttk.Label(row, text=default, foreground="blue")
            lbl.pack(side=tk.LEFT)
            self.status_labels[key] = lbl
    
    def create_action_card(self, parent):
        """操作按钮卡片"""
        card = ttk.LabelFrame(parent, text="🛠️ 操作", padding=20)
        card.pack(fill=tk.X, padx=10, pady=10)
        
        # 按钮区
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="🔄 立即更新", 
                  command=self.on_update_clicked, width=20).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="📋 查看统计", 
                  command=self.refresh_stats, width=20).pack(side=tk.LEFT, padx=5)
        
        # 首次初始化提示
        ttk.Label(card, text="首次使用请下载 2023/2024 年报数据：", 
                 font=('Microsoft YaHei', 9)).pack(anchor=tk.W, pady=(10, 5))
        
        init_frame = ttk.Frame(card)
        init_frame.pack(fill=tk.X)
        
        ttk.Button(init_frame, text="📥 初始化下载（2023/2024 年报）", 
                  command=self.on_init_download, width=30).pack(side=tk.LEFT, padx=5)
        
        # 说明文字
        desc = """说明：
1. 初始化下载：下载 20231231 和 20241231 两个年度的财务数据
2. 自动更新：检测并下载最新发布的财报
3. 财务数据用于筛选策略中的 ROE、ROIC 等指标"""
        ttk.Label(card, text=desc, foreground="gray", 
                 justify=tk.LEFT).pack(anchor=tk.W, pady=10)
    
    def create_log_card(self, parent):
        """数据预览 & 日志区域"""
        # 使用 PanedWindow 分割预览和日志
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 1. 数据预览
        preview_frame = ttk.LabelFrame(paned, text="🔍 数据预览 (最新 100 条)", padding=5)
        paned.add(preview_frame, weight=3)

        columns = ('code', 'period', 'roe', 'roic', 'revenue_yoy', 'gross_margin', 'updated')
        self.tree = ttk.Treeview(preview_frame, columns=columns, show='headings', height=8)
        
        col_configs = [
            ('code', '代码', 100), ('period', '报告期', 100), ('roe', 'ROE%', 80),
            ('roic', 'ROIC%', 80), ('revenue_yoy', '营收增长%', 100),
            ('gross_margin', '毛利率%', 80), ('updated', '更新时间', 150)
        ]
        
        for col, heading, width in col_configs:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=tk.CENTER)
        
        sb_y = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb_y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

        # 2. 日志区域
        log_card = ttk.LabelFrame(paned, text="📝 运行日志", padding=5)
        paned.add(log_card, weight=2)
        
        log_frame = ttk.Frame(log_card)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=8, width=80, 
                                font=('Consolas', 9), bg='#f0f0f0')
        sb_log = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb_log.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_log.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log("财务数据管理模块就绪")

    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.parent.update()
    
    def refresh_stats(self):
        """刷新统计信息并加载预览数据"""
        try:
            stats = self.manager.get_statistics()
            
            self.status_labels['股票数量'].config(text=f"{stats['total_stocks']} 支")
            self.status_labels['记录总数'].config(text=f"{stats['total_records']} 条")
            self.status_labels['数据期间'].config(text=", ".join(stats['periods']) if stats['periods'] else "无数据")
            self.status_labels['最后更新'].config(
                text=stats['last_updated'][:19] if stats['last_updated'] else "未更新"
            )
            self.status_labels['数据库大小'].config(text=f"{stats['db_size_mb']:.1f} MB")
            
            # 更新预览表格
            import sqlite3
            import pandas as pd
            with sqlite3.connect(self.manager.db_path) as conn:
                # 获取数据库中真实存在的列名
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(financial_indicators)")
                cols = [row[1] for row in cursor.fetchall()]
                
                # 智能选择存在的列
                query_cols = ['ts_code', 'period']
                if 'roe_dt' in cols: query_cols.append('roe_dt')
                if 'roic' in cols: query_cols.append('roic')
                if 'tr_yoy' in cols: query_cols.append('tr_yoy')
                if 'gpm' in cols: query_cols.append('gpm')
                query_cols.append('updated_at')
                
                sql = f"SELECT {', '.join(query_cols)} FROM financial_indicators ORDER BY updated_at DESC LIMIT 100"
                df = pd.read_sql_query(sql, conn)
                
                # 清空旧数据
                for item in self.tree.get_children():
                    self.tree.delete(item)
                    
                # 插入新数据
                for _, row in df.iterrows():
                    self.tree.insert('', tk.END, values=(
                        row['ts_code'], row['period'], 
                        f"{row.get('roe_dt', 0):.2f}%" if row.get('roe_dt') else "-",
                        f"{row.get('roic', 0):.2f}%" if row.get('roic') else "-",
                        f"{row.get('tr_yoy', 0):.2f}%" if row.get('tr_yoy') else "-",
                        f"{row.get('gpm', 0):.2f}%" if row.get('gpm') else "-",
                        row['updated_at'][:16] if row['updated_at'] else "-"
                    ))

            self.log("统计及预览数据已同步最新")
        except Exception as e:
            self.log(f"❌ 统计刷新失败: {e}")
            import traceback
            traceback.print_exc()
    
    def on_update_clicked(self):
        """点击更新按钮"""
        from core.config import config
        token = config.get_tushare_token()
        if not token:
            self.log("❌ 未找到 TUSHARE_TOKEN，请先配置")
            return
        
        self.log("🚀 正在连接 Tushare 获取全市场最新财务指标...")
        Thread(target=self._update_worker, args=(token,), daemon=True).start()
    
    def _update_worker(self, token):
        """后台更新线程"""
        try:
            count = self.manager.update_latest(token)
            self.log(f"✅ 全市场数据同步完成！合并处理了 {count} 条记录。")
            self.parent.after(0, self.refresh_stats)
            # 同时尝试刷新主窗口状态
            try:
                # 寻找主窗口实例并刷新
                root = self.parent.winfo_toplevel()
                if hasattr(root, 'refresh_system_status'):
                    self.parent.after(100, root.refresh_system_status)
            except: pass
        except Exception as e:
            self.log(f"❌ 更新失败: {e}")
    
    def on_init_download(self):
        """首次初始化下载"""
        token = config.get_tushare_token()
        if not token:
            self.log("❌ 未找到 TUSHARE_TOKEN，请先配置")
            return
        
        # 检查是否已下载
        stats = self.manager.get_statistics()
        if '20231231' in stats['periods'] and '20241231' in stats['periods']:
            self.log("⚠️ 已检测到 2023/2024 年报数据，无需重复下载")
            return
        
        self.log("开始初始化下载（2023/2024 年报）...")
        Thread(target=self._init_download_worker, args=(token,), daemon=True).start()
    
    def _init_download_worker(self, token):
        """后台初始化下载线程"""
        try:
            count = self.manager.download_periods(token, ['20231231', '20241231'])
            if count > 0:
                self.log(f"✅ 初始化完成，共 {count} 条记录")
                self.refresh_stats()
            else:
                self.log("❌ 未下载到任何数据，请检查 token 或网络")
        except Exception as e:
            self.log(f"❌ 下载失败: {e}")
