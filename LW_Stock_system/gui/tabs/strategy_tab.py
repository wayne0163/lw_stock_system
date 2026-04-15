# 策略管理标签页 - 十字象限布局重构版

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.strategy import StrategyManager, Strategy

class StrategyTab:
    """策略管理页面 - 专业操盘手版布局"""
    
    def __init__(self, parent):
        self.parent = parent
        self.manager = StrategyManager()
        self.current_strategy = None
        self.vars = {} # 统一管理所有 UI 变量
        self.setup_ui()
        self.refresh_list()
    
    def setup_ui(self):
        # 主容器：上下分割
        main_paned = ttk.PanedWindow(self.parent, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- 顶部：列表与基础信息 (高度占比小) ---
        top_frame = ttk.Frame(main_paned, height=150)
        main_paned.add(top_frame, weight=1)
        
        # 列表区
        list_f = ttk.Frame(top_frame)
        list_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(list_f, columns=('name','desc'), show='headings', height=5)
        self.tree.heading('name', text='策略名称'); self.tree.heading('desc', text='描述')
        self.tree.column('name', width=150); self.tree.column('desc', width=400)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_strategy_selected)
        
        # 按钮区
        btn_f = ttk.Frame(top_frame, padding=10)
        btn_f.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Button(btn_f, text="➕ 新建", command=self.on_create).pack(fill=tk.X, pady=2)
        ttk.Button(btn_f, text="🗑️ 删除", command=self.on_delete).pack(fill=tk.X, pady=2)
        ttk.Button(btn_f, text="💾 保存所有修改", style='Accent.TButton', command=self.on_save).pack(fill=tk.X, pady=10)

        # --- 底部：十字象限参数配置 (核心重构点) ---
        config_frame = ttk.LabelFrame(main_paned, text="⚙️ 策略硬核配置 (十字象限布局)", padding=10)
        main_paned.add(config_frame, weight=4)
        
        # 创建 2x2 网格
        grid_f = ttk.Frame(config_frame)
        grid_f.pack(fill=tk.BOTH, expand=True)
        grid_f.columnconfigure(0, weight=1); grid_f.columnconfigure(1, weight=1)
        grid_f.rowconfigure(0, weight=1); grid_f.rowconfigure(1, weight=1)

        # [象限 1: 左上 - 范围与市值]
        q1 = ttk.LabelFrame(grid_f, text="📍 范围与市值", padding=10)
        q1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._build_q1(q1)

        # [象限 2: 右上 - 财务硬核]
        q2 = ttk.LabelFrame(grid_f, text="💰 财务硬核指标", padding=10)
        q2.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self._build_q2(q2)

        # [象限 3: 左下 - 价格技术]
        q3 = ttk.LabelFrame(grid_f, text="📈 价格技术系统", padding=10)
        q3.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._build_q3(q3)

        # [象限 4: 右下 - 成交量与风险]
        q4 = ttk.LabelFrame(grid_f, text="📊 成交量与风险控制", padding=10)
        q4.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self._build_q4(q4)

    def _build_q1(self, p):
        # 市值
        f = ttk.Frame(p); f.pack(fill=tk.X, pady=5)
        self.vars['enable_cap'] = tk.BooleanVar()
        ttk.Checkbutton(f, text="启用市值过滤 (亿元):", variable=self.vars['enable_cap']).pack(side=tk.LEFT)
        self.vars['cap_min'] = tk.DoubleVar(); self.vars['cap_max'] = tk.DoubleVar()
        ttk.Entry(f, textvariable=self.vars['cap_min'], width=6).pack(side=tk.LEFT, padx=5)
        ttk.Label(f, text="~").pack(side=tk.LEFT)
        ttk.Entry(f, textvariable=self.vars['cap_max'], width=6).pack(side=tk.LEFT, padx=5)

    def _build_q2(self, p):
        # 核心财务指标
        metrics = [
            ("roe_dt_min", "ROE 净资产收益率 ≥", "%"),
            ("roic_min", "ROIC 投入资本回报率 ≥", "%"),
            ("tr_yoy_min", "营业总收入增速 ≥", "%"),
            ("dt_netprofit_yoy_min", "扣非净利同比增长率 ≥", "%"),
            ("grossprofit_margin_min", "销售毛利率 ≥", "%")
        ]
        for key, label, unit in metrics:
            f = ttk.Frame(p); f.pack(fill=tk.X, pady=2)
            ttk.Label(f, text=label, width=20).pack(side=tk.LEFT)
            self.vars[key] = tk.DoubleVar()
            ttk.Entry(f, textvariable=self.vars[key], width=8).pack(side=tk.RIGHT)
            ttk.Label(f, text=unit).pack(side=tk.RIGHT, padx=2)

    def _build_q3(self, p):
        # 均线系统
        f1 = ttk.Frame(p); f1.pack(fill=tk.X, pady=2)
        ttk.Label(f1, text="价格均线周期:").pack(side=tk.LEFT)
        self.vars['ma_s'] = tk.IntVar(); self.vars['ma_m'] = tk.IntVar(); self.vars['ma_l'] = tk.IntVar()
        ttk.Entry(f1, textvariable=self.vars['ma_s'], width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(f1, textvariable=self.vars['ma_m'], width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(f1, textvariable=self.vars['ma_l'], width=4).pack(side=tk.LEFT, padx=2)
        self.vars['req_ma_order'] = tk.BooleanVar()
        ttk.Checkbutton(p, text="必须满足: 短 > 中 > 长 (多头排列)", variable=self.vars['req_ma_order']).pack(anchor=tk.W, pady=2)
        
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # RSI
        f2 = ttk.Frame(p); f2.pack(fill=tk.X, pady=2)
        ttk.Label(f2, text="RSI 周期 (短/长):").pack(side=tk.LEFT)
        self.vars['rsi_s_p'] = tk.IntVar(); self.vars['rsi_l_p'] = tk.IntVar()
        ttk.Entry(f2, textvariable=self.vars['rsi_s_p'], width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(f2, textvariable=self.vars['rsi_l_p'], width=4).pack(side=tk.LEFT, padx=2)
        
        f3 = ttk.Frame(p); f3.pack(fill=tk.X, pady=2)
        self.vars['req_rsi_range'] = tk.BooleanVar()
        ttk.Checkbutton(f3, text="RSI(短) 范围:", variable=self.vars['req_rsi_range']).pack(side=tk.LEFT)
        self.vars['rsi_min'] = tk.DoubleVar(); self.vars['rsi_max'] = tk.DoubleVar()
        ttk.Entry(f3, textvariable=self.vars['rsi_min'], width=5).pack(side=tk.LEFT, padx=2)
        ttk.Label(f3, text="< R <").pack(side=tk.LEFT)
        ttk.Entry(f3, textvariable=self.vars['rsi_max'], width=5).pack(side=tk.LEFT, padx=2)

    def _build_q4(self, p):
        # VMA
        f1 = ttk.Frame(p); f1.pack(fill=tk.X, pady=2)
        ttk.Label(f1, text="成交量均线 (短/长):").pack(side=tk.LEFT)
        self.vars['vma_s'] = tk.IntVar(); self.vars['vma_l'] = tk.IntVar()
        ttk.Entry(f1, textvariable=self.vars['vma_s'], width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(f1, textvariable=self.vars['vma_l'], width=4).pack(side=tk.LEFT, padx=2)
        self.vars['req_vma_cross'] = tk.BooleanVar()
        ttk.Checkbutton(p, text="必须满足: VMA短 > VMA长 (放量)", variable=self.vars['req_vma_cross']).pack(anchor=tk.W, pady=2)
        
        ttk.Separator(p, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # 风险控制
        f2 = ttk.Frame(p); f2.pack(fill=tk.X, pady=2)
        ttk.Label(f2, text="资产负债率上限 ≤").pack(side=tk.LEFT)
        self.vars['debt_max'] = tk.DoubleVar()
        ttk.Entry(f2, textvariable=self.vars['debt_max'], width=8).pack(side=tk.RIGHT)
        ttk.Label(f2, text="%").pack(side=tk.RIGHT, padx=2)

    def on_strategy_selected(self, event):
        sel = self.tree.selection()
        if not sel: return
        name = self.tree.item(sel[0], 'values')[0]
        s = self.manager.get(name)
        if s:
            self.current_strategy = s
            self.load_to_ui(s.params)

    def load_to_ui(self, p):
        # 象限 1
        bf = p.get('basic_filters', {})
        self.vars['enable_cap'].set(bf.get('enable_cap', True))
        self.vars['cap_min'].set(bf.get('market_cap_min', 0))
        self.vars['cap_max'].set(bf.get('market_cap_max', 0))
        
        # 象限 2
        ff = p.get('financial_filters', {})
        legacy_map = {
            'n_income_yoy_min': 'dt_netprofit_yoy_min',
            'gpm_min': 'grossprofit_margin_min'
        }
        for k in ['roe_dt_min','roic_min','tr_yoy_min','dt_netprofit_yoy_min','grossprofit_margin_min']:
            val = ff.get(k)
            if val is None:
                # 尝试从 legacy_map 反查
                old_k_list = [ok for ok, nk in legacy_map.items() if nk == k]
                if old_k_list: val = ff.get(old_k_list[0])
            self.vars[k].set(val or 0)
        
        # 象限 3 & 4
        tp = p.get('tech_params', {})
        mas = tp.get('ma_periods', [20, 120, 240])
        self.vars['ma_s'].set(mas[0]); self.vars['ma_m'].set(mas[1]); self.vars['ma_l'].set(mas[2])
        self.vars['req_ma_order'].set(tp.get('require_ma_order', False))
        
        rsis = tp.get('rsi_periods', [6, 12])
        self.vars['rsi_s_p'].set(rsis[0]); self.vars['rsi_l_p'].set(rsis[1])
        self.vars['req_rsi_range'].set(tp.get('require_rsi_s_range', False))
        self.vars['rsi_min'].set(tp.get('rsi_s_min', 0))
        self.vars['rsi_max'].set(tp.get('rsi_s_max', 100))
        
        vmas = tp.get('vma_periods', [5, 10])
        self.vars['vma_s'].set(vmas[0]); self.vars['vma_l'].set(vmas[1])
        self.vars['req_vma_cross'].set(tp.get('require_vma_cross', False))
        
        self.vars['debt_max'].set(ff.get('debt_to_assets_max', 100))

    def on_save(self):
        if not self.current_strategy: return
        p = self.current_strategy.params
        # 写回数据
        p['basic_filters'] = {
            'enable_cap': self.vars['enable_cap'].get(),
            'market_cap_min': self.vars['cap_min'].get(),
            'market_cap_max': self.vars['cap_max'].get()
        }
        p['financial_filters'] = {
            'roe_dt_min': self.vars['roe_dt_min'].get(),
            'roic_min': self.vars['roic_min'].get(),
            'tr_yoy_min': self.vars['tr_yoy_min'].get(),
            'dt_netprofit_yoy_min': self.vars['dt_netprofit_yoy_min'].get(),
            'grossprofit_margin_min': self.vars['grossprofit_margin_min'].get(),
            'debt_to_assets_max': self.vars['debt_max'].get()
        }
        p['tech_params'] = {
            'ma_periods': [self.vars['ma_s'].get(), self.vars['ma_m'].get(), self.vars['ma_l'].get()],
            'rsi_periods': [self.vars['rsi_s_p'].get(), self.vars['rsi_l_p'].get()],
            'vma_periods': [self.vars['vma_s'].get(), self.vars['vma_l'].get()],
            'require_ma_order': self.vars['req_ma_order'].get(),
            'require_rsi_s_range': self.vars['req_rsi_range'].get(),
            'rsi_s_min': self.vars['rsi_min'].get(),
            'rsi_s_max': self.vars['rsi_max'].get(),
            'require_vma_cross': self.vars['req_vma_cross'].get()
        }
        if self.current_strategy.save():
            messagebox.showinfo("成功", "策略参数已同步至物理文件")
            self.refresh_list()

    def refresh_list(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.manager.load_all()
        for s in self.manager.get_all():
            self.tree.insert('', tk.END, values=(s.name, s.description))

    def on_create(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("新策略", "请输入名称:")
        if name:
            # 优先使用 conservative 作为模板，如果不存在则使用硬编码默认值
            template = 'conservative' if 'conservative' in self.manager.strategies else None
            self.manager.create(name, name, template)
            self.refresh_list()

    def on_delete(self):
        sel = self.tree.selection()
        if sel:
            name = self.tree.item(sel[0], 'values')[0]
            if name in ['conservative','aggressive']: return
            if messagebox.askyesno("确认", f"删除策略 {name}?"):
                self.manager.delete(name); self.refresh_list()
