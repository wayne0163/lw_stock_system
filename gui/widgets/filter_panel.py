# gui/widgets/filter_panel.py
# 筛选器面板组件 - 我的版块驱动增强版

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Callable, List
from core.watchlist import WatchlistManager

class FilterPanel(ttk.Frame):
    """左侧筛选面板 - 我的版块 & 技术 & 财务三位一体控制"""
    
    def __init__(self, parent, on_filter_callback, on_save_callback=None, strategy_list: List[str] = None, stock_manager=None):
        super().__init__(parent, padding=10)
        self.on_filter_callback = on_filter_callback
        self.on_save_callback = on_save_callback
        self.strategy_list = strategy_list or []
        self.stock_manager = stock_manager
        self.watchlist_manager = WatchlistManager()
        self.on_load_strategy_callback = None
        self.metrics_vars = {}
        
        # 内部状态
        self.all_themes = []
        self.current_selected_themes = set() 
        
        self.setup_ui()
    
    def setup_ui(self):
        # 1. 策略加载
        top_f = ttk.LabelFrame(self, text="策略快速配置", padding=5)
        top_f.pack(fill=tk.X, pady=(0, 10))
        self.strategy_var = tk.StringVar(value="选择已有策略...")
        self.strategy_combo = ttk.Combobox(top_f, textvariable=self.strategy_var, values=self.strategy_list, state='readonly')
        self.strategy_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.strategy_combo.bind('<<ComboboxSelected>>', self.on_strategy_combo_selected)
        ttk.Button(top_f, text="重置", command=self.reset_all).pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # --- Tab 1: 范围 & 我的版块 (原行业) ---
        scope_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(scope_tab, text=" 📍 我的版块 ")
        
        sf = ttk.LabelFrame(scope_tab, text="选股我的版块范围", padding=10)
        sf.pack(fill=tk.X, pady=5)
        self.scope_var = tk.StringVar(value="all")
        ttk.Radiobutton(sf, text="全市场股票", variable=self.scope_var, value="all").pack(anchor=tk.W)
        ttk.Radiobutton(sf, text="指定我的版块 (含自定义):", variable=self.scope_var, value="industry").pack(anchor=tk.W, pady=(5,0))
        
        # 我的版块搜索与多选
        search_f = ttk.Frame(sf)
        search_f.pack(fill=tk.X, padx=(20,0), pady=2)
        
        self.theme_search_var = tk.StringVar()
        self.theme_search_var.trace_add("write", lambda *args: self.refresh_theme_list())
        search_ent = ttk.Entry(search_f, textvariable=self.theme_search_var, font=('Arial', 9))
        search_ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.show_selected_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_f, text="已选", variable=self.show_selected_var, command=self.refresh_theme_list).pack(side=tk.RIGHT, padx=5)

        list_f = ttk.Frame(sf)
        list_f.pack(fill=tk.BOTH, expand=True, padx=(20,0), pady=2)
        
        self.theme_listbox = tk.Listbox(list_f, selectmode=tk.MULTIPLE, height=6, exportselection=False, font=('Arial', 9))
        self.theme_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.theme_listbox.bind('<<ListboxSelect>>', self.on_theme_select_change)
        
        scrollbar = ttk.Scrollbar(list_f, orient=tk.VERTICAL, command=self.theme_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.theme_listbox.config(yscrollcommand=scrollbar.set)

        self.selected_summary_var = tk.StringVar(value="未选择我的版块")
        summary_lbl = ttk.Label(sf, textvariable=self.selected_summary_var, foreground="#2a9d8f", wraplength=300, font=('Microsoft YaHei', 8))
        summary_lbl.pack(fill=tk.X, padx=(20,0), pady=2)
        
        # 加载数据
        self.load_all_themes_data()
        self.refresh_theme_list()

        # 规则
        rf = ttk.LabelFrame(scope_tab, text="时间跨度规则", padding=10)
        rf.pack(fill=tk.X, pady=5)
        self.data_rule_var = tk.StringVar(value="annual")
        ttk.Radiobutton(rf, text="仅年报数据 (更稳健)", variable=self.data_rule_var, value="annual").pack(anchor=tk.W)
        ttk.Radiobutton(rf, text="最新财报/季报 (更灵敏)", variable=self.data_rule_var, value="latest").pack(anchor=tk.W)

        # 市值
        cf = ttk.LabelFrame(scope_tab, text="总市值限制 (亿元)", padding=10)
        cf.pack(fill=tk.X, pady=5)
        self.cap_check_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cf, text="启用市值过滤", variable=self.cap_check_var).pack(anchor=tk.W)
        sp_f = ttk.Frame(cf); sp_f.pack(fill=tk.X, pady=5)
        self.cap_min_var = tk.IntVar(value=10); self.cap_max_var = tk.IntVar(value=2000)
        ttk.Spinbox(sp_f, from_=0, to=100000, textvariable=self.cap_min_var, width=6).pack(side=tk.LEFT)
        ttk.Label(sp_f, text="~").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(sp_f, from_=0, to=100000, textvariable=self.cap_max_var, width=6).pack(side=tk.LEFT)

        # --- Tab 2: 财务面板 ---
        fin_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(fin_tab, text=" 💰 财务 ")
        metrics_def = [
            ("roe_dt", "ROE (净资产收益率) ≥", 12.0),
            ("roic", "ROIC (投入资本回报率) ≥", 10.0),
            ("tr_yoy", "营业总收入增速 ≥", 10.0),
            ("dt_netprofit_yoy", "扣非净利同比增长率 ≥", 15.0),
            ("grossprofit_margin", "销售毛利率 ≥", 25.0),
            ("debt_to_assets", "资产负债率 ≤", 60.0),
            ("netprofit_margin", "销售净利率 ≥", 10.0)
        ]
        for field, name, default in metrics_def:
            f = ttk.Frame(fin_tab); f.pack(fill=tk.X, pady=3)
            c_var = tk.BooleanVar(value=False); v_var = tk.DoubleVar(value=default)
            ttk.Checkbutton(f, text=name, variable=c_var).pack(side=tk.LEFT)
            ttk.Spinbox(f, from_=-100, to=1000, textvariable=v_var, width=6).pack(side=tk.RIGHT)
            self.metrics_vars[field] = (c_var, v_var)

        # --- Tab 3: 技术面板 ---
        tech_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tech_tab, text=" 📈 技术 ")
        
        # 1. MA
        ma_f = ttk.LabelFrame(tech_tab, text="价格均线周期", padding=5)
        ma_f.pack(fill=tk.X, pady=2)
        self.ma_s_v = tk.IntVar(value=20); self.ma_m_v = tk.IntVar(value=120); self.ma_l_v = tk.IntVar(value=240)
        p_f = ttk.Frame(ma_f); p_f.pack(fill=tk.X)
        ttk.Label(p_f, text="短:").pack(side=tk.LEFT); ttk.Entry(p_f, textvariable=self.ma_s_v, width=3).pack(side=tk.LEFT)
        ttk.Label(p_f, text="中:").pack(side=tk.LEFT, padx=2); ttk.Entry(p_f, textvariable=self.ma_m_v, width=3).pack(side=tk.LEFT)
        ttk.Label(p_f, text="长:").pack(side=tk.LEFT, padx=2); ttk.Entry(p_f, textvariable=self.ma_l_v, width=3).pack(side=tk.LEFT)
        self.ma_order_c = tk.BooleanVar(value=False)
        ttk.Checkbutton(ma_f, text="多头排列 (短>中>长)", variable=self.ma_order_c).pack(anchor=tk.W, pady=2)

        # 2. RSI
        rsi_f = ttk.LabelFrame(tech_tab, text="RSI 强弱指标", padding=5)
        rsi_f.pack(fill=tk.X, pady=2)
        self.rsi_s_v = tk.IntVar(value=6); self.rsi_l_v = tk.IntVar(value=12)
        r_p_f = ttk.Frame(rsi_f); r_p_f.pack(fill=tk.X)
        ttk.Label(r_p_f, text="短:").pack(side=tk.LEFT); ttk.Entry(r_p_f, textvariable=self.rsi_s_v, width=3).pack(side=tk.LEFT)
        ttk.Label(r_p_f, text="长:").pack(side=tk.LEFT, padx=2); ttk.Entry(r_p_f, textvariable=self.rsi_l_v, width=3).pack(side=tk.LEFT)
        self.rsi_cross_c = tk.BooleanVar(value=False); ttk.Checkbutton(rsi_f, text="短线金叉 (短>长)", variable=self.rsi_cross_c).pack(anchor=tk.W)
        
        self.rsi_s_val_c = tk.BooleanVar(value=False); self.rsi_s_limit = tk.IntVar(value=60)
        v_s_f = ttk.Frame(rsi_f); v_s_f.pack(fill=tk.X)
        ttk.Checkbutton(v_s_f, text="RSI(短) >", variable=self.rsi_s_val_c).pack(side=tk.LEFT)
        ttk.Entry(v_s_f, textvariable=self.rsi_s_limit, width=4).pack(side=tk.LEFT)
        
        self.rsi_l_val_c = tk.BooleanVar(value=False); self.rsi_l_limit = tk.IntVar(value=50)
        v_l_f = ttk.Frame(rsi_f); v_l_f.pack(fill=tk.X)
        ttk.Checkbutton(v_l_f, text="RSI(长) >", variable=self.rsi_l_val_c).pack(side=tk.LEFT)
        ttk.Entry(v_l_f, textvariable=self.rsi_l_limit, width=4).pack(side=tk.LEFT)

        # 3. VMA
        vma_f = ttk.LabelFrame(tech_tab, text="成交量均线系统", padding=5)
        vma_f.pack(fill=tk.X, pady=2)
        self.vma_s_v = tk.IntVar(value=5); self.vma_l_v = tk.IntVar(value=10)
        v_p_f = ttk.Frame(vma_f); v_p_f.pack(fill=tk.X)
        ttk.Label(v_p_f, text="短:").pack(side=tk.LEFT); ttk.Entry(v_p_f, textvariable=self.vma_s_v, width=3).pack(side=tk.LEFT)
        ttk.Label(v_p_f, text="长:").pack(side=tk.LEFT, padx=2); ttk.Entry(v_p_f, textvariable=self.vma_l_v, width=3).pack(side=tk.LEFT)
        self.vma_cross_c = tk.BooleanVar(value=False); ttk.Checkbutton(vma_f, text="放量金叉 (短>长)", variable=self.vma_cross_c).pack(anchor=tk.W)

        # 4. 52周价格区间（新增）
        price52w_f = ttk.LabelFrame(tech_tab, text="52周价格区间（距离高低点的百分比）", padding=5)
        price52w_f.pack(fill=tk.X, pady=4)

        # 距52周高点
        self.p52w_high_c = tk.BooleanVar(value=False); self.p52w_high_v = tk.IntVar(value=25)
        pf_top = ttk.Frame(price52w_f); pf_top.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(pf_top, text="距52周高点 ≤", variable=self.p52w_high_c).pack(side=tk.LEFT)
        ttk.Entry(pf_top, textvariable=self.p52w_high_v, width=5).pack(side=tk.LEFT)
        ttk.Label(pf_top, text="%  （必须勾选才生效）").pack(side=tk.LEFT, padx=2)

        # 距52周低点
        self.p52w_low_c = tk.BooleanVar(value=False); self.p52w_low_v = tk.IntVar(value=0)
        pf_bot = ttk.Frame(price52w_f); pf_bot.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(pf_bot, text="距52周低点 ≥", variable=self.p52w_low_c).pack(side=tk.LEFT)
        ttk.Entry(pf_bot, textvariable=self.p52w_low_v, width=5).pack(side=tk.LEFT)
        ttk.Label(pf_bot, text="%  （防止买在历史底部区域）").pack(side=tk.LEFT, padx=2)

        # 底部按钮
        bottom_f = ttk.Frame(self, padding=(0, 10, 0, 0))
        bottom_f.pack(fill=tk.X, side=tk.BOTTOM)
        self.btn_run = ttk.Button(bottom_f, text="🚀 启动全市场我的版块扫描", command=self.on_run_filter, style='Accent.TButton')
        self.btn_run.pack(fill=tk.X, pady=2)
        ttk.Button(bottom_f, text="💾 保存为策略", command=self.on_save_strategy).pack(fill=tk.X)

    def load_all_themes_data(self):
        """整合官方行业与用户自定义我的版块"""
        official = []
        if self.stock_manager:
            try: official = sorted(self.stock_manager.get_all_industries())
            except: pass
            
        # 用户分组
        user_groups = [g for g in self.watchlist_manager.get_groups() if g not in ['自选股', '观察池', '已买入']]
        user_themes = [f"[我的版块] {g}" for g in user_groups]
        
        self.all_themes = user_themes + official

    def refresh_theme_list(self):
        search_term = self.theme_search_var.get().lower()
        only_selected = self.show_selected_var.get()
        self.theme_listbox.delete(0, tk.END)
        
        for theme in self.all_themes:
            is_match = search_term in theme.lower()
            is_selected = theme in self.current_selected_themes
            if only_selected:
                if is_selected and is_match: self.theme_listbox.insert(tk.END, theme)
            elif is_match:
                self.theme_listbox.insert(tk.END, theme)
            
            if theme in self.current_selected_themes and is_match:
                # 刚才 delete 之后索引变了，需要找到正确的索引
                idx = self.theme_listbox.size() - 1
                self.theme_listbox.selection_set(idx)
        self.update_summary()

    def on_theme_select_change(self, event):
        indices = self.theme_listbox.curselection()
        current_view_items = self.theme_listbox.get(0, tk.END)
        
        # 仅同步当前视图可见项的状态
        for i, item in enumerate(current_view_items):
            if i in indices: self.current_selected_themes.add(item)
            else:
                if item in self.current_selected_themes: self.current_selected_themes.remove(item)
        self.update_summary()

    def update_summary(self):
        count = len(self.current_selected_themes)
        if count == 0: self.selected_summary_var.set("未选择我的版块 (默认全市场)")
        else:
            names = sorted(list(self.current_selected_themes))
            txt = ", ".join(names)
            if len(txt) > 55: txt = txt[:52] + "..."
            self.selected_summary_var.set(f"已选({count}): {txt}")

    def on_strategy_combo_selected(self, event):
        if self.on_load_strategy_callback: self.on_load_strategy_callback(self.strategy_var.get())

    def get_params(self) -> Dict:
        fin_filters = {}
        for field, (c_var, v_var) in self.metrics_vars.items():
            if c_var.get():
                suffix = "_max" if field == 'debt_to_assets' else "_min"
                fin_filters[f"{field}{suffix}"] = v_var.get()
        
        return {
            'sectors': list(self.current_selected_themes) if self.scope_var.get() == "industry" else ["全市场"],
            'require_annual': self.data_rule_var.get() == "annual",
            'basic_filters': {'enable_cap': self.cap_check_var.get(), 'market_cap_min': self.cap_min_var.get(), 'market_cap_max': self.cap_max_var.get()},
            'tech_params': {
                'ma_periods': [self.ma_s_v.get(), self.ma_m_v.get(), self.ma_l_v.get()],
                'rsi_periods': [self.rsi_s_v.get(), self.rsi_l_v.get()],
                'vma_periods': [self.vma_s_v.get(), self.vma_l_v.get()],
                'require_ma_order': self.ma_order_c.get(),
                'require_rsi_cross': self.rsi_cross_c.get(),
                'require_rsi_s_val': self.rsi_s_val_c.get(), 'rsi_s_limit': self.rsi_s_limit.get(),
                'require_rsi_l_val': self.rsi_l_val_c.get(), 'rsi_l_limit': self.rsi_l_limit.get(),
                'require_vma_cross': self.vma_cross_c.get()
            },
            'price_distance_filters': {
                'enable_52w_high': self.p52w_high_c.get(),
                'pct_within_52w_high_max': self.p52w_high_v.get(),
                'enable_52w_low': self.p52w_low_c.get(),
                'pct_above_52w_low_min': self.p52w_low_v.get()
            },
            'financial_filters': fin_filters
        }

    def set_params(self, params):
        try:
            self.data_rule_var.set("annual" if params.get('require_annual', True) else "latest")
            sectors = params.get('sectors', [])
            self.current_selected_themes = set()
            if "全市场" in sectors or not sectors:
                self.scope_var.set("all")
            else:
                self.scope_var.set("industry")
                for s in sectors: self.current_selected_themes.add(s)
            
            self.refresh_theme_list()
            bf = params.get('basic_filters', {})
            self.cap_check_var.set(bf.get('enable_cap', True))
            self.cap_min_var.set(bf.get('market_cap_min', 10))
            self.cap_max_var.set(bf.get('market_cap_max', 2000))

            ff = params.get('financial_filters', {})
            for field, (c_var, v_var) in self.metrics_vars.items():
                match = next((ff[k] for k in [f"{field}_min", f"{field}_max", field] if k in ff), None)
                if match is not None: c_var.set(True); v_var.set(match)
                else: c_var.set(False)
            
            tp = params.get('tech_params', {})
            if tp:
                mas = tp.get('ma_periods', [20, 120, 240])
                self.ma_s_v.set(mas[0]); self.ma_m_v.set(mas[1]); self.ma_l_v.set(mas[2])
                rsis = tp.get('rsi_periods', [6, 12])
                self.rsi_s_v.set(rsis[0]); self.rsi_l_v.set(rsis[1])
                vmas = tp.get('vma_periods', [5, 10])
                self.vma_s_v.set(vmas[0]); self.vma_l_v.set(vmas[1])
                self.ma_order_c.set(tp.get('require_ma_order', False))
                self.rsi_cross_c.set(tp.get('require_rsi_cross', False))
                self.rsi_s_val_c.set(tp.get('require_rsi_s_val', False)); self.rsi_s_limit.set(tp.get('rsi_s_limit', 60))
                self.rsi_l_val_c.set(tp.get('require_rsi_l_val', False)); self.rsi_l_limit.set(tp.get('rsi_l_limit', 50))
                self.vma_cross_c.set(tp.get('require_vma_cross', False))

            p52f = params.get('price_distance_filters', {})
            if p52f:
                self.p52w_high_c.set(p52f.get('enable_52w_high', False))
                self.p52w_high_v.set(p52f.get('pct_within_52w_high_max', 25))
                self.p52w_low_c.set(p52f.get('enable_52w_low', False))
                self.p52w_low_v.set(p52f.get('pct_above_52w_low_min', 0))
            self.update_idletasks()
        except Exception as e: print(f"Set UI error: {e}")

    def reset_all(self):
        self.scope_var.set("all")
        self.theme_search_var.set("")
        self.show_selected_var.set(False)
        self.current_selected_themes.clear()
        self.refresh_theme_list()
        for c_var, v_var in self.metrics_vars.values(): c_var.set(False)
        self.ma_order_c.set(False); self.rsi_cross_c.set(False); self.vma_cross_c.set(False)

    def on_run_filter(self): self.on_filter_callback(self.get_params())
    def on_save_strategy(self): 
        if self.on_save_callback: self.on_save_callback(self.get_params())
