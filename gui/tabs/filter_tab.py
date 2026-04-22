# 筛选器标签页 - 投资级执行引擎 (同步增强版)

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import threading
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.financial_data import FinancialDataManager
from core.stock_manager import StockManager
from core.strategy import StrategyManager
from core.daily_data import DailyDataManager
from core.indicators import Indicators
from gui.widgets.filter_panel import FilterPanel

class FilterTab:
    def __init__(self, parent):
        self.parent = parent
        self.financial_manager = FinancialDataManager()
        self.stock_manager = StockManager()
        self.strategy_manager = StrategyManager()
        self.daily_manager = DailyDataManager()
        self.setup_ui()
    
    def setup_ui(self):
        paned = ttk.PanedWindow(self.parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(paned, width=350)
        paned.add(left_frame, weight=0)
        
        # 初始加载列表
        self.strategy_manager.load_all()
        strategies = [s.name for s in self.strategy_manager.get_all()]
        self.filter_panel = FilterPanel(left_frame, self.on_filter_clicked, self.on_save_strategy, 
                                       strategy_list=strategies, stock_manager=self.stock_manager)
        self.filter_panel.on_load_strategy_callback = self.on_load_strategy
        self.filter_panel.pack(fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        stats_frame = ttk.Frame(right_frame, padding=10)
        stats_frame.pack(fill=tk.X)
        self.lbl_total = ttk.Label(stats_frame, text="✨ 投资级硬核引擎就绪", font=('Microsoft YaHei', 11))
        self.lbl_total.pack(side=tk.LEFT)
        self.pb = ttk.Progressbar(stats_frame, mode='indeterminate', length=200)
        
        action_frame = ttk.Frame(stats_frame)
        action_frame.pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="📤 导出 CSV", command=self.on_export_results).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="📋 加入自选", command=self.on_add_all_watchlist).pack(side=tk.LEFT, padx=2)

        table_frame = ttk.Frame(right_frame, padding=(10, 0, 10, 10))
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ('code', 'name', 'sector', 'score', 'ma_desc', 'rsi_desc', 'vma_desc', 'roe', 'roic')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=30)
        col_cfgs = [
            ('code', '代码', 100), ('name', '名称', 120), ('sector', '我的版块', 100),
            ('score', '得分', 80), ('ma_desc', '价格均线', 120), ('rsi_desc', 'RSI强弱', 120),
            ('vma_desc', '成交量', 100), ('roe', 'ROE%', 80), ('roic', 'ROIC%', 80)
        ]
        for col, heading, width in col_cfgs:
            self.tree.heading(col, text=heading, command=lambda c=col: self.sort_column(c, False))
            self.tree.column(col, width=width, anchor=tk.CENTER)
        
        sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.tag_configure('high', foreground='#e63946', font=('Microsoft YaHei', 10, 'bold'))
        self.tree.tag_configure('medium', foreground='#f4a261')
        self.tree.bind('<Double-1>', self.on_item_double_clicked)
        self.tree.bind('<Button-3>', self.on_right_click)

    def on_right_click(self, event):
        """右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self.parent, tearoff=0)
            values = self.tree.item(item, 'values')
            from gui.utils import generate_stock_report
            menu.add_command(label="📊 生成深度财务报告", command=lambda: generate_stock_report(self.parent, values[0], values[1]))
            menu.add_command(label="📋 复制代码", command=lambda: self.copy_to_clipboard(values[0]))
            menu.add_separator()
            menu.add_command(label="📈 查看基本详情", command=lambda: self.on_item_double_clicked(None))
            menu.post(event.x_root, event.y_root)

    def copy_to_clipboard(self, text):
        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)
        messagebox.showinfo("成功", f"代码 {text} 已复制到剪贴板")

    def on_filter_clicked(self, params):
        self._start_filter_thread(params)

    def _start_filter_thread(self, params):
        if not self.pb.winfo_ismapped(): self.pb.pack(side=tk.LEFT, padx=15); self.pb.start()
        self.lbl_total.config(text="🔍 正在执行硬核扫描...")
        self.filter_panel.btn_run.config(state=tk.DISABLED)
        for item in self.tree.get_children(): self.tree.delete(item)
        threading.Thread(target=self._run_filter_thread, args=(params,), daemon=True).start()

    def _run_filter_thread(self, params):
        try:
            # 1. 范围与财务 (SQL)
            sectors = params.get('sectors', [])
            ts_codes = None
            
            if sectors and "全市场" not in sectors:
                ts_codes = []
                from core.watchlist import WatchlistManager
                wm = WatchlistManager()
                
                for s in sectors:
                    if s.startswith("[我的版块] "):
                        # 处理自定义我的版块
                        group_name = s.replace("[我的版块] ", "")
                        group_df = wm.get_all(source=group_name)
                        ts_codes.extend(group_df['ts_code'].tolist())
                    else:
                        # 处理官方行业
                        ts_codes.extend(self.stock_manager.get_codes_by_sector(s))
                ts_codes = list(set(ts_codes))
                
                if not ts_codes:
                    self.parent.after(0, lambda: messagebox.showinfo("结果", "选定我的版块内无股票，请检查自选股分组。"))
                    return

            df_results = self.financial_manager.screen_stocks(
                params['financial_filters'], min_satisfied=0, 
                require_annual=params.get('require_annual', True), ts_codes=ts_codes
            )
            if df_results.empty:
                self.parent.after(0, lambda: messagebox.showinfo("结果", "财务过滤后 0 只入围。"))
                return

            # 2. 技术拦截 (Python)
            stock_codes = df_results['ts_code'].tolist()
            df_daily = self.daily_manager.get_all_daily_trade(stock_codes[:1000], limit=350)
            tp = params.get('tech_params', {})
            
            final_list = []
            import numpy as np
            for _, fin_row in df_results.iterrows():
                code = fin_row['ts_code']
                stock_df = df_daily[df_daily['ts_code'] == code] if not df_daily.empty else pd.DataFrame()
                sig = Indicators.get_signals(stock_df, tp) if not stock_df.empty else {}
                
                # ---- 52周价格区间硬过滤 ----
                p52f = params.get('price_distance_filters', {})
                pct_hi = sig.get('pct_from_52w_high', 0)
                if p52f.get('enable_52w_high') and pct_hi is not None and not np.isnan(pct_hi):
                    if abs(pct_hi) > p52f.get('pct_within_52w_high_max', 25):
                        continue  # 超过距52周高点上限，直接跳过
                pct_lo = sig.get('pct_from_52w_low', 0)
                if p52f.get('enable_52w_low') and pct_lo is not None and not np.isnan(pct_lo):
                    if pct_lo < p52f.get('pct_above_52w_low_min', 0):
                        continue  # 低于距52周低点下限，直接跳过

                # --- 核心打分引擎 (总分 100) ---
                score = 0
                
                # 1. 财务质量 (20分)
                roe = fin_row.get('roe_dt', 0)
                if roe >= 15: score += 8
                elif roe >= 10: score += 4
                
                gpm = fin_row.get('grossprofit_margin', 0)
                if gpm >= 35: score += 8
                elif gpm >= 20: score += 4
                
                debt = fin_row.get('debt_to_assets', 100)
                if debt <= 45: score += 4
                elif debt <= 60: score += 2

                # 2. 成长性与加速 (25分)
                tr_yoy = fin_row.get('tr_yoy', 0)
                if tr_yoy >= 30: score += 10
                elif tr_yoy >= 15: score += 5
                
                profit_yoy = fin_row.get('dt_netprofit_yoy', 0)
                if profit_yoy >= 30: score += 10
                elif profit_yoy >= 15: score += 5
                
                # 加速项: 季度增速 > 年度均值
                if fin_row.get('q_sales_yoy', 0) > tr_yoy: score += 5

                # 3. 技术形态 (20分)
                if sig.get('ma_long_order'): score += 10
                
                # 突破/回踩判断: 现价在 MA20 上方 0%-5% 之间
                cur_price = stock_df['close'].iloc[-1] if not stock_df.empty else 0
                ma20 = sig.get('ma20', 0)
                if ma20 > 0 and 1.0 <= (cur_price / ma20) <= 1.05:
                    score += 10 # 刚起步或完美回踩
                elif ma20 > 0 and 0.98 <= (cur_price / ma20) < 1.0:
                    score += 5  # 强势整理中

                # 4. 预期差 (20分)
                # RSI 状态: 45-65 是“还没被充分炒作”的启动区
                rsi = sig.get(f"rsi{tp['rsi_periods'][0]}", 50)
                if 45 <= rsi <= 65: score += 15
                elif rsi < 45: score += 5 # 底部磨底，预期差大但动能弱
                
                # 简单估值预期 (PB < 4 给予溢价)
                # 注：这里暂时用 RSI 低位模拟预期提升空间，若有 PE 数据效果更佳
                if rsi < 55: score += 5

                # 5. 资金行为 (15分)
                if sig.get('vma_gold_cross'):
                    # 计算量比 (今日量 / 5日均量)
                    vol_series = stock_df['vol'].tail(5)
                    if len(vol_series) == 5:
                        v_ratio = vol_series.iloc[-1] / vol_series.mean()
                        if v_ratio >= 1.5: score += 15
                        elif v_ratio >= 1.1: score += 8
                        else: score += 5
                    else: score += 5
                
                item = {**fin_row.to_dict(), **sig, 'final_score': int(score)}
                final_list.append(item)
            
            final_list.sort(key=lambda x: x['final_score'], reverse=True)
            self.parent.after(0, lambda: self._update_ui_with_results(final_list, tp))
            
        except Exception as e:
            import traceback; traceback.print_exc()
            self.parent.after(0, lambda m=str(e): messagebox.showerror("错误", m))
        finally:
            self.parent.after(0, self._finish_loading)

    def _update_ui_with_results(self, final_list, tp):
        for i, row in enumerate(final_list):
            info = self.stock_manager.get_stock_info(row['ts_code'])
            name = info['name'] if info else row['ts_code']
            sector = info['industry'] if info else '-'
            
            ma_txt = "多头排列" if row.get('ma_long_order') else "整理"
            rsi_txt = f"S:{row.get(f'rsi{tp['rsi_periods'][0]}',0):.0f} L:{row.get(f'rsi{tp['rsi_periods'][1]}',0):.0f}"
            vma_txt = "放量" if row.get('vma_gold_cross') else "-"
            
            tag = 'high' if row['final_score'] >= 85 else 'medium' if row['final_score'] >= 70 else ''
            self.tree.insert('', tk.END, values=(
                row['ts_code'], name, sector, f"{row['final_score']}分",
                ma_txt, rsi_txt, vma_txt,
                f"{row.get('roe_dt',0):.1f}%", f"{row.get('roic',0):.1f}%"
            ), tags=(tag,))
        self.lbl_total.config(text=f"✅ 筛选完成：共 {len(final_list)} 支标的符合要求")

    def _finish_loading(self):
        self.pb.stop(); self.pb.pack_forget()
        self.filter_panel.btn_run.config(state=tk.NORMAL)

    def on_load_strategy(self, name):
        # 关键：强制刷新硬盘数据
        self.strategy_manager.load_all()
        s = self.strategy_manager.get(name)
        if s: self.filter_panel.set_params(s.params)

    def on_save_strategy(self, params):
        from tkinter import simpledialog
        name = simpledialog.askstring("保存", "策略名称:")
        if not name: return
        from core.strategy import Strategy
        f_p = self.strategy_manager.strategies_dir / f"{name}.json"
        s = Strategy({'name': name, 'params': params, '_file_path': str(f_p)})
        if s.save():
            self.strategy_manager.strategies[name] = s
            self.filter_panel.strategy_combo.config(values=[st.name for st in self.strategy_manager.get_all()])
            messagebox.showinfo("成功", "策略已同步")

    def on_export_results(self):
        items = self.tree.get_children()
        if not items: return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            data = [self.tree.item(i, 'values') for i in items]
            pd.DataFrame(data, columns=['代码','名称','行业','评分','均线','RSI','成交量','ROE','ROIC']).to_csv(path, index=False, encoding='utf-8-sig')

    def on_add_all_watchlist(self):
        items = self.tree.get_children()
        if not items or not messagebox.askyesno("确认", f"添加 {len(items)} 支股票？"): return
        from core.watchlist import WatchlistManager
        wm = WatchlistManager(); count = 0
        for it in items:
            v = self.tree.item(it, 'values')
            if wm.add_stock(v[0], name=v[1], sector=v[2]): count += 1
        messagebox.showinfo("完成", f"已添加 {count} 支")

    def on_item_double_clicked(self, event):
        sel = self.tree.selection()
        if not sel: return
        v = self.tree.item(sel[0], 'values')
        messagebox.showinfo(f"详情: {v[1]}", f"均线状态: {v[4]}\nRSI状态: {v[5]}\n成交量: {v[6]}")

    def sort_column(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        l.sort(reverse=reverse)
        for i, (val, k) in enumerate(l): self.tree.move(k, '', i)
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))
