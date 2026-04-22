import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import sqlite3
from datetime import datetime
import json
from pathlib import Path
from core.config import config

class PositionsTab(tk.Frame):
    def __init__(self, parent, position_manager=None):
        super().__init__(parent)
        self.pack(fill='both', expand=True)
        if position_manager is None:
            from core.positions import PositionManager
            self.pm = PositionManager()
        else:
            self.pm = position_manager
        # 使用全局配置
        self.config_manager = config
        self.config = self.config_manager.config
        self.init_ui()

    def init_ui(self):
        # 1. 资产看板
        self.summary_frame = ttk.LabelFrame(self, text=" 账户资产概览 ", padding=10)
        self.summary_frame.pack(fill='x', padx=10, pady=5)
        self.summary_labels = {}
        for label, key in [("可用现金", "cash"), ("持仓市值", "market_value"), ("总资产", "total_assets"), ("总盈亏", "total_pnl")]:
            f = ttk.Frame(self.summary_frame)
            f.pack(side='left', expand=True)
            ttk.Label(f, text=label, foreground="gray").pack()
            val_lab = ttk.Label(f, text="¥0.00", font=("Arial", 12, "bold"))
            val_lab.pack()
            self.summary_labels[key] = val_lab

        # 2. 按钮区
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text="🔄 刷新行情/资产", command=self.refresh_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="📜 历史账目/修正", command=self.show_ledger_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🤖 智能审计报告", command=self.generate_ai_report).pack(side='left', padx=5)
        
        ttk.Button(btn_frame, text="💰 外部资金存取", command=self.show_cash_dialog).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="➕ 手动建仓", command=self.show_buy_dialog).pack(side='right', padx=5)
        
        # 状态栏：显示数据一致性状态
        self.status_label = ttk.Label(btn_frame, text="", foreground="green")
        self.status_label.pack(side='right', padx=10)

        # 3. 数据表格
        self.paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.paned.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 上持仓
        pos_f = ttk.LabelFrame(self.paned, text=" 当前持仓明细 ")
        self.paned.add(pos_f, weight=3)
        self.tree = ttk.Treeview(pos_f, columns=("c", "n", "q", "cp", "cur", "sl", "tp", "pnl", "pct", "d"), show='headings')
        cols = [("c", "代码"), ("n", "名称"), ("q", "持仓"), ("cp", "成本"), ("cur", "现价"), 
                ("sl", "止损"), ("tp", "止盈"), ("pnl", "盈亏"), ("pct", "盈亏%"), ("d", "日期")]
        for cid, head in cols:
            self.tree.heading(cid, text=head)
            self.tree.column(cid, width=80, anchor='center')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind("<Double-1>", lambda e: self.on_double_click())
        self.tree.bind("<Button-3>", self.on_right_click)

        # 下流水
        log_f = ttk.LabelFrame(self.paned, text=" 最近综合流水 ")
        self.paned.add(log_f, weight=2)
        self.log_tree = ttk.Treeview(log_f, columns=("d", "t", "n", "p", "q", "f", "b", "r"), show='headings', height=8)
        l_cols = [("d", "日期", 90), ("t", "动作", 60), ("n", "项目", 100), ("p", "成交价/金额", 90), 
                  ("q", "数量", 60), ("f", "费用", 50), ("b", "余额", 100), ("r", "备注", 250)]
        for cid, head, w in l_cols:
            self.log_tree.heading(cid, text=head)
            self.log_tree.column(cid, width=w, anchor='center')
        self.log_tree.column("r", anchor='w')
        self.log_tree.pack(fill='both', expand=True)
        
        self.refresh_all()

    def on_right_click(self, event):
        """右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self, tearoff=0)
            values = self.tree.item(item, 'values')
            
            from gui.utils import generate_stock_report
            menu.add_command(label="📊 生成深度财务报告", command=lambda: generate_stock_report(self, values[0], values[1]))
            menu.add_command(label="📋 复制代码", command=lambda: self.copy_to_clipboard(values[0]))
            menu.add_separator()
            menu.add_command(label="📉 卖出/减仓", command=self.on_double_click)
            menu.post(event.x_root, event.y_root)

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("成功", f"代码 {text} 已复制到剪贴板")

    def generate_ai_report(self):
        try:
            import subprocess, os, sys
            env = os.environ.copy()
            env["PYTHONPATH"] = "."
            report_dir = Path("output/reports")
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用 sys.executable 并移除强制编码，手动处理解码
            res = subprocess.run([sys.executable, "scripts/prepare_ai_analysis.py"], 
                                 capture_output=True, env=env)
            
            try:
                stdout = res.stdout.decode('utf-8')
                stderr = res.stderr.decode('utf-8')
            except UnicodeDecodeError:
                stdout = res.stdout.decode('gbk', errors='ignore')
                stderr = res.stderr.decode('gbk', errors='ignore')
                
            if res.returncode == 0:
                messagebox.showinfo("Success", "报告已生成在 output/reports/AI_Audit_Report.md")
            else:
                messagebox.showerror("Error", stderr)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def check_and_fix_positions(self):
        """检查 positions 与 trade_log 一致性，不一致时自动重建。"""
        import sqlite3
        from pathlib import Path
        
        db_path = Path(self.pm.db_path)
        if not db_path.exists():
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 加载股票代码映射（symbol → ts_code，补全后缀）
        code_map = {}
        try:
            cursor.execute("SELECT symbol, ts_code FROM stocks_basic")
            for row in cursor.fetchall():
                symbol, ts_code = row
                code_map[str(symbol)] = ts_code  # symbol 如 '688111' → ts_code '688111.SH'
        except:
            pass
        
        # 获取所有有交易的股票
        cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
        codes = [r[0] for r in cursor.fetchall()]
        
        mismatches = []
        for code in codes:
            # 计算理论持仓（基于 trade_log）
            cursor.execute("""
                SELECT trade_type, quantity FROM trade_log 
                WHERE ts_code = ? 
                ORDER BY trade_date ASC, id ASC
            """, (code,))
            trades = cursor.fetchall()
            net_qty = sum(q if t == 'BUY' else -q for t, q in trades)
            
            # 查询实际持仓（positions 中的 ts_code 可能带后缀，需补全）
            ts_code_for_query = code
            if '.' not in code and code in code_map:
                ts_code_for_query = code_map[code]
            
            cursor.execute("SELECT quantity FROM positions WHERE ts_code = ?", (ts_code_for_query,))
            pos_row = cursor.fetchone()
            pos_qty = pos_row[0] if pos_row else 0
            
            if net_qty != pos_qty:
                mismatches.append((code, net_qty, pos_qty))
        
        conn.close()
        
        if mismatches:
            # 发现不一致，直接重建持仓
            print(f"⚠️  发现 {len(mismatches)} 条持仓不一致，正在重建...")
            self.pm.rebuild_positions_from_logs()
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"已重建，请核对", foreground="orange")
        else:
            if hasattr(self, 'status_label'):
                self.status_label.config(text="数据一致", foreground="green")

    def clean_abnormal_trades(self):
        """清理异常交易：删除卖出数量大于当时持仓的 SELL 记录"""
        import sqlite3
        conn = sqlite3.connect(self.pm.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
        codes = [r[0] for r in cursor.fetchall()]
        
        abnormal_ids = []
        for code in codes:
            cursor.execute("""
                SELECT id, trade_type, quantity FROM trade_log 
                WHERE ts_code = ? 
                ORDER BY trade_date ASC, id ASC
            """, (code,))
            rows = cursor.fetchall()
            simulated_qty = 0
            for rid, ttype, qty in rows:
                if ttype == 'BUY':
                    simulated_qty += qty
                elif ttype == 'SELL':
                    if simulated_qty >= qty:
                        simulated_qty -= qty
                    else:
                        abnormal_ids.append(rid)
                        print(f"🗑️  标记异常交易 ID={rid}: {code} 卖出{qty}股，但当时仅持有{simulated_qty}股")
        
        if abnormal_ids:
            placeholders = ','.join(['?'] * len(abnormal_ids))
            cursor.execute(f"DELETE FROM trade_log WHERE id IN ({placeholders})", abnormal_ids)
            conn.commit()
            print(f"✅ 已删除 {len(abnormal_ids)} 条异常交易记录")
        
        conn.close()
    def check_and_fix_positions(self):
        """检查 positions 与 trade_log 一致性，不一致时自动重建。"""
        import sqlite3
        from pathlib import Path
        
        db_path = Path(self.pm.db_path)
        if not db_path.exists():
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有有交易的股票
        cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
        codes = [r[0] for r in cursor.fetchall()]
        
        mismatches = []
        for code in codes:
            cursor.execute("""
                SELECT trade_type, quantity FROM trade_log 
                WHERE ts_code = ? 
                ORDER BY trade_date ASC, id ASC
            """, (code,))
            trades = cursor.fetchall()
            net_qty = sum(q if t == 'BUY' else -q for t, q in trades)
            
            cursor.execute("SELECT quantity FROM positions WHERE ts_code = ?", (code,))
            pos_row = cursor.fetchone()
            pos_qty = pos_row[0] if pos_row else 0
            
            if net_qty != pos_qty:
                mismatches.append((code, net_qty, pos_qty))
        
        conn.close()
        
        if mismatches:
            # 发现不一致，自动重建
            print(f"⚠️  发现 {len(mismatches)} 条持仓不一致，正在自动修复...")
            # 先删除所有异常交易记录（卖出数量大于持仓的记录）
            self.clean_abnormal_trades()
            # 重建持仓
            self.pm.rebuild_positions_from_logs()
            # 更新状态栏（如果存在）
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"已自动修复 {len(mismatches)} 条不一致", foreground="orange")
        else:
            if hasattr(self, 'status_label'):
                self.status_label.config(text="数据一致", foreground="green")

    def clean_abnormal_trades(self):
        """清理异常交易记录：卖出数量大于当前持仓的记录（重复卖出）"""
        import sqlite3
        conn = sqlite3.connect(self.pm.db_path)
        cursor = conn.cursor()
        
        # 获取所有股票的持仓和交易
        cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
        codes = [r[0] for r in cursor.fetchall()]
        
        cleaned = 0
        for code in codes:
            # 计算当前理论持仓
            cursor.execute("""
                SELECT trade_type, quantity FROM trade_log 
                WHERE ts_code = ? 
                ORDER BY trade_date ASC, id ASC
            """, (code,))
            trades = cursor.fetchall()
            net_qty = 0
            for t, q in trades:
                if t == 'BUY':
                    net_qty += q
                elif t == 'SELL':
                    if net_qty >= q:
                        net_qty -= q
                    else:
                        # 异常：卖出数量大于当前持仓，标记为问题记录
                        print(f"⚠️  发现异常交易: {code} 卖出{q}股，但当前仅持有{net_qty}股，标记为待清理")
                        # 这里暂不删除，由 rebuild_positions_from_logs 处理
                        pass
        
        conn.close()
        return cleaned

    def refresh_all(self):
        """刷新所有数据：行情、持仓、流水。任何异常都会弹窗提示。"""
        import traceback
        try:
            # 🔧 先检查 positions 一致性，如果不一致则自动重建
            self.check_and_fix_positions()
            
            # 0. 自动同步行情现价 (从 daily_data.db 同步到 stock_data.db)
            try:
                from core.daily_data import DailyDataManager
                ddm = DailyDataManager()
                df_pos = self.pm.get_all()
                if not df_pos.empty:
                    codes = df_pos['ts_code'].unique().tolist()
                    prices = ddm.get_latest_prices(codes)
                    if prices:
                        self.pm.update_prices_bulk(prices)
            except Exception as e:
                print(f"自动同步现价失败: {e}")

            s = self.pm.get_position_summary()
            # 更新资产概览（所有字段保护性访问）
            self.summary_labels['cash'].config(text=f"¥{s.get('cash', 0):,.2f}")
            self.summary_labels['market_value'].config(text=f"¥{s.get('total_value', 0):,.2f}")
            self.summary_labels['total_assets'].config(text=f"¥{s.get('total_assets', 0):,.2f}")
            # 账户总盈亏 = 当前总资产 - 初始本金 250,000
            p = s.get('account_pnl', 0)
            pp = s.get('account_pnl_pct', 0)
            self.summary_labels['total_pnl'].config(text=f"¥{p:,.2f} ({pp:.2f}%)",
                                                   foreground='red' if p > 0 else 'green' if p < 0 else 'black')

            # 刷新持仓表格
            for i in self.tree.get_children():
                self.tree.delete(i)
            df_pos = self.pm.get_all()
            for _, r in df_pos.iterrows():
                # 保护：pnl/pnl_pct 可能为 NULL（未计算），默认为 0
                pnl = r.get('pnl')
                if pnl is None or (isinstance(pnl, float) and pd.isna(pnl)):
                    pnl = 0.0
                pnl_pct = r.get('pnl_pct')
                if pnl_pct is None or (isinstance(pnl_pct, float) and pd.isna(pnl_pct)):
                    pnl_pct = 0.0
                tag = ('profit',) if pnl > 0 else ('loss',) if pnl < 0 else ()
                sl, tp = r.get('stop_loss_price'), r.get('target_price')
                sl_s = f"{float(sl):.2f}" if sl and not pd.isna(sl) else "-"
                tp_s = f"{float(tp):.2f}" if tp and not pd.isna(tp) else "-"
                cur_p = r.get('current_price')
                cur_p_s = f"{float(cur_p):.3f}" if cur_p and not pd.isna(cur_p) else f"{r['cost_price']:.3f}"
                
                self.tree.insert('', 'end', values=(r['ts_code'], r['name'], r['quantity'], 
                                                   f"{r['cost_price']:.3f}", cur_p_s, 
                                                   sl_s, tp_s, f"{pnl:.2f}", 
                                                   f"{pnl_pct:.2f}%", r['buy_date']), tags=tag)
            self.tree.tag_configure('profit', foreground='red')
            self.tree.tag_configure('loss', foreground='green')

            # 刷新交易流水
            for i in self.log_tree.get_children():
                self.log_tree.delete(i)
            with sqlite3.connect(self.pm.db_path) as conn:
                df_log = pd.read_sql_query("SELECT * FROM trade_log ORDER BY trade_date DESC, id DESC LIMIT 20", conn)
            for _, r in df_log.iterrows():
                name_display = f"💰 {r['name']}" if r['ts_code'] == 'CASH' else r['name']
                self.log_tree.insert('', 'end', values=(r['trade_date'], r['trade_type'], name_display, 
                                                       f"{r['price']:,.2f}", r['quantity'], 
                                                       f"{r['transaction_cost']:.1f}", 
                                                       f"{r['post_balance']:,.2f}", r['notes'] or ""))
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("刷新失败", f"刷新数据时出错：\n{str(e)}\n\n请查看控制台日志获取详细信息。")

    def on_double_click(self):
        sel = self.tree.selection()
        if not sel:
            return
        c = self.tree.item(sel[0])['values'][0]
        df = self.pm.get_all()
        d = df[df['ts_code'] == c].iloc[0]
        SellDialog(self, self.pm, d, self.config, self.refresh_all)

    def show_buy_dialog(self):
        BuyDialog(self, self.pm, self.config, self.refresh_all)

    def show_ledger_dialog(self):
        LedgerDialog(self, self.pm, self.config, self.refresh_all)

    def show_cash_dialog(self):
        CashOpDialog(self, self.pm, self.refresh_all)

class BuyDialog(tk.Toplevel):
    def __init__(self, parent, pm, config, callback):
        super().__init__(parent)
        self.pm = pm
        self.config = config
        self.callback = callback
        self.title("手动建仓")
        self.geometry("500x600")
        self.init_ui()

    def init_ui(self):
        f = ttk.Frame(self, padding=20)
        f.pack(fill='both', expand=True)
        self.ins = {}
        fields = [("代码", "c"), ("名称", "n"), ("数量", "q"), ("单价", "p"), ("止损", "sl"), ("止盈", "tp"), ("日期", "d")]
        for i, (l, k) in enumerate(fields):
            ttk.Label(f, text=l).grid(row=i, column=0, pady=5, sticky='w')
            e = ttk.Entry(f)
            e.grid(row=i, column=1, pady=5, sticky='ew')
            self.ins[k] = e
            if k == 'd':
                e.insert(0, datetime.now().strftime("%Y-%m-%d"))
        
        ttk.Label(f, text="环境").grid(row=7, column=0, pady=5, sticky='w')
        # 获取环境选项，如果不存在则使用默认值
        env_options = self.config.get('gui_settings', {}).get('market_env_options', ["震荡市"])
        self.env = ttk.Combobox(f, values=env_options, state="readonly")
        self.env.grid(row=7, column=1, pady=5, sticky='ew')
        if self.env['values']:
            self.env.current(0)
            
        ttk.Label(f, text="理由").grid(row=8, column=0, pady=5, sticky='nw')
        self.notes = tk.Text(f, height=5)
        self.notes.grid(row=8, column=1, pady=5, sticky='ew')
        
        ttk.Button(f, text="确认存入", command=self.save).grid(row=9, column=0, columnspan=2, pady=20)

    def save(self):
        try:
            self.pm.add_position(self.ins['c'].get(), self.ins['n'].get(), 
                                int(self.ins['q'].get()), float(self.ins['p'].get()), 
                                self.ins['d'].get(), self.notes.get("1.0", "end-1c"), 
                                float(self.ins['sl'].get() or 0), 
                                float(self.ins['tp'].get() or 0), self.env.get())
            self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))

class SellDialog(tk.Toplevel):
    def __init__(self, parent, pm, data, config, callback):
        super().__init__(parent)
        self.pm = pm
        self.data = data
        self.config = config
        self.callback = callback
        self.title(f"卖出/减仓 - {data['name']}")
        self.geometry("400x500")
        self.init_ui()

    def init_ui(self):
        f = ttk.Frame(self, padding=20)
        f.pack(fill='both', expand=True)
        
        # 股票信息展示
        info_f = ttk.LabelFrame(f, text=" 股票信息 ", padding=10)
        info_f.pack(fill='x', pady=5)
        
        ttk.Label(info_f, text=f"代码: {self.data['ts_code']}").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Label(info_f, text=f"名称: {self.data['name']}").grid(row=0, column=1, sticky='w', padx=20, pady=2)
        ttk.Label(info_f, text=f"当前持仓: {self.data['quantity']}").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Label(info_f, text=f"成本价格: {self.data['cost_price']:.3f}").grid(row=1, column=1, sticky='w', padx=20, pady=2)

        # 输入区域
        input_f = ttk.Frame(f, padding=10)
        input_f.pack(fill='both', expand=True, pady=10)
        
        ttk.Label(input_f, text="卖出数量").grid(row=0, column=0, sticky='w', pady=5)
        self.q_in = ttk.Entry(input_f)
        self.q_in.insert(0, str(self.data['quantity']))
        self.q_in.grid(row=0, column=1, sticky='ew', pady=5, padx=5)
        
        ttk.Label(input_f, text="成交单价").grid(row=1, column=0, sticky='w', pady=5)
        self.p_in = ttk.Entry(input_f)
        # 预填现价或成本价
        cur_p = self.data.get('current_price')
        default_p = f"{cur_p:.3f}" if cur_p and not pd.isna(cur_p) else f"{self.data['cost_price']:.3f}"
        self.p_in.insert(0, default_p)
        self.p_in.grid(row=1, column=1, sticky='ew', pady=5, padx=5)
        
        ttk.Label(input_f, text="市场环境").grid(row=2, column=0, sticky='w', pady=5)
        env_options = self.config.get('gui_settings', {}).get('market_env_options', ["震荡市"])
        self.env = ttk.Combobox(input_f, values=env_options, state="readonly")
        self.env.grid(row=2, column=1, sticky='ew', pady=5, padx=5)
        if self.env['values']:
            self.env.current(0)
            
        ttk.Label(input_f, text="卖出备注").grid(row=3, column=0, sticky='nw', pady=5)
        self.notes = tk.Text(input_f, height=5, width=30)
        self.notes.grid(row=3, column=1, sticky='ew', pady=5, padx=5)
        
        btn = ttk.Button(f, text=" 确认执行交易 ", command=self.save)
        btn.pack(pady=10)

    def save(self):
        try:
            qty_str = self.q_in.get().strip()
            price_str = self.p_in.get().strip()
            
            if not qty_str or not price_str:
                messagebox.showwarning("提示", "请输入卖出数量和成交价格")
                return
                
            qty = int(qty_str)
            price = float(price_str)
            
            if qty <= 0:
                messagebox.showwarning("提示", "卖出数量必须大于0")
                return

            result = self.pm.sell_position(self.data['id'], price, qty, 
                                 self.notes.get("1.0", "end-1c"), 
                                 self.env.get())
            if not result:
                messagebox.showerror("错误", "卖出失败：未找到对应的持仓记录\n\n可能原因：\n1. 该股票已不在当前持仓列表中\n2. 持仓数据不一致\n\n请点击'刷新行情/资产'按钮同步数据后重试")
                return
            
            self.callback()
            self.destroy()
        except ValueError:
            messagebox.showerror("错误", "数量必须为整数，价格必须为数字")
        except Exception as e:
            messagebox.showerror("系统错误", f"卖出失败：{str(e)}\n\n请查看控制台日志获取详细信息")
            import traceback; traceback.print_exc()

class CashOpDialog(tk.Toplevel):
    def __init__(self, parent, pm, callback):
        super().__init__(parent)
        self.pm = pm
        self.callback = callback
        self.title("资金存取")
        self.geometry("350x300")
        self.init_ui()

    def init_ui(self):
        f = ttk.Frame(self, padding=20)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text="类型").grid(row=0, column=0, pady=5)
        self.type_cb = ttk.Combobox(f, values=["DEPOSIT", "WITHDRAW"], state="readonly")
        self.type_cb.grid(row=0, column=1, pady=5)
        self.type_cb.current(0)
        ttk.Label(f, text="金额").grid(row=1, column=0, pady=5)
        self.amt_in = ttk.Entry(f)
        self.amt_in.grid(row=1, column=1, pady=5)
        ttk.Label(f, text="日期").grid(row=2, column=0, pady=5)
        self.date_in = ttk.Entry(f)
        self.date_in.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_in.grid(row=2, column=1, pady=5)
        ttk.Label(f, text="备注").grid(row=3, column=0, pady=5)
        self.notes = ttk.Entry(f)
        self.notes.grid(row=3, column=1, pady=5)
        ttk.Button(f, text="确认执行", command=self.save).grid(row=4, column=0, columnspan=2, pady=20)

    def save(self):
        try:
            self.pm.manual_cash_op(float(self.amt_in.get()), self.type_cb.get(), 
                                  self.notes.get(), self.date_in.get())
            self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))

class LedgerDialog(tk.Toplevel):
    def __init__(self, parent, pm, config, callback):
        super().__init__(parent)
        self.pm = pm
        self.config = config
        self.callback = callback
        self.title("历史对账修正")
        self.geometry("1100x650")
        self.init_ui()

    def init_ui(self):
        f = ttk.Frame(self, padding=10)
        f.pack(fill='x')
        ttk.Label(f, text="筛选项目:").pack(side='left')
        self.search = ttk.Entry(f)
        self.search.pack(side='left', padx=5)
        ttk.Button(f, text="查询", command=self.refresh).pack(side='left')
        
        self.tree = ttk.Treeview(self, columns=("id", "d", "t", "n", "p", "q", "f", "b", "env", "r"), show='headings')
        cols = [("id", "ID", 40), ("d", "日期", 90), ("t", "动作", 60), ("n", "项目", 90), 
                ("p", "价格/金额", 90), ("q", "数量", 60), ("f", "费用", 50), ("b", "余额", 90), 
                ("env", "环境", 70), ("r", "备注", 250)]
        for cid, head, w in cols:
            self.tree.heading(cid, text=head)
            self.tree.column(cid, width=w, anchor='center')
        self.tree.column("r", anchor='w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)
        
        btn_f = ttk.Frame(self)
        btn_f.pack(pady=10)
        ttk.Button(btn_f, text="📝 修正选中流水", command=self.edit_selected).pack(side='left', padx=10)
        ttk.Button(btn_f, text="❌ 删除选中流水", command=self.delete_selected).pack(side='left', padx=10)
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        import sqlite3
        with sqlite3.connect(self.pm.db_path) as conn:
            q = "SELECT * FROM trade_log WHERE name LIKE ? ORDER BY trade_date DESC, id DESC"
            df = pd.read_sql_query(q, conn, params=(f"%{self.search.get()}%",))
        for _, r in df.iterrows():
            self.tree.insert('', 'end', values=(r['id'], r['trade_date'], r['trade_type'], r['name'], 
                                               f"{r['price']:,.2f}", r['quantity'], 
                                               f"{r['transaction_cost']:.1f}", 
                                               f"{r['post_balance']:,.2f}", 
                                               r['market_env'] or "-", r['notes'] or ""))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("警告", "删除流水将导致持仓重新计算，确认删除？"):
            return
        lid = self.tree.item(sel[0])['values'][0]
        import sqlite3
        with sqlite3.connect(self.pm.db_path) as conn:
            conn.execute("DELETE FROM trade_log WHERE id = ?", (lid,))
            # 删除后立即重建持仓（基于剩余流水）
            self.pm.rebuild_positions_from_logs()
            conn.commit()
        self.callback()
        self.refresh()

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        lid = self.tree.item(sel[0])['values'][0]
        import sqlite3
        with sqlite3.connect(self.pm.db_path) as conn:
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT * FROM trade_log WHERE id = ?", (lid,)).fetchone()
        
        dlg = tk.Toplevel(self)
        dlg.title(f"修正 ID: {lid}")
        f = ttk.Frame(dlg, padding=20)
        f.pack()
        ins = {}
        fields = [("日期", "trade_date"), ("价格", "price"), ("数量", "quantity"), 
                  ("止损", "stop_loss"), ("止盈", "take_profit")]
        for i, (l, k) in enumerate(fields):
            ttk.Label(f, text=l).grid(row=i, column=0, pady=3)
            e = ttk.Entry(f)
            e.insert(0, str(r[k]) if r[k] is not None else "")
            e.grid(row=i, column=1)
            ins[k] = e
            
        ttk.Label(f, text="理由").grid(row=5, column=0)
        n_t = tk.Text(f, height=4, width=30)
        n_t.insert("1.0", r['notes'] or "")
        n_t.grid(row=5, column=1)
        
        def save():
            try:
                self.pm.edit_trade_log(lid, trade_date=ins['trade_date'].get(), 
                                      price=float(ins['price'].get()), 
                                      quantity=int(ins['quantity'].get()), 
                                      stop_loss=float(ins['stop_loss'].get() or 0), 
                                      take_profit=float(ins['take_profit'].get() or 0), 
                                      notes=n_t.get("1.0", "end-1c"))
                # 编辑流水后，重新计算持仓和余额
                self.pm.rebuild_positions_from_logs()
                self.callback()
                self.refresh()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        ttk.Button(f, text="💾 保存并重算余额", command=save).grid(row=6, column=0, columnspan=2, pady=10)
