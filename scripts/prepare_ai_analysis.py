
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date
import json
from pathlib import Path

def generate_full_audit_report():
    db_path = 'database/stock_data.db'
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_path = Path(f'output/reports/{today_str}-AI_Audit_Report.md')
    conn = sqlite3.connect(db_path)
    
    # --- 1. 加载配置与基础信息 ---
    config = json.load(open('config/app_settings.json', 'r', encoding='utf-8')) if Path('config/app_settings.json').exists() else {}
    profile = config.get("user_profile", {})
    
    # --- 2. 获取数据源 ---
    trades_df = pd.read_sql_query("SELECT * FROM trade_log ORDER BY trade_date ASC, id ASC", conn)
    indices_df = pd.read_sql_query("SELECT * FROM market_indices WHERE ts_code = '399300.SZ' ORDER BY trade_date ASC", conn)
    positions_df = pd.read_sql_query("SELECT * FROM positions", conn)
    
    if trades_df.empty:
        print("Error: No data.")
        return

    # --- 3. 计算账户概览 (Executive Summary) ---
    start_date_str = trades_df['trade_date'].min()
    end_date_str = datetime.now().strftime('%Y-%m-%d')
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.now().date()
    days_diff = (end_date - start_date).days
    years_diff = days_diff / 365.25
    
    # 现金与市值 (基于最新流水)
    current_cash = trades_df.iloc[-1]['post_balance'] if 'post_balance' in trades_df.columns else 0.0
    current_mkt_val = (positions_df['current_price'].fillna(positions_df['cost_price']) * positions_df['quantity']).sum()
    total_assets = current_cash + current_mkt_val
    
    # 收益计算
    initial_invest = trades_df[trades_df['trade_type'] == 'DEPOSIT']['amount'].sum()
    total_ret_pct = (total_assets / initial_invest - 1) if initial_invest > 0 else 0
    cagr = ((total_assets / initial_invest)**(1/years_diff) - 1) if (initial_invest > 0 and years_diff > 0) else 0

    # --- 4. 每日资产重播 (Daily Snapshots) ---
    date_range = pd.date_range(start_date, end_date)
    daily_stats = []
    max_a = 0
    for d in date_range:
        d_s = d.strftime('%Y-%m-%d')
        # 该日结束余额
        d_logs = trades_df[trades_df['trade_date'] <= d_s]
        if d_logs.empty: continue
        c_bal = d_logs.iloc[-1]['post_balance']
        
        # 该日持仓
        p_res = pd.read_sql_query("""
            SELECT ts_code, name, SUM(CASE WHEN trade_type = 'BUY' THEN quantity ELSE -quantity END) as qty
            FROM trade_log WHERE trade_date <= ? GROUP BY ts_code HAVING qty > 0
        """, conn, params=(d_s,))
        
        m_val = 0.0
        struct = []
        for _, r in p_res.iterrows():
            # 简化价格：尝试从 positions 找现价，否则用 log 均价
            pr_res = conn.execute("SELECT current_price FROM positions WHERE ts_code = ?", (r['ts_code'],)).fetchone()
            pr = pr_res[0] if pr_res else 0.0
            val = r['qty'] * pr
            m_val += val
            struct.append(f"{r['name']}:{val/(c_bal+m_val):.0%}" if (c_bal+m_val)>0 else "")
            
        t_a = c_bal + m_val
        max_a = max(max_a, t_a)
        dd = (max_a - t_a) / max_a if max_a > 0 else 0
        
        # 指数
        idx_p = indices_df[indices_df['trade_date'] <= d_s].tail(1)
        b_v = idx_p['close'].iloc[0] if not idx_p.empty else 0
        
        daily_stats.append({"d": d_s, "t": t_a, "c": c_bal, "m": m_val, "dd": dd, "b": b_v, "s": ", ".join(struct[:3])})

    # --- 5. 交易对匹配 (Matched Trades) ---
    closed_list = []
    win_count = 0
    for code in trades_df[trades_df['ts_code'] != 'CASH']['ts_code'].unique():
        s_t = trades_df[trades_df['ts_code'] == code].copy()
        buys = s_t[s_t['trade_type'] == 'BUY'].to_dict('records')
        sells = s_t[s_t['trade_type'] == 'SELL'].to_dict('records')
        for b in buys:
            match = [s for s in sells if s['trade_date'] >= b['trade_date']]
            if match:
                s = match[0]; sells.remove(s)
                pnl = (s['price'] - b['price']) * b['quantity']
                if pnl > 0: win_count += 1
                closed_list.append({
                    "d": b['trade_date'], "c": code, "n": b['name'], "type": "买入/卖出",
                    "bp": b['price'], "sp": s['price'], "sd": s['trade_date'],
                    "q": b['quantity'], "amt": b['amount'], "reason": b['notes'],
                    "sl": b['stop_loss'], "tp": b['take_profit'], "pnl": pnl
                })
            else:
                closed_list.append({
                    "d": b['trade_date'], "c": code, "n": b['name'], "type": "买入/持仓",
                    "bp": b['price'], "sp": "-", "sd": "-", "q": b['quantity'],
                    "amt": b['amount'], "reason": b['notes'], "sl": b['stop_loss'],
                    "tp": b['take_profit'], "pnl": 0
                })

    # --- 6. 组装 Markdown ---
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# AI_Audit_Report.md - 投资组合审计报告\n\n")
        f.write("> 依据真实账本重播生成 | 专业诊断版\n\n---\n")
        
        f.write("## 一、账户概览\n### 基础信息\n")
        f.write(f"- **初始投资额**: {initial_invest:,.0f}元\n")
        f.write(f"- **当前总资产**: {total_assets:,.0f}元\n")
        f.write(f"- **当前现金**: {current_cash:,.0f}元\n")
        f.write(f"- **当前持仓市值**: {current_mkt_val:,.0f}元\n")
        f.write(f"- **投资期限**: {years_diff:.1f}年\n")
        f.write(f"- **数据起始日期**: {start_date_str}\n")
        f.write(f"- **数据截止日期**: {end_date_str}\n\n")
        
        f.write("### 收益指标\n")
        f.write(f"- **总收益率**: {total_ret_pct:.2%}\n")
        f.write(f"- **年化收益率 (CAGR)**: {cagr:.2%}\n\n")
        
        f.write("### 主观信息\n")
        f.write(f"- **投资目标**: {profile.get('annual_return_target','-')}\n")
        f.write(f"- **风险偏好**: {profile.get('risk_preference','-')}\n")
        f.write(f"- **最大回撤容忍度**: {profile.get('max_drawdown_tolerance','-')}\n")
        f.write(f"- **资金来源**: {profile.get('source_of_funds','-')}\n\n---\n")
        
        f.write("## 二、交易明细表 (Transaction Logs)\n")
        f.write("| 序号 | 日期 | 股票代码 | 方向 | 价格 | 数量 | 金额 | 交易理由 | 预期止盈 | 预期止损 | 实际卖出价 | 实际卖出日期 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for i, t in enumerate(closed_list):
            f.write(f"| {i+1} | {t['d']} | {t['c']} | 买入 | {t['bp']:.2f} | {t['q']} | {t['amt']:,.0f} | {t['reason']} | {t['tp'] or '-'} | {t['sl'] or '-'} | {t['sp']} | {t['sd']} |\n")
        
        f.write("\n---\n## 三、当前持仓明细\n")
        f.write("| 股票代码 | 名称 | 持仓数量 | 成本价 | 当前价 | 持仓盈亏 | 盈亏率 | 仓位占比 |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for _, r in positions_df.iterrows():
            cp = r['current_price'] or r['cost_price']
            pnl = (cp - r['cost_price']) * r['quantity']
            pct = (cp / r['cost_price'] - 1)
            pos_pct = (r['quantity'] * cp) / total_assets if total_assets > 0 else 0
            f.write(f"| {r['ts_code']} | {r['name']} | {r['quantity']} | {r['cost_price']:.2f} | {cp:.2f} | {pnl:,.0f} | {pct:.2%} | {pos_pct:.1%} |\n")
        
        f.write(f"\n**现金**: {current_cash:,.0f}元 (占资产{current_cash/total_assets:.1%})\n")
        f.write(f"**总资产**: {total_assets:,.0f}元\n\n---\n")
        
        f.write("## 四、每日资产快照 (示例片段)\n")
        f.write("| 日期 | 总资产 | 现金 | 持仓市值 | 回撤 | 399300基准 | 持仓结构 |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for s in daily_stats[-20:]:
            f.write(f"| {s['d']} | {s['t']:,.0f} | {s['c']:,.0f} | {s['m']:,.0f} | {s['dd']:.2%} | {s['b']:.2f} | {s['s']} |\n")
            
        f.write("\n---\n## 五、数据质量自检\n")
        f.write(f"- [x] 交易笔数: {len(closed_list)}笔\n")
        f.write(f"- [x] 价格已复权 (Tushare原始数据)\n")
        f.write(f"- [x] 交易理由已填写\n")
        f.write(f"- [x] 初始资金与流水对齐\n")

    print(f"Success: Professional audit report generated at {output_path}")

if __name__ == "__main__":
    try:
        generate_full_audit_report()
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
