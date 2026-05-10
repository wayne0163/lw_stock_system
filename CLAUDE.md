# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python main.py                              # Start GUI
python main.py --test                       # Run import self-check
python scripts/test_all.py                  # Run module import tests
python scripts/fix_positions.py             # Rebuild positions table from trade_log
python scripts/auto_tasks.py --help         # See all CLI automation options
python scripts/auto_tasks.py --sync-market  # Sync full market daily data from Tushare
python scripts/auto_tasks.py --ai-audit     # Run full portfolio AI audit
python scripts/gen_stock_report.py <ts_code>  # Generate deep fundamental report for one stock
```

## Architecture

### Three-Layer Design

**Core Data Layer** (`core/`) — stateless managers, each backed by its own SQLite DB:
- `stock_manager.py` — `StockManager`: `stocks_basic` table (TS code, name, industry, list date). Fetches from Tushare `stock_basic` API.
- `financial_data.py` — `FinancialDataManager`: `financial_indicators` table (ROE, revenue growth, gross margin, etc.). Dynamic column extension (auto-ALTER-TABLE). Uses Tushare `fina_indicator_vip`.
- `daily_data.py` — `DailyDataManager`: `daily_trade` table (OHLCV). Batch download by trade date, missing-date auto-replenish.
- `positions.py` — Two classes: `PositionManager` (trade execution, cost-basis tracking via trade_log ledger) and `StopLossProfitManager` (per-position stop-loss/take-profit strategy engine with 3+3 strategy types).
- `indicators.py` — `Indicators`: stateless Pandas-based technical calculations (RSI, MA, 52-week high distance).
- `strategy.py` — `StrategyManager`: JSON-configurable screening filter chain.
- `config.py` — `Config`: centralized config from `config/` JSON files, Tushare token, AI settings.
- `watchlist.py` — `WatchlistManager`: watchlist CRUD with group support.

**GUI Layer** (`gui/`) — Tkinter/ttk with custom warm-gold theme:
- `main_window.py` — `MainWindow`: root Tk app, navigation + Notebook layout, status bar, menu bar.
- `navigation.py` — `NavigationPanel`: left sidebar with icon+title+description nav items and status panel.
- `theme.py` — `Colors`, `Fonts`, `Theme`: warm-gold light theme (default) and dark mode backup.
- `tabs/position_tab.py` — Positions dashboard with asset cards, P&L tracking, stop-loss/profit-taking strategy dialog, hover tooltips.
- `tabs/filter_tab.py` — Financial + technical screening UI with scoring system.
- `tabs/watchlist_tab.py` — Full market stock browser with star marking and sorting.
- Other tabs: `strategy_tab.py`, `financial_tab.py`, `reports_tab.py`, `settings_tab.py`.
- `widgets/filter_panel.py` — Reusable multi-tab filter widget.
- `utils.py` — `center_window()`, `generate_stock_report()` threading wrapper.
- `stock_chart.py` — `show_stock_chart()`: embedded candlestick chart dialog built on mplfinance + matplotlib. Shows 300-day K-line, volume bars, and RSI(14) with overbought/oversold lines.

**Scripts Layer** (`scripts/`) — CLI/cron-friendly automation:
- `auto_tasks.py` — Unified CLI gateway: `--add-watchlist`, `--gen-reports`, `--ai-audit`, `--sync-market`.
- `gen_stock_report.py` — Standalone fundamental analysis report generator.
- `prepare_ai_analysis.py` — Portfolio-level AI audit report.
- `fix_positions.py` — Rebuild positions from trade_log (for data inconsistency repair).

### Database — Three Separate SQLite Files (in `database/`)

| File | Key Tables | Purpose |
|------|-----------|---------|
| `stock_data.db` | `positions`, `trade_log`, `stocks_basic`, `assets`, `watchlist` | Business + ledger |
| `financial_data.db` | `financial_indicators` | Fundamental data |
| `daily_data.db` | `daily_trade` | Market data |

### Key Design Principles

- **Ledger-based accounting**: `trade_log` is the single source of truth. `positions` is rebuilt from logs via `rebuild_positions_from_logs()`. Never modify `positions` directly.
- **Raw field passthrough**: Financial data stored as-is from Tushare. No transformation or interpretation in the data layer.
- **Stop-loss takes priority**: In `StopLossProfitManager.check_position()`, stop-loss is checked before take-profit. A losing position never triggers profit exit.
- **JSON-driven strategies**: Screening conditions in `config/strategies/*.json` define filter chains without code changes.
- **Thread safety**: GUI uses `threading.Thread` + `after()` callbacks for data operations to keep UI responsive.

### Stop-Loss / Take-Profit Strategy System

See `StopLossProfitManager` in `core/positions.py` lines 7-361.

Types:
- Stop loss: `fixed` (fixed % from cost), `trailing` (from highest high), `breakeven` (fixed → cost after profit target hit)
- Take profit: `target` (fixed price), `trailing` (from peak), `scale` (tiered 20/40/60% with partial sells)
- Trailing modes: `strict` (exact trigger) / `loose` (2% extra buffer)

Database columns for v2 strategy fields are auto-migrated via `ALTER TABLE ADD COLUMN` in `PositionManager.init_db()`.
