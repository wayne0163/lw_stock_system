
import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime

# 确保路径正确
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.positions import PositionManager
from core.daily_data import DailyDataManager

def test_price_sync():
    # 1. 设置测试环境
    test_stock_db = 'database/stock_data.db'
    test_daily_db = 'database/daily_data.db'
    
    pm = PositionManager(db_path=test_stock_db)
    dm = DailyDataManager(db_path=test_daily_db)
    
    # 模拟数据
    ts_code = '000001.SZ'
    name = '平安银行'
    cost_price = 10.0
    quantity = 100
    current_market_price = 15.0
    
    print(f"--- 测试开始: {ts_code} ---")
    
    # 2. 清理并准备测试数据
    with sqlite3.connect(test_stock_db) as conn:
        conn.execute("DELETE FROM positions WHERE ts_code = ?", (ts_code,))
        conn.execute("UPDATE assets SET cash = 100000 WHERE id = 1")
        conn.commit()
    
    with sqlite3.connect(test_daily_db) as conn:
        conn.execute("DELETE FROM daily_trade WHERE ts_code = ?", (ts_code,))
        conn.execute("""
            INSERT INTO daily_trade (ts_code, trade_date, close, pct_chg)
            VALUES (?, ?, ?, ?)
        """, (ts_code, '20260402', current_market_price, 2.5))
        conn.commit()
        
    # 3. 添加持仓 (初始 current_price 为空或由 add_position 设置)
    print("正在添加持仓...")
    pm.add_position(ts_code, name, quantity, cost_price)
    
    # 检查初始状态
    pos_before = pm.get_all()
    curr_before = pos_before[pos_before['ts_code'] == ts_code]['current_price'].iloc[0]
    print(f"同步前现价: {curr_before}")
    
    # 4. 执行同步
    print("执行同步...")
    price_dict = dm.get_latest_prices([ts_code])
    print(f"从行情库获取到最新价: {price_dict}")
    pm.update_prices_bulk(price_dict)
    
    # 5. 验证结果
    pos_after = pm.get_all()
    curr_after = pos_after[pos_after['ts_code'] == ts_code]['current_price'].iloc[0]
    pnl_after = pos_after[pos_after['ts_code'] == ts_code]['pnl'].iloc[0]
    pnl_pct_after = pos_after[pos_after['ts_code'] == ts_code]['pnl_pct'].iloc[0]
    
    print(f"同步后现价: {curr_after}")
    print(f"计算所得盈亏: {pnl_after}")
    print(f"计算所得盈亏率: {pnl_pct_after}%")
    
    if curr_after == current_market_price:
        print("✅ 现价同步成功！")
    else:
        print("❌ 现价同步失败！")
        
    expected_pnl = (current_market_price - cost_price) * quantity
    if pnl_after == expected_pnl:
        print("✅ 盈亏计算成功！")
    else:
        print("❌ 盈亏计算失败！")

if __name__ == "__main__":
    test_price_sync()
