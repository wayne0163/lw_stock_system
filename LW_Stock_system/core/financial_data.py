# core/financial_data.py
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialDataManager:
    def __init__(self, db_path=None):
        # 基于当前文件位置确定项目根目录，避免相对路径依赖 cwd
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'financial_data.db'
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """初始化数据库表 (确保核心索引列存在，支持动态扩展)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    ann_date DATE,
                    -- 定义核心索引列，确保基本筛选性能
                    roe_dt REAL,
                    roic REAL,
                    tr_yoy REAL,
                    dt_netprofit_yoy REAL,      -- 扣非净利增速
                    grossprofit_margin REAL,    -- 销售毛利率
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ts_code, period)
                )
            """)
            
            # 基础索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts_period ON financial_indicators(ts_code, period)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_period ON financial_indicators(period)")
            conn.commit()
            logger.info(f"财务数据库初始化完成 (支持全量字段保存): {self.db_path}")

    def update_latest(self, token):
        """同步最新财报"""
        import tushare as ts
        pro = ts.pro_api(token)
        now = datetime.now()
        Y = now.year
        mmdd = int(now.strftime('%m%d'))
        
        target_periods = set()
        if 301 <= mmdd <= 531: target_periods.add(f"{Y-1}1231")
        if 415 <= mmdd <= 615: target_periods.add(f"{Y}0331")
        if 715 <= mmdd <= 915: target_periods.add(f"{Y}0630")
        if 1015 <= mmdd <= 1215: target_periods.add(f"{Y}0930")
        
        if not target_periods:
            target_periods.add(f"{Y-1}0930")
            target_periods.add(f"{Y-1}1231")
            
        logger.info(f"📅 财务同步窗口: {list(target_periods)}")
        
        total_saved = 0
        for period in sorted(list(target_periods), reverse=True):
            try:
                # 获取全量指标 (VIP 接口返回约 100+ 字段)
                df = pro.fina_indicator_vip(period=period)
                if df is not None and not df.empty:
                    if 'period' not in df.columns: df['period'] = period
                    if 'ann_date' not in df.columns:
                        df['ann_date'] = df['end_date'] if 'end_date' in df.columns else period
                    
                    saved = self._save_dataframe(df)
                    total_saved += saved
                    logger.info(f"  ✓ {period}: 成功同步 {saved} 条指标")
                else:
                    logger.info(f"  ℹ️ {period}: 暂无数据")
            except Exception as e:
                logger.error(f"  ❌ {period} 同步失败: {e}")
        return total_saved

    def _save_dataframe(self, df):
        """全量保存数据，支持数据库表结构自动扩展"""
        if df.empty: return 0
        
        # 数据清理：确保 period 和 ann_date 格式统一
        if 'period' not in df.columns and 'end_date' in df.columns:
            df['period'] = df['end_date']

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 动态检查并扩展表结构
            cursor.execute("PRAGMA table_info(financial_indicators)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            for col in df.columns:
                if col not in existing_cols and col != 'id':
                    # 根据数据类型判断
                    dtype = "REAL" if pd.api.types.is_numeric_dtype(df[col]) else "TEXT"
                    try:
                        cursor.execute(f"ALTER TABLE financial_indicators ADD COLUMN {col} {dtype}")
                        logger.info(f"🛠️ 数据库自动扩展新列: {col} ({dtype})")
                    except Exception as e:
                        logger.warning(f"扩展列 {col} 失败: {e}")
            
            # 2. 使用临时表高效合并数据
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df['updated_at'] = now_str
            
            df.to_sql('financial_temp', conn, if_exists='replace', index=False)
            
            # 获取交集列名，防止因表结构变更导致的插入失败
            cursor.execute("PRAGMA table_info(financial_indicators)")
            final_db_cols = {row[1] for row in cursor.fetchall() if row[1] != 'id'}
            common_cols = [c for c in df.columns if c in final_db_cols]
            
            cols_str = ",".join(common_cols)
            sql = f"""
                INSERT OR REPLACE INTO financial_indicators ({cols_str})
                SELECT {cols_str} FROM financial_temp
            """
            cursor.execute(sql)
            cursor.execute("DROP TABLE financial_temp")
            conn.commit()
            return len(df)

    def screen_stocks(self, filters, min_satisfied=1, require_annual=True, ts_codes=None):
        """执行财务筛选 (全透传模式，直接使用 Tushare 原始字段名)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(financial_indicators)")
            db_existing_cols = {row[1] for row in cursor.fetchall()}
            
            # 1. 子查询：锁定最新报告期
            where_base = []
            if require_annual: where_base.append("period LIKE '%1231'")
            
            sub_params = []
            if ts_codes:
                placeholders = ','.join(['?'] * len(ts_codes))
                where_base.append(f"ts_code IN ({placeholders})")
                sub_params.extend(ts_codes)
            
            base_filter_str = ("WHERE " + " AND ".join(where_base)) if where_base else ""
            
            subquery = f"""
                SELECT ts_code, MAX(period) as max_period
                FROM financial_indicators
                {base_filter_str}
                GROUP BY ts_code
            """
            
            # 2. 硬指标过滤 (直接使用 filters 中的原始 key)
            hard_where = []
            main_params = []
            active_metrics = set() # 记录本次筛选涉及的所有原始指标

            for key, value in filters.items():
                db_col = key.replace('_min', '').replace('_max', '')
                if db_col in db_existing_cols:
                    op = ">=" if key.endswith('_min') else "<="
                    hard_where.append(f"f1.{db_col} {op} ?")
                    main_params.append(value)
                    active_metrics.add(db_col)
                else:
                    logger.warning(f"⚠️ 筛选跳过: 数据库中尚无列 {db_col}")
            
            final_where = (" AND " + " AND ".join(hard_where)) if hard_where else ""
            
            # 3. 结果投影 (始终包含 ts_code, period 以及本次筛选的所有指标)
            select_cols = ["f1.ts_code", "f1.period"]
            
            # 预定义核心显示列，如果它们在数据库中则显示
            display_candidates = ['roe_dt', 'roic', 'tr_yoy', 'q_sales_yoy', 'dt_netprofit_yoy', 'grossprofit_margin', 'debt_to_assets']
            # 合并用户本次筛选涉及的列
            final_display_cols = sorted(list(set(display_candidates) | active_metrics))
            
            for db_col in final_display_cols:
                if db_col in db_existing_cols:
                    select_cols.append(f"f1.{db_col}")
                else:
                    select_cols.append(f"0 as {db_col}")
            
            sql = f"""
                SELECT {', '.join(select_cols)}
                FROM financial_indicators f1
                INNER JOIN ({subquery}) f2 
                ON f1.ts_code = f2.ts_code AND f1.period = f2.max_period
                WHERE 1=1 {final_where}
            """
            
            logger.info(f"🔍 财务全透传扫描 (指标: {list(active_metrics)})")
            df = pd.read_sql_query(sql, conn, params=sub_params + main_params)
            return df

    def get_statistics(self):
        """获取数据库统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            try:
                result = conn.execute("SELECT COUNT(*) FROM financial_indicators").fetchone()
                stats['total_records'] = result[0] if result else 0
                
                result = conn.execute("SELECT COUNT(DISTINCT ts_code) FROM financial_indicators").fetchone()
                stats['total_stocks'] = result[0] if result else 0
                
                result = conn.execute("SELECT DISTINCT period FROM financial_indicators ORDER BY period").fetchall()
                stats['periods'] = [row[0] for row in result]
                
                result = conn.execute("SELECT MAX(updated_at) FROM financial_indicators").fetchone()
                stats['last_updated'] = result[0] if result else "无"
                
                stats['db_size_mb'] = self.db_path.stat().st_size / (1024*1024) if self.db_path.exists() else 0
            except Exception as e:
                logger.error(f"获取统计信息失败: {e}")
                return {'total_records': 0, 'total_stocks': 0, 'periods': [], 'last_updated': '错误', 'db_size_mb': 0}
            
            return stats

    def get_latest_period(self):
        with sqlite3.connect(self.db_path) as conn:
            try:
                row = conn.execute("SELECT MAX(period) FROM financial_indicators").fetchone()
                return row[0] if row and row[0] else None
            except: return None

if __name__ == '__main__':
    fd = FinancialDataManager()
    print(f"财务模块就绪，最新期: {fd.get_latest_period()}")
