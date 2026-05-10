import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import sqlite3
from datetime import datetime
import json
from pathlib import Path
from core.config import config

# 导入主题
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from gui.theme import Colors, Fonts, set_treeview_style


class PositionsTab(tk.Frame):
    def __init__(self, parent, position_manager=None):
        super().__init__(parent, bg=Colors.BG_DARK)
        self.pack(fill='both', expand=True)
        if position_manager is None:
            from core.positions import PositionManager
            self.pm = PositionManager()
        else:
            self.pm = position_manager
        self.config_manager = config
        self.config = self.config_manager.config
        self.stat_card_values = {}  # 存储每个卡片的数值标签 {key: label_widget}
        self._tip_window = None
        self._tip_after = None
        self._last_tip = None
        self._strategy_info = {}  # {tree_iid: {'sl_info': str, 'tp_info': str}}
        self.init_ui()

    def init_ui(self):
        """现代卡片式布局"""
        # 主容器
        main_container = tk.Frame(self, bg=Colors.BG_DARK)
        main_container.pack(fill='both', expand=True)

        # ========== 顶部资产看板 ==========
        stats_container = tk.Frame(main_container, bg=Colors.BG_DARK)
        stats_container.pack(fill=tk.X, padx=15, pady=(15, 10))

        self.stat_cards = {}
        stats = [
            ('cash', '💰', '可用现金', '¥0.00'),
            ('market_value', '📊', '持仓市值', '¥0.00'),
            ('total_assets', '🏦', '总资产', '¥0.00'),
            ('total_pnl', '📈', '总盈亏', '+¥0.00'),
        ]

        for key, icon, title, value in stats:
            card, value_label = self._create_stat_card(
                stats_container, icon, title, value
            )
            self.stat_cards[key] = card
            self.stat_card_values[key] = value_label

        # ========== 快捷操作栏 ==========
        action_bar = tk.Frame(main_container, bg=Colors.BG_CARD, padx=15, pady=10)
        action_bar.pack(fill=tk.X, padx=15, pady=10)

        left_btns = [
            ('🔄 刷新行情', self.refresh_all),
            ('📜 历史账目', self.show_ledger_dialog),
            ('🤖 AI审计报告', self.generate_ai_report),
        ]
        for text, cmd in left_btns:
            btn = tk.Button(action_bar, text=text, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                          font=("Microsoft YaHei", 10), relief=tk.FLAT, padx=15, pady=8,
                          cursor="hand2", command=cmd,
                          highlightthickness=1, highlightbackground=Colors.BORDER)
            btn.pack(side=tk.LEFT, padx=5)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=Colors.PRIMARY_BG, fg=Colors.PRIMARY_DARK))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY))

        right_btns = [
            ('📤 持仓导出', self.export_positions),
            ('💰 资金存取', self.show_cash_dialog),
            ('➕ 手动建仓', self.show_buy_dialog),
        ]
        for text, cmd in right_btns:
            btn = tk.Button(action_bar, text=text, bg=Colors.PRIMARY, fg="white",
                          font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, padx=15, pady=8,
                          cursor="hand2", command=cmd)
            btn.pack(side=tk.RIGHT, padx=5)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=Colors.PRIMARY_DARK))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=Colors.PRIMARY))

        # ========== 主内容区 ==========
        content = tk.Frame(main_container, bg=Colors.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 持仓表格
        pos_frame = tk.LabelFrame(content, text="  📈 当前持仓明细  ",
                                 bg=Colors.BG_DARK, fg=Colors.PRIMARY_DARK,
                                 font=("Microsoft YaHei", 11, "bold"),
                                 padx=10, pady=5)
        pos_frame.pack(fill=tk.BOTH, expand=True)

        tree_frame = tk.Frame(pos_frame, bg=Colors.BG_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.tree = ttk.Treeview(tree_frame, style="Treeview",
                                columns=("c", "n", "q", "cp", "cur", "sl", "tp", "pnl", "pct"),
                                show='headings', height=10)

        cols = [
            ("c", "代码", 90),
            ("n", "名称", 100),
            ("q", "持仓", 70),
            ("cp", "成本", 85),
            ("cur", "现价", 85),
            ("sl", "止损价", 95),
            ("tp", "止盈价", 95),
            ("pnl", "盈亏", 90),
            ("pct", "盈亏%", 80),
        ]

        for cid, head, width in cols:
            self.tree.heading(cid, text=head, anchor=tk.CENTER)
            self.tree.column(cid, width=width, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", lambda e: self.on_double_click())
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind('<Motion>', self._on_tree_motion)
        self.tree.bind('<Leave>', self._on_tree_leave)
        set_treeview_style(self.tree)

        # ========== 交易流水 ==========
        log_frame = tk.LabelFrame(content, text="  📜 最近交易流水  ",
                                 bg=Colors.BG_DARK, fg=Colors.PRIMARY_DARK,
                                 font=("Microsoft YaHei", 11, "bold"),
                                 padx=10, pady=5)
        log_frame.pack(fill=tk.X, pady=10)

        log_inner = tk.Frame(log_frame, bg=Colors.BG_CARD)
        log_inner.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.log_tree = ttk.Treeview(log_inner, style="Treeview",
                                    columns=("d", "t", "n", "p", "q", "f", "b", "r"),
                                    show='headings', height=6)

        l_cols = [
            ("d", "日期", 100),
            ("t", "类型", 60),
            ("n", "项目", 120),
            ("p", "价格", 90),
            ("q", "数量", 70),
            ("f", "费用", 70),
            ("b", "余额", 100),
            ("r", "备注", 180),
        ]

        for cid, head, width in l_cols:
            self.log_tree.heading(cid, text=head, anchor=tk.CENTER)
            self.log_tree.column(cid, width=width, anchor=tk.CENTER)

        log_scroll = ttk.Scrollbar(log_inner, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscroll=log_scroll.set)
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击流水查看详情
        self.log_tree.bind("<Double-1>", lambda e: self.on_log_double_click())

        self.refresh_all()

    def _create_stat_card(self, parent, icon, title, value):
        """创建统计卡片，返回 (card_frame, value_label)"""
        card = tk.Frame(parent, bg=Colors.BG_CARD, relief=tk.FLAT, bd=1,
                       highlightbackground=Colors.BORDER,
                       width=180, height=90)

        # 图标
        icon_lbl = tk.Label(card, text=icon, bg=Colors.BG_CARD, fg=Colors.PRIMARY,
                           font=("Arial", 20), anchor=tk.W, padx=15, pady=10)
        icon_lbl.pack(anchor=tk.W)

        # 标题
        tk.Label(card, text=title, bg=Colors.BG_CARD, fg=Colors.TEXT_MUTED,
                font=("Microsoft YaHei", 9), anchor=tk.W, padx=15).pack(anchor=tk.W, pady=(5, 0))

        # 数值
        value_lbl = tk.Label(card, text=value, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                            font=("Arial", 16, "bold"), anchor=tk.W, padx=15)
        value_lbl.pack(anchor=tk.W)

        # 先 pack card 以激活布局
        card.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        card.update_idletasks()  # 强制刷新布局

        return card, value_lbl

    def _update_card_value(self, key, value, is_positive=True):
        """直接更新数值标签"""
        if key not in self.stat_card_values:
            return
        label = self.stat_card_values[key]
        if key == 'total_pnl':
            color = Colors.ACCENT_RED if is_positive else Colors.ACCENT_GREEN
            label.configure(text=value, fg=color)
        else:
            label.configure(text=value, fg=Colors.TEXT_PRIMARY)

    def on_log_double_click(self):
        """双击交易流水查看详情"""
        sel = self.log_tree.selection()
        if not sel:
            return
        values = self.log_tree.item(sel[0])['values']
        if not values:
            return

        # values: 日期, 类型, 项目, 价格, 数量, 费用, 余额, 备注
        date, trade_type, name, price, qty, fee, balance, notes = values

        # 查询完整信息
        import sqlite3
        with sqlite3.connect(self.pm.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trade_log WHERE trade_date=? AND trade_type=? AND name=? LIMIT 1",
                (date, trade_type, name.replace('💰 ', '') if name.startswith('💰') else name)
            ).fetchall()
            row = rows[0] if rows else None

        if not row:
            # 尝试用日期模糊匹配
            rows = conn.execute(
                "SELECT * FROM trade_log WHERE trade_date=? LIMIT 1", (date,)
            ).fetchall()
            row = rows[0] if rows else None

        detail_text = f"""━━━━━━━━━━━━━━━━━━━━━━
📅 日期: {date}
📋 类型: {trade_type}
📛 名称: {name}
💵 价格/金额: {price}
🔢 数量: {qty}
💰 费用: {fee}
🏦 余额: {balance}
📝 备注: {notes if notes else '(无)'}"""

        if row:
            detail_text += f"""
━━━━━━━━━━━━━━━━━━━━━━
🆔 记录ID: {row['id']}
🏷️ 市场环境: {row.get('market_env') or '(无)'}
🎯 止损设置: {row.get('stop_loss') or '(无)'}
🎯 止盈设置: {row.get('take_profit') or '(无)'}"""

        dlg = tk.Toplevel(self)
        dlg.title(f"📜 交易详情 - {name}")
        dlg.geometry("480x380")
        dlg.configure(bg=Colors.BG_DARK)
        dlg.transient(self)
        dlg.grab_set()

        info_frame = tk.Frame(dlg, bg=Colors.BG_CARD, padx=20, pady=15)
        info_frame.pack(fill='both', expand=True, padx=15, pady=15)

        tk.Label(info_frame, text=f"📜 {name} 交易详情", bg=Colors.BG_CARD,
                fg=Colors.PRIMARY_DARK, font=("Microsoft YaHei", 13, "bold"),
                anchor='w').pack(anchor='w', pady=(0, 15))

        # 交易类型标签
        type_color = Colors.ACCENT_GREEN if trade_type == 'BUY' else Colors.ACCENT_RED if trade_type == 'SELL' else Colors.TEXT_SECONDARY
        type_label = tk.Label(info_frame, text=f"【{trade_type}】", bg=Colors.BG_CARD,
                            fg=type_color, font=("Microsoft YaHei", 11, "bold"))
        type_label.pack(anchor='w', pady=(0, 10))

        # 信息行
        info_rows = [
            ("📅 日期", str(date)),
            ("💵 价格/金额", str(price)),
            ("🔢 数量", str(qty)),
            ("💰 手续费", str(fee)),
            ("🏦 账户余额", str(balance)),
            ("🏷️ 市场环境", str(row.get('market_env')) if row else '(无)'),
            ("🎯 止损价", str(row.get('stop_loss')) if row else '(无)'),
            ("🎯 止盈价", str(row.get('take_profit')) if row else '(无)'),
        ]

        for label_text, value_text in info_rows:
            row_frame = tk.Frame(info_frame, bg=Colors.BG_CARD)
            row_frame.pack(fill='x', pady=3)
            tk.Label(row_frame, text=label_text, bg=Colors.BG_CARD,
                    fg=Colors.TEXT_SECONDARY, font=("Microsoft YaHei", 10),
                    width=10, anchor='w').pack(side='left')
            val = value_text if value_text and value_text != 'None' else '(无)'
            tk.Label(row_frame, text=val, bg=Colors.BG_CARD,
                    fg=Colors.TEXT_PRIMARY, font=("Microsoft YaHei", 10),
                    anchor='w').pack(side='left')

        # 备注区
        tk.Label(info_frame, text="📝 备注:", bg=Colors.BG_CARD,
                fg=Colors.TEXT_SECONDARY, font=("Microsoft YaHei", 10),
                anchor='w').pack(anchor='w', pady=(10, 2))
        notes_content = notes if notes else '(无备注)'
        notes_label = tk.Label(info_frame, text=notes_content, bg=Colors.BG_CARD,
                             fg=Colors.TEXT_PRIMARY, font=("Microsoft YaHei", 10),
                             anchor='w', justify='left', wraplength=400)
        notes_label.pack(anchor='w', fill='x')

        # 关闭按钮
        tk.Button(dlg, text="✕ 关闭", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), relief=tk.FLAT, padx=20, pady=6,
                command=dlg.destroy).pack(pady=(10, 0))

    def on_right_click(self, event):
        """右键菜单（持仓表格）"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu = tk.Menu(self, tearoff=0)
            values = self.tree.item(item, 'values')
            from gui.utils import generate_stock_report
            menu.add_command(label="📊 生成深度财务报告",
                          command=lambda: generate_stock_report(self, values[0], values[1]))
            menu.add_command(label="📋 复制代码",
                          command=lambda: self.copy_to_clipboard(values[0]))
            menu.add_separator()
            menu.add_command(label="🎯 修改止盈止损策略",
                          command=self.show_stop_loss_dialog)
            menu.add_command(label="📉 卖出/减仓",
                          command=self.on_double_click)
            menu.add_separator()
            menu.add_command(label="📈 K线图",
                          command=lambda: self._show_stock_chart(values[0], values[1]))
            menu.post(event.x_root, event.y_root)

    def _show_stock_chart(self, ts_code, name):
        """显示K线图"""
        from gui.stock_chart import show_stock_chart
        show_stock_chart(self, ts_code, name)

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
        """检查 positions 与 trade_log 一致性，不一致时自动重建"""
        import sqlite3
        from pathlib import Path
        db_path = Path(self.pm.db_path)
        if not db_path.exists():
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        code_map = {}
        try:
            cursor.execute("SELECT symbol, ts_code FROM stocks_basic")
            for row in cursor.fetchall():
                code_map[str(row[0])] = row[1]
        except:
            pass
        cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
        codes = [r[0] for r in cursor.fetchall()]
        mismatches = []
        for code in codes:
            cursor.execute(
                "SELECT trade_type, quantity FROM trade_log WHERE ts_code = ? ORDER BY trade_date ASC, id ASC",
                (code,))
            trades = cursor.fetchall()
            net_qty = sum(q if t == 'BUY' else -q for t, q in trades)
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
            print(f"⚠️  发现 {len(mismatches)} 条持仓不一致，正在重建...")
            self.pm.rebuild_positions_from_logs()

    def clean_abnormal_trades(self):
        """清理异常交易"""
        import sqlite3
        conn = sqlite3.connect(self.pm.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
        codes = [r[0] for r in cursor.fetchall()]
        abnormal_ids = []
        for code in codes:
            cursor.execute(
                "SELECT id, trade_type, quantity FROM trade_log WHERE ts_code = ? ORDER BY trade_date ASC, id ASC",
                (code,))
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
        if abnormal_ids:
            for lid in abnormal_ids:
                conn.execute("DELETE FROM trade_log WHERE id = ?", (lid,))
            conn.commit()
            print(f"🗑️  已清理 {len(abnormal_ids)} 条异常流水")
        conn.close()

    def refresh_all(self):
        """刷新所有数据"""
        import traceback
        try:
            self.check_and_fix_positions()

            # 同步行情现价
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

            # 更新资产看板
            cash = s.get('cash', 0)
            market_val = s.get('total_value', 0)
            total_assets = s.get('total_assets', 0)
            pnl = s.get('account_pnl', 0)
            pnl_pct = s.get('account_pnl_pct', 0)

            self._update_card_value('cash', f"¥{cash:,.2f}")
            self._update_card_value('market_value', f"¥{market_val:,.2f}")
            self._update_card_value('total_assets', f"¥{total_assets:,.2f}")
            pnl_text = f"{'+' if pnl >= 0 else ''}¥{pnl:,.2f} ({pnl_pct:+.2f}%)"
            self._update_card_value('total_pnl', pnl_text, is_positive=(pnl >= 0))

            # 刷新持仓表格
            for i in self.tree.get_children():
                self.tree.delete(i)
            self._strategy_info.clear()
            df_pos = self.pm.get_all()
            for _, r in df_pos.iterrows():
                pnl_val = r.get('pnl')
                if pnl_val is None or (isinstance(pnl_val, float) and pd.isna(pnl_val)):
                    pnl_val = 0.0
                pnl_pct_val = r.get('pnl_pct')
                if pnl_pct_val is None or (isinstance(pnl_pct_val, float) and pd.isna(pnl_pct_val)):
                    pnl_pct_val = 0.0
                tag = ('profit',) if pnl_val > 0 else ('loss',) if pnl_val < 0 else ()

                # 止损止盈 - 计算触发价格（与 StopLossProfitManager 保持一致）
                sl_type = r.get('stop_loss_type', 'fixed')
                tp_type = r.get('profit_exit_type', 'trailing')
                cost = r['cost_price']
                highest = r.get('highest_since_buy', 0) or cost
                if isinstance(highest, float) and pd.isna(highest):
                    highest = cost

                # 止损触发价
                sl_price = None
                if sl_type == 'fixed':
                    sl_price = cost * (1 - float(r.get('stop_loss_value', 0.08)))
                elif sl_type == 'trailing':
                    sl_price = highest * (1 - float(r.get('stop_loss_value', 0.20)))
                    if r.get('trailing_mode', 'strict') == 'loose':
                        sl_price -= highest * 0.02
                elif sl_type == 'breakeven':
                    activate = float(r.get('breakeven_activate', 0.10))
                    if highest >= cost * (1 + activate):
                        sl_price = cost
                    else:
                        sl_price = cost * (1 - float(r.get('stop_loss_value', 0.08)))

                # 止盈触发价
                tp_price = None
                if tp_type == 'target':
                    tp_raw = r.get('target_price')
                    if tp_raw is not None and not pd.isna(tp_raw):
                        tp_price = float(tp_raw)
                elif tp_type == 'trailing':
                    tp_price = highest * (1 - float(r.get('profit_exit_value', 0.15)))
                elif tp_type == 'scale':
                    s1 = float(r.get('scale_profit_1', 0.20))
                    s2 = float(r.get('scale_profit_2', 0.40))
                    tp_display = f"+{s1*100:.0f}/{s2*100:.0f}/{float(r.get('scale_profit_3', 0.60))*100:.0f}%"

                if tp_type != 'scale':
                    tp_display = f"{tp_price:.3f}" if tp_price is not None else \
                        {'target': '目标', 'trailing': '移动', 'scale': '分批'}.get(tp_type, tp_type)
                sl_display = f"{sl_price:.3f}" if sl_price is not None else \
                    {'fixed': '固定', 'trailing': '移动', 'breakeven': '保本'}.get(sl_type, sl_type)

                cur_p = r.get('current_price')
                cur_p_s = f"{float(cur_p):.3f}" if cur_p and not pd.isna(cur_p) else f"{r['cost_price']:.3f}"

                iid = self.tree.insert('', 'end', values=(
                    r['ts_code'], r['name'], int(r['quantity']),
                    f"{r['cost_price']:.3f}", cur_p_s,
                    sl_display, tp_display,
                    f"{pnl_val:,.2f}", f"{pnl_pct_val:+.2f}%"
                ), tags=tag)

                # 存储策略信息供 tooltip 使用
                self._strategy_info[iid] = self._make_strategy_info(r)

            self.tree.tag_configure('profit', foreground=Colors.ACCENT_RED)
            self.tree.tag_configure('loss', foreground=Colors.ACCENT_GREEN)

            # 刷新交易流水
            for i in self.log_tree.get_children():
                self.log_tree.delete(i)
            with sqlite3.connect(self.pm.db_path) as conn:
                df_log = pd.read_sql_query(
                    "SELECT * FROM trade_log ORDER BY trade_date DESC, id DESC LIMIT 20", conn)
            for _, r in df_log.iterrows():
                name_display = f"💰 {r['name']}" if r['ts_code'] == 'CASH' else r['name']
                self.log_tree.insert('', 'end', values=(
                    r['trade_date'], r['trade_type'], name_display,
                    f"{r['price']:,.2f}", r['quantity'],
                    f"{r['transaction_cost']:.1f}",
                    f"{r['post_balance']:,.2f}",
                    (r.get('notes') or '')[:30]
                ))

        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("刷新失败", f"刷新数据时出错：\n{str(e)}")

    def on_double_click(self):
        """双击卖出"""
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

    def show_stop_loss_dialog(self):
        """显示止盈止损策略修改对话框"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要修改的持仓")
            return
        c = self.tree.item(sel[0])['values'][0]
        df = self.pm.get_all()
        if c not in df['ts_code'].values:
            messagebox.showwarning("提示", "未找到该持仓")
            return
        d = df[df['ts_code'] == c].iloc[0]
        StopLossProfitDialog(self, self.pm, d, self.refresh_all)

    def export_positions(self):
        """导出持仓到JSON文件"""
        from tkinter import filedialog
        import json
        from pathlib import Path
        last_dir = self.config.get('LAST_EXPORT_DIR', str(Path.home()))
        last_file = self.config.get('LAST_EXPORT_FILE', '持仓情况.json')
        file_path = filedialog.asksaveasfilename(
            title='导出持仓JSON文件',
            initialdir=last_dir,
            initialfile=last_file,
            defaultextension='.json',
            filetypes=[('JSON文件', '*.json'), ('所有文件', '*.*')]
        )
        if not file_path:
            return
        try:
            df_pos = self.pm.get_all()
            if df_pos.empty:
                messagebox.showwarning("提示", "当前无持仓，无需导出")
                return
            holdings = []
            for _, r in df_pos.iterrows():
                holdings.append({
                    'ts_code': r['ts_code'],
                    'name': r['name'],
                    'quantity': int(r['quantity']),
                    'cost_price': float(r['cost_price']),
                    'current_price': float(r.get('current_price') or r['cost_price']),
                    'pnl': float(r.get('pnl') or 0),
                    'pnl_pct': float(r.get('pnl_pct') or 0),
                    'buy_date': r.get('buy_date', '')
                })
            export_data = {
                'holdings': holdings,
                'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'LW_Stock_system'
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            self.config['LAST_EXPORT_DIR'] = str(Path(file_path).parent)
            self.config['LAST_EXPORT_FILE'] = str(Path(file_path).name)
            messagebox.showinfo("成功", f"持仓已导出到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    # ========== Tooltip 策略信息提示 ==========

    def _make_strategy_info(self, r):
        """构建策略信息文本（供 tooltip 使用）"""
        cost = r['cost_price']
        sl_type = r.get('stop_loss_type', 'fixed')
        sl_value = r.get('stop_loss_value', 0.08)
        highest = r.get('highest_since_buy', 0) or cost
        if isinstance(highest, float) and pd.isna(highest):
            highest = cost
        trailing_mode = r.get('trailing_mode', 'strict')

        sl_lines = []
        sl_names = {'fixed': '固定比例止损', 'trailing': '移动止损', 'breakeven': '保本止损'}
        sl_lines.append(f"类型: {sl_names.get(sl_type, sl_type)}({sl_type})")
        if sl_type == 'fixed':
            trigger = cost * (1 - sl_value)
            sl_lines.append(f"止损比例: {sl_value*100:.0f}%")
            sl_lines.append(f"触发价: {trigger:.3f} (成本 {cost:.3f})")
        elif sl_type == 'trailing':
            trigger = highest * (1 - sl_value)
            if trailing_mode == 'loose':
                trigger -= highest * 0.02
            sl_lines.append(f"回落比例: {sl_value*100:.0f}%")
            tm_names = {'strict': '严格-回落即触发', 'loose': '宽松-额外2%容忍'}
            sl_lines.append(f"模式: {tm_names.get(trailing_mode, trailing_mode)}")
            sl_lines.append(f"触发价: {trigger:.3f}")
            sl_lines.append(f"跟踪最高价: {highest:.3f}")
        elif sl_type == 'breakeven':
            activate = float(r.get('breakeven_activate', 0.10))
            sl_lines.append(f"初始止损: {sl_value*100:.0f}% 即 {cost*(1-sl_value):.3f}")
            sl_lines.append(f"激活条件: 涨{activate*100:.0f}% 即 {cost*(1+activate):.3f}")
            if highest >= cost * (1 + activate):
                sl_lines.append(f"状态: ✅ 已激活 保本价 {cost:.3f}")
            else:
                sl_lines.append(f"状态: ⏳ 未激活 当前止损 {cost*(1-sl_value):.3f}")

        tp_type = r.get('profit_exit_type', 'trailing')
        tp_value = r.get('profit_exit_value', 0.15)
        tp_target = r.get('target_price')

        tp_lines = []
        tp_names = {'target': '目标价止盈', 'trailing': '移动止盈', 'scale': '分批止盈'}
        tp_lines.append(f"类型: {tp_names.get(tp_type, tp_type)}({tp_type})")
        if tp_type == 'target':
            if tp_target is not None and not pd.isna(tp_target):
                tp_lines.append(f"目标价: {tp_target:.3f}")
            else:
                tp_lines.append("目标价: 未设置")
        elif tp_type == 'trailing':
            trigger = highest * (1 - tp_value)
            tp_lines.append(f"回落比例: {tp_value*100:.0f}%")
            tp_lines.append(f"触发价: {trigger:.3f}")
            tp_lines.append(f"跟踪最高价: {highest:.3f}")
        elif tp_type == 'scale':
            s1 = float(r.get('scale_profit_1', 0.20))
            s2 = float(r.get('scale_profit_2', 0.40))
            s3 = float(r.get('scale_profit_3', 0.60))
            r1 = float(r.get('scale_ratio_1', 0.33))
            r2 = float(r.get('scale_ratio_2', 0.33))
            profit_pct = (r.get('current_price', 0) or cost - cost) / cost if cost > 0 else 0
            tp_lines.append(f"第1批: +{s1*100:.0f}% ({cost*(1+s1):.3f}) 卖{r1*100:.0f}%")
            tp_lines.append(f"第2批: +{s2*100:.0f}% ({cost*(1+s2):.3f}) 卖{r2*100:.0f}%")
            tp_lines.append(f"第3批: +{s3*100:.0f}% 高点回落8%清仓")

        return {'sl': '\n'.join(sl_lines), 'tp': '\n'.join(tp_lines)}

    def _on_tree_motion(self, event):
        """鼠标悬停时延迟显示策略 tooltip"""
        col = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        cell = (item, col)

        if cell == self._last_tip and self._tip_window:
            return
        self._hide_strategy_tip()
        self._last_tip = cell

        if col not in ('#6', '#7') or not item or item not in self._strategy_info:
            return

        key = 'sl' if col == '#6' else 'tp'
        prefix = '🛑 止损策略' if col == '#6' else '🎯 止盈策略'
        text = f"{prefix}\n{'-'*20}\n{self._strategy_info[item][key]}"

        self._tip_after = self.after(400, lambda t=text: self._show_strategy_tip(t))

    def _show_strategy_tip(self, text):
        """显示 tooltip 弹出窗口"""
        self._hide_strategy_tip()
        x = self.winfo_pointerx() + 15
        y = self.winfo_pointery() + 10
        self._tip_window = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes('-topmost', True)
        frame = tk.Frame(tw, bg='#FFFFCC', relief=tk.SOLID, borderwidth=1)
        frame.pack()
        tk.Label(frame, text=text, justify=tk.LEFT,
                bg='#FFFFCC', fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 9), padx=8, pady=6).pack()

    def _on_tree_leave(self, event=None):
        """鼠标离开树状表格时隐藏 tooltip"""
        self._last_tip = None
        self._hide_strategy_tip()

    def _hide_strategy_tip(self):
        """隐藏 tooltip"""
        if self._tip_after:
            self.after_cancel(self._tip_after)
            self._tip_after = None
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


# ==================== 对话框类 ====================

class BuyDialog(tk.Toplevel):
    def __init__(self, parent, pm, config, callback):
        super().__init__(parent)
        self.pm = pm
        self.config = config
        self.callback = callback
        self.title("➕ 买入建仓")
        self.geometry("450x500")
        self.configure(bg=Colors.BG_DARK)
        self.transient(parent)
        self.grab_set()
        self.init_ui()

    def init_ui(self):
        f = tk.Frame(self, bg=Colors.BG_DARK, padx=20, pady=15)
        f.pack(fill='both', expand=True)

        tk.Label(f, text="📈 买入建仓", bg=Colors.BG_DARK, fg=Colors.PRIMARY_DARK,
                font=("Microsoft YaHei", 14, "bold")).pack(anchor=tk.W, pady=15)

        fields = [
            ("股票代码:", "ts_code"),
            ("股票名称:", "name"),
            ("买入数量:", "quantity"),
            ("成交价格:", "price"),
            ("市场环境:", "market_env"),
        ]

        self.inputs = {}
        for label, key in fields:
            row = tk.Frame(f, bg=Colors.BG_DARK)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text=label, bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                    font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
            entry = tk.Entry(row, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                           insertbackground=Colors.TEXT_PRIMARY, width=25)
            entry.pack(side=tk.LEFT, padx=(0, 5))
            self.inputs[key] = entry

        tk.Label(f, text="备注:", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W, pady=10)
        self.inputs['notes'] = tk.Text(f, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                                      height=4, width=40, insertbackground=Colors.TEXT_PRIMARY)
        self.inputs['notes'].pack(pady=5)

        btn_frame = tk.Frame(f, bg=Colors.BG_DARK)
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="✓ 确认买入", bg=Colors.PRIMARY, fg="white",
                 font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, padx=20, pady=8,
                 command=self.save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="✕ 取消", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                 font=("Microsoft YaHei", 10), relief=tk.FLAT, padx=20, pady=8,
                 command=self.destroy).pack(side=tk.LEFT, padx=5)

    def save(self):
        try:
            ts_code = self.inputs['ts_code'].get().strip()
            name = self.inputs['name'].get().strip()
            quantity = int(self.inputs['quantity'].get())
            price = float(self.inputs['price'].get())
            market_env = self.inputs['market_env'].get().strip()
            notes = self.inputs['notes'].get("1.0", "end-1c").strip()

            if not ts_code:
                messagebox.showerror("错误", "股票代码不能为空")
                return

            self.pm.add_position(ts_code, name, quantity, price, sl=None, tp=None,
                               notes=f"{notes} [环境:{market_env}]" if market_env else notes)
            self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))


