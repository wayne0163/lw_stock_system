# LW_Stock_system 核心功能与逻辑重建规格说明书 (V1.0)

## 1. 系统定位与核心价值
LW_Stock_system 是一个基于 **Python + SQLite3 + Tushare** 的量化投资管理与决策支持系统。其核心逻辑在于：**以交易流水为唯一真理（Ledger-based）**，通过多维财务策略筛选标的，并利用 AI 进行深度审计。

---

## 2. 系统架构与数据模型

### 2.1 数据库架构 (Multi-DB Design)
系统采用三库分离架构，以降低耦合并提高查询效率：

#### A. `stock_data.db` (业务与账本库)
*   **`positions` 表**：
    *   `ts_code` (TEXT, PK): 股票代码 (如 600519.SH)
    *   `quantity` (INTEGER): 当前持股数量
    *   `cost_price` (REAL): 摊薄后的成本价
    *   `current_price` (REAL): 最新收盘价
    *   `pnl` (REAL): 浮动盈亏额
    *   `pnl_pct` (REAL): 浮动盈亏百分比
    *   `last_updated` (TIMESTAMP): 最后更新时间
*   **`trade_log` 表 (核心流水)**：
    *   `ts_code` (TEXT), `trade_type` (BUY/SELL), `quantity` (INTEGER), `price` (REAL), `amount` (REAL), `transaction_cost` (REAL), `post_balance` (REAL), `trade_date` (DATE)
*   **`watchlist` 表**：记录自选股及其加入理由。

#### B. `financial_data.db` (财务指标库)
*   存储个股近 10 年的核心财务摘要（营收、净利、ROE、负债率、现金流等）。
*   数据来源：Tushare `fina_indicator` 和 `income` 接口。

#### C. `daily_data.db` (行情库)
*   存储日线行情数据（开高低收、成交量、换手率）。

---

## 3. 核心业务逻辑模块

### 3.1 账本一致性算法 (`PositionManager`)
*   **流水驱动原则**：`positions` 表仅作为缓存，所有数据必须能通过 `trade_log` 完整重建。
*   **成本计算模型**：
    *   买入：`(旧总量 * 旧成本 + 新买额 + 佣金) / 新总量`
    *   卖出：仅减少 `quantity`，不改变 `cost_price`（除非清仓）。
*   **重建功能**：`rebuild_positions_from_logs()` 必须能够按时间顺序回溯 `trade_log`，模拟每笔交易以修复可能的数据偏差。

### 3.2 动态策略引擎 (`StrategyManager`)
*   **JSON 配置化**：策略逻辑不写死，通过 `config/strategies/*.json` 定义。
*   **链式过滤逻辑**：
    1.  **硬性过滤**：剔除 ST、退市、上市未满一年的新股。
    2.  **量价过滤**：支持 MA 均线斜率、成交量异动、相对强度 (RSI) 计算。
    3.  **财务过滤**：支持 ROE 连续三年增长、经营现金流为正等指标。

### 3.3 动态止盈止损管理器 (`StopLossProfitManager`)

#### 核心设计理念
面向成长股量身定制，遵循"截断亏损，让利润奔跑"原则。系统自动跟踪持仓最高价，表格直接显示各策略的当前触发价格。

#### 支持策略类型

**止损策略（本金保护，三选一）**：
| 类型 | 算法 | 默认参数 | 适用场景 |
|------|------|---------|---------|
| **fixed** ⭐默认 | 当前价 < 成本价 × (1 - 比例) | 8% | 通用严格风控，逻辑清晰（威廉·欧奈尔法则） |
| **trailing** | 当前价 < 最高价 × (1 - 比例) | 20%，strict模式 | 已盈利持仓，让利润奔跑 |
| **breakeven** | 未激活：固定比例 / 已激活：成本价 | 初始8%，激活10% | 先求保本，再求利润 |

**止盈策略（利润锁定，三选一）**：
| 类型 | 算法 | 默认参数 | 适用场景 |
|------|------|---------|---------|
| **trailing** ⭐默认 | 当前价 < 最高价 × (1 - 比例) | 15% | 主升浪中让利润奔跑 |
| **scale** | 三级阶梯止盈 | +20%/+40%/+60% | 不确定涨幅，分批锁定 |
| **target** | 当前价 >= 目标价 | 手动设置 | 有明确估值目标 |

**移动模式**：
| 模式 | 说明 |
|------|------|
| strict | 回落到触发价立即执行 |
| loose | 触发价额外下移2%，减少震荡被震出 |

#### 数据库字段（`positions`表 v2 策略字段）
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `stop_loss_type` | TEXT | 'fixed' | 止损类型: fixed/trailing/breakeven |
| `stop_loss_value` | REAL | 0.08 | 止损比例（8% = 成本或最高点回落8%） |
| `profit_exit_type` | TEXT | 'trailing' | 止盈类型: target/trailing/scale |
| `profit_exit_value` | REAL | 0.15 | 移动止盈比例（从最高点回落15%） |
| `trailing_mode` | TEXT | 'strict' | 移动模式: strict(严格)/loose(宽松2%容忍) |
| `highest_since_buy` | REAL | 0 | 买入后最高价（自动跟踪） |
| `breakeven_activate` | REAL | 0.10 | 保本激活涨幅（最高价超过成本10%后移止损至成本） |
| `scale_profit_1` | REAL | 0.20 | 分批止盈第一阶梯（+20%） |
| `scale_profit_2` | REAL | 0.40 | 分批止盈第二阶梯（+40%） |
| `scale_profit_3` | REAL | 0.60 | 分批止盈第三阶梯（+60%后高点回落清仓） |
| `scale_ratio_1` | REAL | 0.33 | 第一批卖出比例（1/3） |
| `scale_ratio_2` | REAL | 0.33 | 第二批卖出比例（1/3） |
| `target_price` | REAL | NULL | 目标价止盈的目标价格 |

