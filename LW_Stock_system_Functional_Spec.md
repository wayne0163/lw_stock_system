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

### 3.3 数据同步逻辑 (`StockManager`)
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