class SellDialog(tk.Toplevel):
    def __init__(self, parent, pm, pos_data, config, callback):
        super().__init__(parent)
        self.pm = pm
        self.data = pos_data
        self.config = config
        self.callback = callback
        self.title(f"📉 卖出 - {pos_data['name']}")
        self.geometry("420x480")
        self.configure(bg=Colors.BG_DARK)
        self.transient(parent)
        self.grab_set()
        self.init_ui()

    def init_ui(self):
        f = tk.Frame(self, bg=Colors.BG_DARK, padx=20, pady=15)
        f.pack(fill='both', expand=True)

        tk.Label(f, text=f"📉 卖出 - {self.data['name']}",
                bg=Colors.BG_DARK, fg=Colors.ACCENT_RED,
                font=("Microsoft YaHei", 13, "bold")).pack(anchor=tk.W, pady=10)

        info = tk.Frame(f, bg=Colors.BG_CARD, padx=15, pady=10)
        info.pack(fill=tk.X, pady=15)
        tk.Label(info, text=f"代码: {self.data['ts_code']}", bg=Colors.BG_CARD,
               fg=Colors.TEXT_PRIMARY, font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W)
        tk.Label(info, text=f"持仓: {self.data['quantity']}股", bg=Colors.BG_CARD,
               fg=Colors.TEXT_PRIMARY, font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W)
        tk.Label(info, text=f"成本: {self.data['cost_price']:.3f}元", bg=Colors.BG_CARD,
               fg=Colors.TEXT_PRIMARY, font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W)

        input_f = tk.Frame(f, bg=Colors.BG_DARK)
        input_f.pack(fill='both', expand=True)

        rows = [
            ("卖出数量", "quantity", self.data['quantity']),
            ("成交单价", "price", ""),
            ("市场环境", "market_env", ""),
        ]
        self.q_in = None
        for label_text, key, default in rows:
            row = tk.Frame(input_f, bg=Colors.BG_DARK)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text=label_text, bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                    font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
            entry = tk.Entry(row, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                           insertbackground=Colors.TEXT_PRIMARY, width=20)
            if default:
                entry.insert(0, str(default))
            entry.pack(side=tk.LEFT)
            if key == 'quantity':
                self.q_in = entry
            setattr(self, f'{key}_in', entry)

        tk.Label(input_f, text="备注:", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W, pady=10)
        self.notes = tk.Text(input_f, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                           height=4, width=38, insertbackground=Colors.TEXT_PRIMARY)
        self.notes.pack(pady=5)

        btn = tk.Frame(f, bg=Colors.BG_DARK)
        btn.pack(pady=15)
        tk.Button(btn, text="✓ 确认卖出", bg=Colors.ACCENT_RED, fg="white",
                 font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, padx=20, pady=8,
                 command=self.save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn, text="✕ 取消", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                 font=("Microsoft YaHei", 10), relief=tk.FLAT, padx=20, pady=8,
                 command=self.destroy).pack(side=tk.LEFT, padx=5)

    def save(self):
        try:
            q = int(self.q_in.get())
            p = float(self.price_in.get())
            env = self.market_env_in.get().strip()
            notes = self.notes.get("1.0", "end-1c").strip()
            ok = self.pm.sell_position(self.data['id'], p, q,
                                     notes=f"{notes} [环境:{env}]" if env else notes)
            if ok:
                self.callback()
                self.destroy()
            else:
                messagebox.showerror("错误", "卖出失败")
        except Exception as e:
            messagebox.showerror("错误", str(e))


