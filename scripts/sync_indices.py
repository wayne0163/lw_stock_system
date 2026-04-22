
import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path

def sync_market_indices():
    # 1. 加载配置
    config_path = Path('config/app_settings.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    benchmarks = config['user_profile']['benchmarks']
    
    # 2. 获取 Tushare Token
    from core.config import Config
    token = Config().config.get('tushare_token', '')
    if not token:
        # 尝试从环境变量获取
        import os
        token = os.environ.get('TUSHARE_TOKEN', '')
    
    if not token:
        print("❌ 未发现 Tushare Token，请在设置中配置。")
        return
        
    pro = ts.pro_api(token)
    
    db_path = 'database/stock_data.db'
    conn = sqlite3.connect(db_path)
    
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
    
    print(f"开始同步指数数据: {benchmarks}...")
    
    for ts_code in benchmarks:
        try:
            # 拉取历史行情
            df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df.empty:
                print(f"⚠️ 未获取到 {ts_code} 的数据")
                continue
                
            # 格式化日期为 YYYY-MM-DD
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
            
            # 写入数据库
            for _, row in df.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO market_indices (ts_code, trade_date, close)
                    VALUES (?, ?, ?)
                """, (ts_code, row['trade_date'], row['close']))
            
            print(f"✅ 已同步 {ts_code}: {len(df)} 条记录")
        except Exception as e:
            print(f"❌ 同步 {ts_code} 失败: {e}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    sync_market_indices()