#### 策略算法详解

**止损算法**：
```
fixed:     trigger = cost × (1 - sl_pct)
           当前价 ≤ trigger → STOP_LOSS

trailing:  trigger = highest × (1 - sl_pct)
           loose模式额外下移2%: trigger -= highest × 0.02
           当前价 ≤ trigger → STOP_LOSS

breakeven: 若 highest ≥ cost × (1 + activate_pct) → 已激活，trigger = cost
           若未激活 → trigger = cost × (1 - sl_pct)
           当前价 ≤ trigger → STOP_LOSS
```

**止盈算法**：
```
target:    trigger = target_price
           当前价 ≥ trigger → SELL_ALL

trailing:  trigger = highest × (1 - pe_pct)
           当前价 ≤ trigger → SELL_ALL

scale:     s1/s2/s3 = 各阶梯涨幅，r1/r2 = 各批卖出比例
           盈利 ≥ s3 → 第3批从高点回落8%清仓 → SELL_ALL
           盈利 ≥ s2 → 第2批触发 → SELL_PART 建议卖 r2
           盈利 ≥ s1 → 第1批触发 → SELL_PART 建议卖 r1
```

**检查顺序**：`check_position()`
1. 更新 `highest_since_buy`（仅向上移动）
2. 止损优先：亏损时不考虑止盈
3. 止盈其次：盈利时考虑兑现
4. 返回 {action, summary, trigger_price}

#### GUI交互
*   右键菜单「修改止盈止损策略」弹出对话框
*   策略类型切换时动态显示/隐藏对应参数
*   持仓表格"止损价""止盈价"列直接显示当前触发价
*   鼠标悬停显示完整策略详情 tooltip

### 3.5 K线图深度分析组件 (`stock_chart.py`)
*   **触发方式**：在「全部股票」「智能筛选」「持仓管理」页面中，双击或右键菜单点击查看K线图。
*   **数据源**：从 `daily_data.db` 的 `daily_trade` 表获取最近 350 个交易日数据。
*   **图表内容**：
    *   **K线图**：日本蜡烛图，红涨绿跌（符合A股习惯）。
    *   **成交量**：K线下方成交量柱状图。
    *   **RSI 指标**：14日RSI线（蓝色）+ 6日平滑均线（橙色）+ 超买线70（红色虚线）+ 超卖线30（绿色虚线）。
*   **技术实现**：
    *   基于 `mplfinance` + `matplotlib`，嵌入 Tkinter 窗口。
    *   后台线程加载数据，主线程绘图，界面不卡顿。
    *   支持 matplotlib NavigationToolbar（缩放、平移、保存图片）。
*   **窗口规格**：1000x700，最小 800x550，响应式缩放。

### 3.4 数据同步逻辑 (`StockManager`)
*   **幂等性更新**：每次同步前检查数据库中已有的最新日期，仅抓取缺失的增量数据。
*   **容错处理**：Tushare 接口有频次限制，必须实现指数退避重试逻辑。

---

## 4. AI 审计与分析工作流

系统集成了“AI 投资助手”，通过以下资产驱动：
1.  **分析引擎 (`Investment Analysis Engine.md`)**：定义 AI 扮演的角色、分析框架和行业判断标准。
2.  **评分系统 (`scoring_system.md`)**：定义量化指标到分值的映射逻辑。
3.  **报告模板 (`report_template.md`)**：定义 Markdown 报告的结构。

**执行流程**：
1.  从数据库提取个股 5 年财务特征 DataFrame。
2.  将 DataFrame 转换为 JSON/Markdown 表格并注入 Prompt。
3.  调用大模型（OpenAI API 或类似接口）进行文本化分析。
4.  输出最终的“深度财务分析报告”。

---

## 5. 自动化脚本与 CLI 接口
系统应支持以下命令行调用，以便于集成和定时任务：

*   `main.py --update-stocks`：更新全量 A 股列表。
*   `main.py --update-financial`：更新财务数据（通常按季报/年报频次）。
*   `main.py --update-daily`：同步最新日线数据。
*   `scripts/auto_tasks.py`：触发全自动策略扫描并发送通知。
*   `scripts/fix_positions.py`：当持仓数据异常时手动触发全量重建。

---

## 6. 给重建 AI 的提示词 (Prompt Suggestion)
> "请根据《LW_Stock_system 重建规格说明书》使用 Python 3 实现一套量化选股管理系统。
> 1. 首先实现 `core/positions.py`，确保其 `PositionManager` 能够基于 SQLite 记录买入/卖出流水，并能随时通过流水重建持仓状态。
> 2. 实现 `core/stock_manager.py` 对接 Tushare 数据源。
> 3. 系统必须保证数据存储在三个独立的 SQLite 数据库文件中（业务、财务、行情）。
> 4. 实现一个基于 JSON 配置文件驱动的选股过滤链。
> 5. 暂不需要 GUI，所有功能需通过主入口 main.py 的 CLI 标志调用。"
