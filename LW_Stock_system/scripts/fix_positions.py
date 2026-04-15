#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键修复 positions 表：根据 trade_log 全量重建，确保与交易流水一致
用法：python fix_positions.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from core.positions import PositionManager

def main():
    print("🔧 开始修复 positions 表...")
    pm = PositionManager()
    
    # 重建前检查
    print("\n📊 重建前 positions 数据：")
    df_before = pm.get_all()
    if df_before.empty:
        print("  (空)")
    else:
        for _, r in df_before.iterrows():
            print(f"  {r['ts_code']} {r['name']} 持仓 {r['quantity']} 股")
    
    # 执行重建
    print("\n⚙️  正在根据 trade_log 重建 positions...")
    inserted = pm.rebuild_positions_from_logs()
    print(f"✅ 重建完成，当前有效持仓 {inserted} 条")
    
    # 重建后检查
    print("\n📊 重建后 positions 数据：")
    df_after = pm.get_all()
    if df_after.empty:
        print("  (空)")
    else:
        for _, r in df_after.iterrows():
            print(f"  {r['ts_code']} {r['name']} 持仓 {r['quantity']} 股")
    
    # 验证一致性
    print("\n🔍 一致性验证：")
    import sqlite3
    conn = sqlite3.connect(pm.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT ts_code FROM trade_log WHERE trade_type IN ('BUY', 'SELL')")
    codes = [r[0] for r in cursor.fetchall()]
    
    all_ok = True
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
        
        if net_qty == pos_qty:
            print(f"  ✅ {code}: 理论={net_qty}, 实际={pos_qty}")
        else:
            print(f"  ❌ {code}: 理论={net_qty}, 实际={pos_qty} (差异 {net_qty - pos_qty})")
            all_ok = False
    
    conn.close()
    
    if all_ok:
        print("\n🎉 所有持仓已一致！修复完成。")
    else:
        print("\n⚠️  仍有不一致，请检查 trade_log 数据是否完整。")
    
    print(f"\n💰 当前现金余额：{pm.get_cash():,.2f} 元")
    summary = pm.get_position_summary()
    print(f"📈 总资产：{summary['total_assets']:,.2f} 元 (盈亏 {summary['account_pnl']:+,.2f})")

if __name__ == "__main__":
    main()
