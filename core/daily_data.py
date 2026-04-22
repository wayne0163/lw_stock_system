# core/daily_data.py
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, time
import logging
import time as sleep_time

logger = logging.getLogger(__name__)

class DailyDataManager:
    """管理股票每日交易数据 (OHLC, Volume, etc.)"""
    
    def __init__(self, db_path=None):
        # 基于当前文件位置确定项目根目录，避免相对路径依赖 cwd
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'daily_data.db'
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """初始化每日交易数据表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_trade (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    pre_close REAL,
                    change REAL,
                    pct_chg REAL,
                    vol REAL,
                    amount REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ts_code, trade_date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts_trade_date ON daily_trade(ts_code, trade_date)")
            conn.commit()

    def get_latest_date_in_db(self, ts_code):
        """获取数据库中某只股票最后一条交易记录的日期"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT MAX(trade_date) FROM daily_trade WHERE ts_code = ?", (ts_code,))
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def get_target_end_date(self):
        """
        计算目标截止日期：
        16:30 以后视为今天已收盘，可以尝试下载今天的数据；
        否则截止到昨天。
        """
        now = datetime.now()
        market_close_buffer = time(16, 30)
        
        if now.time() > market_close_buffer:
            return now.strftime('%Y%m%d')
        else:
            # 简单处理为昨天（Tushare 会自动过滤掉非交易日的请求）
            from datetime import timedelta
            return (now - timedelta(days=1)).strftime('%Y%m%d')

    def clear_all_data(self):
        """彻底清空所有行情数据 (谨慎使用)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM daily_trade")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='daily_trade'")
            conn.commit()
            logger.info("💥 已彻底清空 daily_trade 表数据")

    def sync_market_data(self, token, start_date="20250101"):
        """
        按日期同步全市场行情（比按股票代码同步快得多）
        """
        import tushare as ts
        pro = ts.pro_api(token)
        
        target_end = self.get_target_end_date()
        
        # 1. 获取交易日历，确定需要下载的日期范围
        try:
            df_cal = pro.trade_cal(exchange='', start_date=start_date, end_date=target_end)
            # 仅保留开市日期
            trade_days = df_cal[df_cal['is_open'] == 1]['cal_date'].tolist()
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return 0
            
        # 2. 检查数据库中已有的日期
        # 优化：不仅检查日期是否存在，还要检查该日期的数据量是否足够（防止之前因断网等导致的残缺数据）
        with sqlite3.connect(self.db_path) as conn:
            day_counts = pd.read_sql_query(
                "SELECT trade_date, COUNT(*) as cnt FROM daily_trade GROUP BY trade_date", 
                conn
            )
            # 只有记录数超过 4000 条的日期才被视为完整
            existing_days = day_counts[day_counts['cnt'] > 4000]['trade_date'].tolist()
            
        missing_days = [d for d in trade_days if d not in existing_days]
        if not missing_days:
            logger.info("全市场行情已是最新且数据完整，无需更新。")
            return 0
            
        logger.info(f"检测到缺失或不完整交易日共 {len(missing_days)} 天，开始全量重补/更新...")
        
        total_saved = 0
        for day in sorted(missing_days):
            logger.info(f"正在下载 {day} 的全市场行情 (Batch Mode)...")
            try:
                # 核心：批量获取全市场数据
                df = pro.daily(trade_date=day)
                if not df.empty:
                    saved = self._save_dataframe(df)
                    total_saved += saved
                    logger.info(f"  ✓ {day}: 成功保存 {saved} 条记录")
                else:
                    logger.warning(f"  ⚠️ {day}: Tushare 未返回任何行情数据")
                
                # 限流处理：全量数据请求较重，建议稍微拉长间隔
                sleep_time.sleep(0.8)
            except Exception as e:
                logger.error(f"  ❌ {day} 下载失败: {e}")
                # 如果触发频率限制，多等一会儿
                if "每分钟" in str(e) or "接口压力" in str(e):
                    sleep_time.sleep(5)
                
        return total_saved

    def sync_daily_data(self, token, ts_codes, start_date_default="20250327"):
        """
        增量同步行情数据
        """
        import tushare as ts
        pro = ts.pro_api(token)
        
        target_end = self.get_target_end_date()
        total_new_records = 0
        
        logger.info(f"开始同步行情：目标截止日期 {target_end}")
        
        for code in ts_codes:
            # 1. 查找本地最后日期
            last_date = self.get_latest_date_in_db(code)
            
            # 2. 确定本次下载的起始日期
            if last_date:
                # 如果本地已有数据，从最后一日的后一天开始（Tushare start_date 是包含关系）
                # 为了简单和安全，我们直接从 last_date 开始，INSERT OR REPLACE 会处理重复
                fetch_start = last_date
            else:
                fetch_start = start_date_default
            
            if fetch_start >= target_end:
                logger.info(f"  - {code}: 已是最新 (Last: {last_date})")
                continue
                
            logger.info(f"  - {code}: 正在同步 {fetch_start} -> {target_end}...")
            
            try:
                # 3. 调用 API (Tushare 积分足够建议批量下载，此处为自选股设计)
                df = pro.daily(ts_code=code, start_date=fetch_start, end_date=target_end)
                
                if not df.empty:
                    saved = self._save_dataframe(df)
                    total_new_records += saved
                    logger.info(f"    ✓ 成功更新 {saved} 条记录")
                
                # 频率限制（每分钟 200 次左右，视积分而定）
                sleep_time.sleep(0.2) 
                
            except Exception as e:
                logger.error(f"  ✗ {code} 同步失败: {e}")
                
        return total_new_records

    def _save_dataframe(self, df):
        """保存 DataFrame 到数据库"""
        if df.empty:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('daily_trade_temp', conn, if_exists='replace', index=False)
            sql = """
                INSERT OR REPLACE INTO daily_trade 
                (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
                SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount 
                FROM daily_trade_temp
            """
            cursor = conn.execute(sql)
            conn.execute("DROP TABLE daily_trade_temp")
            conn.commit()
            return cursor.rowcount

    def get_all_daily_trade(self, ts_codes, limit=100):
        """批量获取多支股票的交易数据"""
        if not ts_codes:
            return pd.DataFrame()
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ','.join(['?'] * len(ts_codes))
            sql = f"""
                SELECT ts_code, trade_date, open, high, low, close, vol, pct_chg
                FROM daily_trade 
                WHERE ts_code IN ({placeholders})
                ORDER BY ts_code, trade_date ASC
            """
            df = pd.read_sql_query(sql, conn, params=ts_codes)
            return df

    def get_latest_price(self, ts_code):
        """获取最新收盘价和涨跌幅"""
        with sqlite3.connect(self.db_path) as conn:
            sql = "SELECT close, pct_chg, trade_date FROM daily_trade WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1"
            cursor = conn.execute(sql, (ts_code,))
            row = cursor.fetchone()
            if row:
                return {"price": row[0], "pct_chg": row[1], "date": row[2]}
            return None

    def get_latest_prices(self, ts_codes):
        """批量获取多只股票的最新收盘价"""
        if not ts_codes:
            return {}
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ','.join(['?'] * len(ts_codes))
            # 使用子查询获取每个代码的最新日期对应的价格
            sql = f"""
                SELECT ts_code, close 
                FROM daily_trade 
                WHERE (ts_code, trade_date) IN (
                    SELECT ts_code, MAX(trade_date) 
                    FROM daily_trade 
                    WHERE ts_code IN ({placeholders})
                    GROUP BY ts_code
                )
            """
            df = pd.read_sql_query(sql, conn, params=ts_codes)
            return dict(zip(df['ts_code'], df['close']))

    def get_overall_latest_date(self):
        """获取数据库中所有股票里最晚的一个交易日期"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT MAX(trade_date) FROM daily_trade")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