class LedgerDialog(tk.Toplevel):
    def __init__(self, parent, pm, config, callback):
        super().__init__(parent)
        self.pm = pm
        self.config = config
        self.callback = callback
        self.title("📜 历史账目修正")
        self.geometry("900x500")
        self.configure(bg=Colors.BG_DARK)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        f = tk.Frame(self, bg=Colors.BG_DARK, padx=15, pady=10)
        f.pack(fill='both', expand=True)

        tk.Label(f, text="📜 历史账目流水", bg=Colors.BG_DARK, fg=Colors.PRIMARY_DARK,
                font=("Microsoft YaHei", 12, "bold")).pack(anchor=tk.W, pady=10)

        search_row = tk.Frame(f, bg=Colors.BG_DARK)
        search_row.pack(fill=tk.X, pady=10)
        tk.Label(search_row, text="搜索:", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        self.search = tk.Entry(search_row, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                              insertbackground=Colors.TEXT_PRIMARY, width=20)
        self.search.pack(side=tk.LEFT, padx=5)
        self.search.bind('<KeyRelease>', lambda e: self.refresh())
        tk.Button(search_row, text="🔍 搜索", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                 relief=tk.FLAT, padx=10, command=self.refresh).pack(side=tk.LEFT)

        tree_frame = tk.Frame(f, bg=Colors.BG_CARD)
        tree_frame.pack(fill='both', expand=True)

        cols = [("id", "ID", 50), ("d", "日期", 90), ("t", "类型", 60),
                ("n", "项目", 100), ("p", "价格", 90), ("q", "数量", 60),
                ("f", "费用", 60), ("b", "余额", 100), ("e", "环境", 80), ("r", "备注", 200)]
        self.tree = ttk.Treeview(tree_frame, style="Treeview", columns=[c[0] for c in cols],
                               show='headings', height=12)
        for cid, head, width in cols:
            self.tree.heading(cid, text=head, anchor=tk.CENTER)
            self.tree.column(cid, width=width, anchor=tk.CENTER)
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scroll.set)
        self.tree.pack(side=tk.LEFT, fill='both', expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda e: self.on_double_click())

        btn_f = tk.Frame(f, bg=Colors.BG_DARK, pady=10)
        btn_f.pack(pady=5)
        tk.Button(btn_f, text="📝 修正选中流水", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                 relief=tk.FLAT, padx=15, command=self.edit_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="❌ 删除选中流水", bg=Colors.ACCENT_RED, fg="white",
                 relief=tk.FLAT, padx=15, command=self.delete_selected).pack(side=tk.LEFT, padx=5)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        with sqlite3.connect(self.pm.db_path) as conn:
            q = "SELECT * FROM trade_log WHERE name LIKE ? ORDER BY trade_date DESC, id DESC"
            df = pd.read_sql_query(q, conn, params=(f"%{self.search.get()}%",))
        for _, r in df.iterrows():
            self.tree.insert('', 'end', values=(
                r['id'], r['trade_date'], r['trade_type'], r['name'],
                f"{r['price']:,.2f}", r['quantity'],
                f"{r['transaction_cost']:.1f}",
                f"{r['post_balance']:,.2f}",
                r.get('market_env') or "-",
                r.get('notes') or ""
            ))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("警告", "删除流水将导致持仓重新计算，确认删除？"):
            return
        lid = self.tree.item(sel[0])['values'][0]
        with sqlite3.connect(self.pm.db_path) as conn:
            conn.execute("DELETE FROM trade_log WHERE id = ?", (lid,))
            self.pm.rebuild_positions_from_logs()
            conn.commit()
        self.callback()
        self.refresh()

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        lid = self.tree.item(sel[0])['values'][0]
        with sqlite3.connect(self.pm.db_path) as conn:
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT * FROM trade_log WHERE id = ?", (lid,)).fetchone()
        dlg = tk.Toplevel(self)
        dlg.title(f"修正 ID: {lid}")
        dlg.configure(bg=Colors.BG_DARK)
        f = tk.Frame(dlg, bg=Colors.BG_DARK, padx=20, pady=15)
        f.pack()
        ins = {}
        fields = [("日期", "trade_date"), ("价格", "price"), ("数量", "quantity"),
                  ("止损", "stop_loss"), ("止盈", "take_profit")]
        for i, (l, k) in enumerate(fields):
            row = tk.Frame(f, bg=Colors.BG_DARK)
            row.grid(row=i, column=0, pady=3, sticky='w')
            tk.Label(row, text=l, bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                    font=("Microsoft YaHei", 10), width=8).pack(side=tk.LEFT)
            e = tk.Entry(row, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                        insertbackground=Colors.TEXT_PRIMARY, width=20)
            e.insert(0, str(r[k]) if r[k] is not None else "")
            e.pack(side=tk.LEFT)
            ins[k] = e
        tk.Label(f, text="理由", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10)).grid(row=5, column=0, sticky='w', pady=5)
        n_t = tk.Text(f, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY, height=4, width=30,
                      insertbackground=Colors.TEXT_PRIMARY)
        n_t.insert("1.0", r['notes'] or "")
        n_t.grid(row=5, column=1, pady=5, padx=5)

        def save():
            try:
                self.pm.edit_trade_log(lid,
                    trade_date=ins['trade_date'].get(),
                    price=float(ins['price'].get()),
                    quantity=int(ins['quantity'].get()),
                    stop_loss=float(ins['stop_loss'].get() or 0),
                    take_profit=float(ins['take_profit'].get() or 0),
                    notes=n_t.get("1.0", "end-1c"))
                self.pm.rebuild_positions_from_logs()
                self.callback()
                self.refresh()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        tk.Button(f, text="💾 保存并重算余额", bg=Colors.PRIMARY, fg="white",
                 font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, padx=15, pady=8,
                 command=save).grid(row=6, column=0, columnspan=2, pady=15)


