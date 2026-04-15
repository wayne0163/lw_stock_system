import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
from core.config import config

class SettingsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill='both', expand=True)
        self.config_manager = config
        self.init_ui()

    def init_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill='both', expand=True)
        
        ttk.Label(container, text="👤 个人投资画像与目标设定", font=("Arial", 14, "bold")).pack(anchor='w', pady=10)
        
        self.inputs = {}
        # 从全局配置中获取 profile
        profile = self.config_manager.config.get("user_profile", {})
        
        fields = [
            ("投资目标 (年化 %):", "annual_return_target"),
            ("最大回撤容忍度 (%):", "max_drawdown_tolerance"),
            ("资金来源说明:", "source_of_funds"),
            ("风险偏好 (保守/稳健/激进):", "risk_preference"),
            ("核心投资哲学:", "investment_philosophy")
        ]
        
        form = ttk.Frame(container)
        form.pack(fill='x', pady=10)
        
        for i, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky='w', pady=5)
            entry = ttk.Entry(form, width=40)
            entry.insert(0, str(profile.get(key, "")))
            entry.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
            self.inputs[key] = entry
            
        form.columnconfigure(1, weight=1)
        
        ttk.Button(container, text="💾 保存配置", command=self.save_config).pack(pady=20)
        
        # 帮助说明
        help_text = (
            "💡 说明：\n"
            "1. 这些参数将直接决定 AI 对您交易行为的评价标准。\n"
            "2. 比如：如果回撤超过您的容忍度，AI 会发出红色预警。\n"
            "3. 资金来源会影响 AI 对您交易心态（恐慌/从容）的分析。"
        )
        ttk.Label(container, text=help_text, foreground="gray", justify='left').pack(anchor='w', pady=20)

        # 特别功能说明按钮
        ttk.Button(container, text="📖 特别功能说明（隐藏逻辑）", command=self.show_special_features).pack(pady=10)

    def show_special_features(self):
        """弹出特别功能说明窗口"""
        dialog = tk.Toplevel(self)
        dialog.title("📖 特别功能说明 - 隐藏逻辑与设定")
        dialog.geometry("900x700")
        dialog.transient(self)
        dialog.grab_set()

        # 创建滚动文本框
        text_frame = ttk.Frame(dialog, padding=20)
        text_frame.pack(fill='both', expand=True)

        text_widget = tk.Text(text_frame, wrap='word', font=('Arial', 11), height=30, width=80)
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 说明内容
        content = """
# 📖 特别功能说明

## 一、💰 盈亏计算口径（必读）

### 1.1 三个关键数字
- **持仓盈亏**：股票当前市值 - 持仓成本（不含交易费用影响）
- **账户总盈亏**：当前总资产 - 初始本金 250,000（这才是你真正的赚/亏）
- **现金余额**：实际可用的资金

### 1.2 为什么两者不一致？
- 持仓盈亏 = 6,576.65 元（仅股票市值变动）
- 账户总盈亏 = 1,737.69 元（扣除所有交易费用后的净赚）
- 差额 = 4,998.96 元 = 已花掉的手续费 + 已实现的盈亏差额

> ✅ 界面显示的是 **账户总盈亏**（总资产 - 初始本金），不是持仓盈亏。

---

## 二、🔢 筛选器与打分逻辑（外面看不到）

### 2.1 自选股筛选（全部股票页）
- **"仅自选"模式**：只显示 `watchlist` 表中 `is_favorite=1` 的股票
- **搜索框**：实时搜索代码/名称（防抖 300ms，避免频繁查询）
- **排序**：点击列标题可升序/降序（记忆上次排序状态）

### 2.2 行业/版块分类
- 数据来自 `stocks_basic` 表的 `industry` 字段
- 版块筛选在后台已准备好，界面暂未开放（预留扩展）

---

## 三、💸 交易费用计算规则（精确到分）

### 3.1 费用公式
```python
手续费 = 成交额 × 0.0003 + 15  # 买卖统一，最低 15 元
```
- **买入费用**：直接从买入金额扣除
- **卖出费用**：从卖出金额扣除
- **过户费**：忽略（A股小于 0.001%，可忽略）

### 3.2 成本价含费
```
成本价 = (成交额 + 手续费) ÷ 数量
```
举例：鼎通科技买入 700 股 @ 151.37
- 成交额：105,959.00
- 手续费：46.79
- 总成本：106,005.79
- **成本价：106,005.79 ÷ 700 = 151.437**

> 这解释了为什么成本价和实时价格不一样。

---

## 四、📊 持仓重建逻辑（rebuild_positions_from_logs）

### 4.1 何时触发？
- 首次启动（positions 表为空）
- 手动点击"重建持仓"（未来功能）
- 数据校验失败时自动修复

### 4.2 重建步骤
1. **清空 positions 表**
2. **读取所有 trade_log**（按时间顺序）
3. **逐笔计算净持有数量**（买入累加，卖出递减）
4. **计算加权成本价**（成本 = 成交额 + 手续费）
5. **从最近一次买入记录恢复止损止盈**
6. **自动补全 ts_code 后缀**（如 603662 → 603662.SH）
7. **重算现金余额**（基于所有流水 post_balance）

### 4.3 关键细节
- 成本计算**包含手续费**，不是简单的价格加权
- 如果某股票净持有为 0，不插入 positions 表
- `ts_code` 后缀从 `stocks_basic` 表自动匹配，确保格式统一

---

## 五、🔁 价格同步时机（自动更新 current_price）

### 5.1 触发场景
1. **GUI 点击"刷新行情/资产"** → 立即从 `daily_data.db` 同步最新价
2. **启动时自动同步**（如果 positions 非空）

### 5.2 同步流程
```
positions.ts_code 列表 → DailyDataManager.get_latest_prices() → 
update_prices_bulk() → 计算 pnl/pnl_pct → 写入 positions
```

### 5.3 数据源
- **行情数据**：`daily_data.db` 的 `daily_trade` 表（由 tushare 每日下载）
- **最新日期**：取每个股票的最大 `trade_date`
- **无行情处理**：如果某股票在 daily_trade 中找不到，`current_price` 保持为 `NULL`

---

## 六、🎯 成本价与现价的差异

### 6.1 为什么成本价不是第一笔买入价？
- 多次买入时，成本价 = **加权平均成本**（含手续费）
- 部分卖出时，成本价 = **剩余持仓的加权成本**（按比例减少总成本）

### 6.2 举例：鼎通科技
```
3月19日：买入 700 股 @ 151.37，成本 106,005.79
4月3日：卖出 200 股 @ 147.27
剩余 500 股的成本 = 106,005.79 × (500/700) = 75,718.42 ÷ 500 = 151.437
```

---

## 七、⚠️ 已知限制与注意事项

### 7.1 路径依赖（已修复）
- **旧版本**：使用相对路径 `'database/xxx.db'`，在 OpenClaw 环境下会指向错误位置
- **当前版本**：所有 Manager 使用基于 `__file__` 的绝对路径，确保数据一致性

### 7.2 ts_code 格式（已统一）
- **问题**：trade_log 用 `603662`（无后缀），positions 用 `603662.SH`（有后缀）
- **修复**：rebuild 时自动补全后缀，`get_latest_prices` 统一用带后缀的代码

### 7.3 价格同步失败处理
- 如果 `daily_data.db` 无该股票行情，`current_price` 为 `NULL`
- GUI 显示时会回退到成本价（避免空白）
- 建议每日收盘后运行 `python scripts/sync_market_data.py` 更新行情

---

## 八、🔧 后台脚本说明

### 8.1 sync_market_data.py
- **功能**：从 tushare 下载当日行情，更新 `daily_data.db`
- **执行频率**：建议每个交易日 15:30 后运行（收盘后）
- **依赖**：TUSHARE_TOKEN 环境变量

### 8.2 auto_tasks.py（计划任务）
- **每周日 9:00**：自动生成周报，同步行情
- **每日 9:30**：检查持仓，生成开盘前的市场情绪简报
- **依赖**：cron 服务（OpenClaw 内置）

---

## 九、🎨 界面交互细节

### 9.1 颜色含义
- **红色**：盈利（pnl > 0）
- **绿色**：亏损（pnl < 0）
- **黑色**：持平

### 9.2 数据刷新
- **after(0) → after_idle**：避免多线程冲突（Tkinter 线程安全）
- **自动同步**：进入页面时延迟 100ms 加载（确保主循环就绪）

### 9.3 表格列
- **止损/止盈**：显示 "-" 表示未设置
- **现价**：如果为 None，显示成本价（灰色）
- **买卖日期**：买入当天显示，卖出后该记录从 positions 移除

---

## 🔑 核心文件路径参考

| 文件/目录 | 说明 |
|-----------|------|
| `database/stock_data.db` | 持仓、交易流水、现金 |
| `database/daily_data.db` | 每日行情（OHLC） |
| `config/app_config.json` | AI 配置、API Key |
| `config/app_settings.json` | 用户画像、GUI 设置 |
| `scripts/sync_market_data.py` | 行情同步脚本 |
| `output/reports/` | 分析报告输出目录 |

---

📌 **提示**：这些设定会随着版本更新而变化，请以实际代码为准。
"""

        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')

        # 底部按钮
        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="✅ 关闭", command=dialog.destroy).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="📋 复制内容", command=lambda: self.copy_to_clipboard(dialog, content)).pack(side='right', padx=5)

        dialog.update_idletasks()

    def copy_to_clipboard(self, parent, text):
        """复制说明内容到剪贴板"""
        parent.clipboard_clear()
        parent.clipboard_append(text)
        messagebox.showinfo("已复制", "说明内容已复制到剪贴板，可以粘贴到笔记软件中。")

    def save_config(self):
        new_profile = {k: v.get() for k, v in self.inputs.items()}
        self.config_manager.config["user_profile"] = new_profile
        
        try:
            # 使用全局配置管理器的保存方法
            self.config_manager.save_config()
            messagebox.showinfo("成功", "投资画像已更新，AI 诊断将采用最新标准。")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
