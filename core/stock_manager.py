# core/stock_manager.py
import sqlite3
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StockManager:
    """管理所有股票的基础信息（代码、名称、上市日期等）"""
    
    def __init__(self, db_path=None):
        # 基于当前文件位置确定项目根目录，避免相对路径依赖 cwd
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'stock_data.db'
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """初始化股票基础信息表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks_basic (
                    ts_code TEXT PRIMARY KEY,
                    symbol TEXT,
                    name TEXT,
                    area TEXT,
                    industry TEXT,
                    market TEXT,
                    list_date TEXT,
                    is_st INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON stocks_basic(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_industry ON stocks_basic(industry)")
            conn.commit()
    
    def update_stocks_list(self, token):
        """从 Tushare 获取并更新所有股票列表"""
        import tushare as ts
        pro = ts.pro_api(token)
        
        logger.info("正在获取 Tushare 股票列表...")
        try:
            # 获取上市和暂停上市的股票
            df_l = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date')
            df_p = pro.stock_basic(exchange='', list_status='P', fields='ts_code,symbol,name,area,industry,market,list_date')
            df = pd.concat([df_l, df_p], ignore_index=True)
            
            if df.empty:
                logger.warning("获取到的股票列表为空")
                return 0
            
            # 🔧 修复中文编码：Tushare 返回的 name 字段可能因 requests 编码检测错误而乱码
            # 现象：name 列显示为 '��ͨ�Ƽ�' 等，实际是 UTF-8 字节被错误解码为 GBK 的结果
            # 解决：如果 name 包含异常字符，尝试用 'latin1'  round-trip 修复
            def fix_encoding(s):
                """修复因编码错误导致的乱码"""
                if not isinstance(s, str):
                    return s
                # 检测是否包含大量非 ASCII 控制字符或乱码特征
                if any(ord(c) > 0xFF for c in s):  # 已经是正确 Unicode
                    return s
                # 尝试：将乱码字符串重新编码为 latin1（字节原样保留），再用 utf-8 解码
                try:
                    return s.encode('latin1').decode('utf-8')
                except:
                    return s
            
            if df['name'].dtype == 'object':
                df['name'] = df['name'].apply(fix_encoding)
            
            # 标记 ST
            df['is_st'] = df['name'].apply(lambda x: 1 if 'ST' in x or '*ST' in x else 0)
            df['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with sqlite3.connect(self.db_path) as conn:
                df.to_sql('stocks_basic', conn, if_exists='replace', index=False)
                conn.commit()
            
            logger.info(f"成功更新 {len(df)} 支股票基础信息")
            return len(df)
        except Exception as e:
            logger.error(f"更新股票列表失败: {e}")
            return 0
    
    def get_stock_info(self, ts_code):
        """获取单只股票信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM stocks_basic WHERE ts_code = ?", (ts_code,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def search_stocks(self, keyword, limit=10):
        """搜索股票（代码或名称）"""
        with sqlite3.connect(self.db_path) as conn:
            sql = """
                SELECT ts_code, name, industry, market 
                FROM stocks_basic 
                WHERE ts_code LIKE ? OR name LIKE ? OR symbol LIKE ?
                LIMIT ?
            """
            params = [f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', limit]
            df = pd.read_sql_query(sql, conn, params=params)
            return df
    
    def get_codes_by_sector(self, sector):
        """根据行业获取股票代码列表"""
        with sqlite3.connect(self.db_path) as conn:
            # Tushare 的 industry 可能有空值
            cursor = conn.execute("SELECT ts_code FROM stocks_basic WHERE industry = ?", (sector,))
            return [row[0] for row in cursor.fetchall()]

    def get_all_industries(self):
        """获取所有已存在的行业列表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT industry FROM stocks_basic WHERE industry IS NOT NULL AND industry != '' ORDER BY industry")
            return [row[0] for row in cursor.fetchall()]

    def get_all_codes(self):
        """获取所有股票代码列表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT ts_code FROM stocks_basic")
            return [row[0] for row in cursor.fetchall()]

    def get_stock_name(self, ts_code):
        """快速获取名称"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT name FROM stocks_basic WHERE ts_code = ?", (ts_code,))
            row = cursor.fetchone()
            return row[0] if row else ts_code

if __name__ == '__main__':
    # 简单测试
    import os
    token = os.environ.get('TUSHARE_TOKEN')
    sm = StockManager()
    if token:
        sm.update_stocks_list(token)
    print(sm.search_stocks('茅台'))