class CashOpDialog(tk.Toplevel):
    def __init__(self, parent, pm, callback):
        super().__init__(parent)
        self.pm = pm
        self.callback = callback
        self.title("💰 外部资金存取")
        self.geometry("380x280")
        self.configure(bg=Colors.BG_DARK)
        self.init_ui()

    def init_ui(self):
        f = tk.Frame(self, bg=Colors.BG_DARK, padx=20, pady=15)
        f.pack(fill='both', expand=True)

        tk.Label(f, text="💰 外部资金存取", bg=Colors.BG_DARK, fg=Colors.PRIMARY_DARK,
                font=("Microsoft YaHei", 13, "bold")).pack(anchor=tk.W, pady=15)

        tk.Label(f, text="操作类型:", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        self.type_var = tk.StringVar(value='DEPOSIT')
        type_frame = tk.Frame(f, bg=Colors.BG_DARK)
        type_frame.pack(pady=5)
        tk.Radiobutton(type_frame, text="💵 入金", variable=self.type_var, value='DEPOSIT',
                      bg=Colors.BG_DARK, fg=Colors.ACCENT_GREEN, selectcolor=Colors.BG_CARD,
                      command=self.update_color).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(type_frame, text="💸 出金", variable=self.type_var, value='WITHDRAW',
                      bg=Colors.BG_DARK, fg=Colors.ACCENT_RED, selectcolor=Colors.BG_CARD,
                      command=self.update_color).pack(side=tk.LEFT, padx=10)

        tk.Label(f, text="金额:", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W, pady=10)
        self.amt_in = tk.Entry(f, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                               insertbackground=Colors.TEXT_PRIMARY, width=25)
        self.amt_in.pack(pady=5)

        tk.Label(f, text="备注:", bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), anchor=tk.W).pack(anchor=tk.W)
        self.notes = tk.Entry(f, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                              insertbackground=Colors.TEXT_PRIMARY, width=25)
        self.notes.pack(pady=5)

        btn_frame = tk.Frame(f, bg=Colors.BG_DARK)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="✓ 确认执行", bg=Colors.PRIMARY, fg="white",
                 font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, padx=20, pady=8,
                 command=self.save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="✕ 取消", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                 font=("Microsoft YaHei", 10), relief=tk.FLAT, padx=20, pady=8,
                 command=self.destroy).pack(side=tk.LEFT, padx=5)

    def update_color(self):
        pass

    def save(self):
        try:
            amt = float(self.amt_in.get())
            op_type = self.type_var.get()
            notes = self.notes.get().strip()
            self.pm.manual_cash_op(amt, op_type, notes)
            self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))


class StopLossProfitDialog(tk.Toplevel):
    """止盈止损策略配置对话框（v2）"""
    STOP_LOSS_TYPES = ['fixed', 'trailing', 'breakeven']
    PROFIT_TYPES = ['target', 'trailing', 'scale']
    TRAILING_MODES = ['strict', 'loose']

    def __init__(self, parent, pm, pos_data, callback):
        super().__init__(parent)
        self.pm = pm
        self.pos_data = pos_data
        self.callback = callback
        self.title(f"🎯 止盈止损策略 - {pos_data['name']}")
        self.geometry("560x620")
        self.configure(bg=Colors.BG_DARK)
        self.resizable(False, False)
        self.init_ui()
        self.load_current_strategy()

    def init_ui(self):
        main_f = tk.Frame(self, bg=Colors.BG_DARK, padx=20, pady=15)
        main_f.pack(fill='both', expand=True)

        # 标题
        tk.Label(main_f, text=f"📊 {self.pos_data['name']} ({self.pos_data['ts_code']})",
                bg=Colors.BG_DARK, fg=Colors.PRIMARY_DARK,
                font=("Microsoft YaHei", 14, "bold")).pack(anchor=tk.W, pady=10)

        # 持仓信息卡片
        info_card = tk.Frame(main_f, bg=Colors.BG_CARD, padx=15, pady=8)
        info_card.pack(fill=tk.X, pady=10)
        cost = self.pos_data['cost_price']
        highest = self.pos_data.get('highest_since_buy', 0) or cost
        tk.Label(info_card, text=f"持仓: {self.pos_data['quantity']}股  |  成本: {cost:.3f}  |  最高: {highest:.3f}",
                bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10)).pack(anchor=tk.W)

        # ======== 止损策略卡片 ========
        sl_card = tk.LabelFrame(main_f, text=" 🛑 止损策略 ",
                               bg=Colors.BG_DARK, fg=Colors.ACCENT_RED,
                               font=("Microsoft YaHei", 11, "bold"), padx=15, pady=10)
        sl_card.pack(fill=tk.X, pady=8)

        sl_inner = tk.Frame(sl_card, bg=Colors.BG_CARD)
        sl_inner.pack(fill=tk.X)

        # 止损类型
        r1 = tk.Frame(sl_inner, bg=Colors.BG_CARD, pady=6)
        r1.pack(fill=tk.X)
        tk.Label(r1, text="类型:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.sl_type_var = tk.StringVar(value='fixed')
        cf = ttk.Combobox(r1, textvariable=self.sl_type_var, values=self.STOP_LOSS_TYPES,
                          state='readonly', width=12)
        cf.pack(side=tk.LEFT)
        cf.bind('<<ComboboxSelected>>', lambda e: self._update_sl_ui())

        # 止损比例（所有类型共用）
        r2 = tk.Frame(sl_inner, bg=Colors.BG_CARD, pady=6)
        r2.pack(fill=tk.X)
        tk.Label(r2, text="止损比例:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.sl_value_var = tk.StringVar(value='8')
        tk.Entry(r2, textvariable=self.sl_value_var, width=8,
                bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT)
        tk.Label(r2, text="%", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=3)
        tk.Label(r2, text="初始/固定止损比例", bg=Colors.BG_CARD, fg=Colors.TEXT_MUTED,
                font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=(8, 0))

        # 保本激活涨幅（仅 breakeven）
        self.be_row = tk.Frame(sl_inner, bg=Colors.BG_CARD, pady=6)
        tk.Label(self.be_row, text="保本激活:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.be_var = tk.StringVar(value='10')
        tk.Entry(self.be_row, textvariable=self.be_var, width=8,
                bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT)
        tk.Label(self.be_row, text="%", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=3)
        tk.Label(self.be_row, text="涨超此比例后止损移至成本价", bg=Colors.BG_CARD,
                fg=Colors.TEXT_MUTED, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=(8, 0))

        # 移动模式（仅 trailing）
        self.tm_row = tk.Frame(sl_inner, bg=Colors.BG_CARD, pady=6)
        tk.Label(self.tm_row, text="移动模式:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.trailing_mode_var = tk.StringVar(value='strict')
        tcf = ttk.Combobox(self.tm_row, textvariable=self.trailing_mode_var,
                          values=self.TRAILING_MODES, state='readonly', width=10)
        tcf.pack(side=tk.LEFT)
        tk.Label(self.tm_row, text="strict=严格  loose=宽松(+2%缓冲)", bg=Colors.BG_CARD,
                fg=Colors.TEXT_MUTED, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=8)

        # ======== 止盈策略卡片 ========
        pe_card = tk.LabelFrame(main_f, text=" 🎯 止盈策略 ",
                               bg=Colors.BG_DARK, fg=Colors.ACCENT_GREEN,
                               font=("Microsoft YaHei", 11, "bold"), padx=15, pady=10)
        pe_card.pack(fill=tk.X, pady=8)

        pe_inner = tk.Frame(pe_card, bg=Colors.BG_CARD)
        pe_inner.pack(fill=tk.X)

        # 止盈类型
        pr1 = tk.Frame(pe_inner, bg=Colors.BG_CARD, pady=6)
        pr1.pack(fill=tk.X)
        tk.Label(pr1, text="类型:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.pe_type_var = tk.StringVar(value='trailing')
        pcf = ttk.Combobox(pr1, textvariable=self.pe_type_var, values=self.PROFIT_TYPES,
                          state='readonly', width=12)
        pcf.pack(side=tk.LEFT)
        pcf.bind('<<ComboboxSelected>>', lambda e: self._update_pe_ui())

        # 移动止盈比例（用于 trailing）
        self.tp_row = tk.Frame(pe_inner, bg=Colors.BG_CARD, pady=6)
        tk.Label(self.tp_row, text="回落比例:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.pe_value_var = tk.StringVar(value='15')
        tk.Entry(self.tp_row, textvariable=self.pe_value_var, width=8,
                bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT)
        tk.Label(self.tp_row, text="%", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=3)
        tk.Label(self.tp_row, text="从最高价回落此比例触发", bg=Colors.BG_CARD,
                fg=Colors.TEXT_MUTED, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=(8, 0))

        # 分批止盈（用于 scale）
        self.scale_frame = tk.Frame(pe_inner, bg=Colors.BG_CARD)

        s_row = tk.Frame(self.scale_frame, bg=Colors.BG_CARD, pady=6)
        s_row.pack(fill=tk.X)
        tk.Label(s_row, text="分批止盈:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        sf = tk.Frame(s_row, bg=Colors.BG_CARD)
        sf.pack(side=tk.LEFT)

        self.scale_1_var = tk.StringVar(value='20')
        self.scale_2_var = tk.StringVar(value='40')
        self.scale_3_var = tk.StringVar(value='60')

        def _mke(step, v):
            tk.Label(sf, text=f"第{step}批 +", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                    font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
            tk.Entry(sf, textvariable=v, width=4,
                    bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                    insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT, padx=(0, 10))
        _mke(1, self.scale_1_var)
        _mke(2, self.scale_2_var)
        _mke(3, self.scale_3_var)

        # 分批卖出比例
        sr_row = tk.Frame(self.scale_frame, bg=Colors.BG_CARD, pady=6)
        sr_row.pack(fill=tk.X)
        tk.Label(sr_row, text="卖出比例:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        srf = tk.Frame(sr_row, bg=Colors.BG_CARD)
        srf.pack(side=tk.LEFT)
        self.scale_r1_var = tk.StringVar(value='33')
        self.scale_r2_var = tk.StringVar(value='33')
        tk.Label(srf, text="第1批卖", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Entry(srf, textvariable=self.scale_r1_var, width=4,
                bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT)
        tk.Label(srf, text="%  第2批卖", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Entry(srf, textvariable=self.scale_r2_var, width=4,
                bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT)
        tk.Label(srf, text="%  第3批清仓", bg=Colors.BG_CARD, fg=Colors.TEXT_SECONDARY,
                font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        # 目标价（用于 target）
        self.target_row = tk.Frame(pe_inner, bg=Colors.BG_CARD, pady=6)
        tk.Label(self.target_row, text="目标价:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                font=("Microsoft YaHei", 10), width=10, anchor=tk.W).pack(side=tk.LEFT)
        self.target_price_var = tk.StringVar(value='')
        tk.Entry(self.target_row, textvariable=self.target_price_var, width=12,
                bg=Colors.BG_NAV, fg=Colors.TEXT_PRIMARY,
                insertbackground=Colors.TEXT_PRIMARY).pack(side=tk.LEFT)

        # ======== 按钮 ========
        btn_frame = tk.Frame(main_f, bg=Colors.BG_DARK, pady=10)
        btn_frame.pack(fill=tk.X)

        apply_btn = tk.Button(btn_frame, text="✓ 应用策略", bg=Colors.PRIMARY, fg="white",
                            font=("Microsoft YaHei", 11, "bold"), relief=tk.FLAT,
                            padx=20, pady=6, cursor="hand2", command=self.apply_strategy)
        apply_btn.pack(side=tk.LEFT, padx=5)
        apply_btn.bind("<Enter>", lambda e: apply_btn.configure(bg=Colors.PRIMARY_DARK))
        apply_btn.bind("<Leave>", lambda e: apply_btn.configure(bg=Colors.PRIMARY))

        reset_btn = tk.Button(btn_frame, text="↺ 重置", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                            font=("Microsoft YaHei", 11), relief=tk.FLAT,
                            padx=20, pady=6, cursor="hand2", command=self.reset_default)
        reset_btn.pack(side=tk.LEFT, padx=5)
        reset_btn.bind("<Enter>", lambda e: reset_btn.configure(bg=Colors.BG_NAV))
        reset_btn.bind("<Leave>", lambda e: reset_btn.configure(bg=Colors.BG_CARD))

        close_btn = tk.Button(btn_frame, text="✕ 关闭", bg=Colors.ACCENT_RED, fg="white",
                             font=("Microsoft YaHei", 11), relief=tk.FLAT,
                             padx=20, pady=6, cursor="hand2", command=self.destroy)
        close_btn.pack(side=tk.RIGHT, padx=5)
        close_btn.bind("<Enter>", lambda e: close_btn.configure(bg="#c62828"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(bg=Colors.ACCENT_RED))

        self._update_sl_ui()
        self._update_pe_ui()

    # ---------- UI 动态显隐 ----------

    def _update_sl_ui(self):
        sl_type = self.sl_type_var.get()
        self.tm_row.pack_forget()
        self.be_row.pack_forget()
        if sl_type == 'trailing':
            self.tm_row.pack(fill=tk.X)
        elif sl_type == 'breakeven':
            self.be_row.pack(fill=tk.X)

    def _update_pe_ui(self):
        pe_type = self.pe_type_var.get()
        self.tp_row.pack_forget()
        self.scale_frame.pack_forget()
        self.target_row.pack_forget()
        if pe_type == 'trailing':
            self.tp_row.pack(fill=tk.X)
        elif pe_type == 'scale':
            self.scale_frame.pack(fill=tk.X)
        elif pe_type == 'target':
            self.target_row.pack(fill=tk.X)

    # ---------- 数据加载 / 保存 ----------

    def load_current_strategy(self):
        pd = self.pos_data
        self.sl_type_var.set(pd.get('stop_loss_type', 'fixed'))
        self.sl_value_var.set(str(int(pd.get('stop_loss_value', 0.08) * 100)))
        self.trailing_mode_var.set(pd.get('trailing_mode', 'strict'))
        self.be_var.set(str(int(pd.get('breakeven_activate', 0.10) * 100)))
        self.pe_type_var.set(pd.get('profit_exit_type', 'trailing'))
        self.pe_value_var.set(str(int(pd.get('profit_exit_value', 0.15) * 100)))
        self.scale_1_var.set(str(int(pd.get('scale_profit_1', 0.20) * 100)))
        self.scale_2_var.set(str(int(pd.get('scale_profit_2', 0.40) * 100)))
        self.scale_3_var.set(str(int(pd.get('scale_profit_3', 0.60) * 100)))
        self.scale_r1_var.set(str(int(pd.get('scale_ratio_1', 0.33) * 100)))
        self.scale_r2_var.set(str(int(pd.get('scale_ratio_2', 0.33) * 100)))
        tp = pd.get('target_price')
        self.target_price_var.set(str(tp) if tp else '')
        self._update_sl_ui()
        self._update_pe_ui()

    def apply_strategy(self):
        try:
            pos_id = self.pos_data['id']
            cost = self.pos_data['cost_price']
            params = {
                'stop_loss_type': self.sl_type_var.get(),
                'stop_loss_value': float(self.sl_value_var.get()) / 100,
                'trailing_mode': self.trailing_mode_var.get(),
                'profit_exit_type': self.pe_type_var.get(),
            }
            # 保本激活
            try:
                params['breakeven_activate'] = float(self.be_var.get()) / 100
            except ValueError:
                pass
            # 移动止盈比例
            try:
                params['profit_exit_value'] = float(self.pe_value_var.get()) / 100
            except ValueError:
                pass
            # 分批止盈
            try:
                params.update({
                    'scale_profit_1': float(self.scale_1_var.get()) / 100,
                    'scale_profit_2': float(self.scale_2_var.get()) / 100,
                    'scale_profit_3': float(self.scale_3_var.get()) / 100,
                    'scale_ratio_1': float(self.scale_r1_var.get()) / 100,
                    'scale_ratio_2': float(self.scale_r2_var.get()) / 100,
                })
            except ValueError:
                pass
            # 目标价
            tp = self.target_price_var.get().strip()
            if tp:
                params['target_price'] = float(tp)

            success = self.pm.slpm.update_strategy(pos_id, **params)
            if success:
                messagebox.showinfo("✅ 成功", f"已为 {self.pos_data['name']} 更新止盈止损策略")
                self.callback()
                self.destroy()
            else:
                messagebox.showerror("❌ 错误", "更新策略失败")
        except ValueError as e:
            messagebox.showerror("❌ 输入错误", f"请检查数值：{e}")
        except Exception as e:
            messagebox.showerror("❌ 错误", f"更新策略时出错：{e}")

    def reset_default(self):
        d = self.pm.slpm.get_default_strategy()
        self.sl_type_var.set(d['stop_loss_type'])
        self.sl_value_var.set(str(int(d['stop_loss_value'] * 100)))
        self.trailing_mode_var.set(d['trailing_mode'])
        self.be_var.set(str(int(d['breakeven_activate'] * 100)))
        self.pe_type_var.set(d['profit_exit_type'])
        self.pe_value_var.set(str(int(d['profit_exit_value'] * 100)))
        self.scale_1_var.set(str(int(d['scale_profit_1'] * 100)))
        self.scale_2_var.set(str(int(d['scale_profit_2'] * 100)))
        self.scale_3_var.set(str(int(d['scale_profit_3'] * 100)))
        self.scale_r1_var.set(str(int(d['scale_ratio_1'] * 100)))
        self.scale_r2_var.set(str(int(d['scale_ratio_2'] * 100)))
        self.target_price_var.set('')
        self._update_sl_ui()
        self._update_pe_ui()
