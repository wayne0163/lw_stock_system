# 自选股管理模块

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

class WatchlistManager:
    """自选股管理"""
    
    def __init__(self, db_path=None):
        # 基于当前文件位置确定项目根目录，避免相对路径依赖 cwd
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'stock_data.db'
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """初始化自选股表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    name TEXT,
                    sector TEXT,
                    source TEXT DEFAULT '手动添加',
                    notes TEXT,
                    added_date DATE DEFAULT CURRENT_DATE,
                    UNIQUE(ts_code, source)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts_code ON watchlist(ts_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sector ON watchlist(sector)")
            conn.commit()
    
    def add_stock(self, ts_code, name=None, sector=None, source='手动添加', notes=None):
        """添加股票到自选股"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO watchlist (ts_code, name, sector, source, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (ts_code, name, sector, source, notes))
                conn.commit()
                return True
            except Exception as e:
                print(f"添加失败: {e}")
                return False
    
    def remove_stock(self, ts_code, source='手动添加'):
        """删除自选股"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM watchlist WHERE ts_code = ? AND source = ?", 
                        (ts_code, source))
            conn.commit()
            return conn.total_changes > 0
    
    def get_all(self, source=None):
        """获取所有自选股"""
        with sqlite3.connect(self.db_path) as conn:
            if source:
                df = pd.read_sql_query("SELECT * FROM watchlist WHERE source = ? ORDER BY added_date DESC", 
                                      conn, params=(source,))
            else:
                df = pd.read_sql_query("SELECT * FROM watchlist ORDER BY added_date DESC", conn)
            return df
    
    def search(self, keyword, source=None):
        """搜索股票（代码或名称）"""
        with sqlite3.connect(self.db_path) as conn:
            sql = "SELECT * FROM watchlist WHERE (ts_code LIKE ? OR name LIKE ?)"
            params = [f'%{keyword}%', f'%{keyword}%']
            
            if source:
                sql += " AND source = ?"
                params.append(source)
            
            df = pd.read_sql_query(sql, conn, params=params)
            return df
    
    def get_by_sector(self, sector):
        """按板块获取"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM watchlist WHERE sector = ?", 
                                  conn, params=(sector,))
            return df
    
    def count(self, source=None):
        """统计数量"""
        with sqlite3.connect(self.db_path) as conn:
            if source:
                result = conn.execute("SELECT COUNT(*) FROM watchlist WHERE source = ?", 
                                     (source,)).fetchone()
            else:
                result = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()
            return result[0] if result else 0
    
    def export_csv(self, output_path, source=None):
        """导出为 CSV"""
        df = self.get_all(source)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        return len(df)
    
    def import_csv(self, csv_path, source='导入文件'):
        """从 CSV 导入"""
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        imported = 0
        
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO watchlist 
                        (ts_code, name, sector, source, notes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (row['ts_code'], row.get('name'), row.get('sector'), 
                          source, row.get('notes')))
                    imported += 1
                except:
                    pass
            conn.commit()
        
        return imported
    
    def get_groups(self):
        """获取所有分组（source）"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("SELECT DISTINCT source FROM watchlist ORDER BY source").fetchall()
            return [row[0] for row in result]

    # ---- stock_tags 标签管理 ----
    def add_tag(self, ts_code, tag_name):
        """给股票添加标签"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO stock_tags (ts_code, tag_name) VALUES (?, ?)",
                    (ts_code, tag_name)
                )
                conn.commit()
                return True
            except Exception as e:
                print(f"添加标签失败: {e}")
                return False

    def remove_tag(self, ts_code, tag_name):
        """删除股票的指定标签"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM stock_tags WHERE ts_code = ? AND tag_name = ?",
                (ts_code, tag_name)
            )
            conn.commit()
            return conn.total_changes > 0

    def get_tags_for_stock(self, ts_code):
        """获取股票的所有标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT tag_name FROM stock_tags WHERE ts_code = ?", (ts_code,)
            )
            return [r[0] for r in cursor.fetchall()]

    def get_all_tags(self):
        """获取所有不重复的标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT tag_name FROM stock_tags ORDER BY tag_name"
            )
            return [r[0] for r in cursor.fetchall()]

if __name__ == '__main__':
    # 测试
    mgr = WatchlistManager('database/test_watchlist.db')
    
    print("测试添加股票...")
    mgr.add_stock('002782.SZ', name='可立克', sector='AI硬件', notes='观察')
    mgr.add_stock('000001.SZ', name='平安银行', sector='金融')
    mgr.add_stock('600519.SH', name='贵州茅台', sector='消费')
    
    print("查询全部:")
    print(mgr.get_all())
    
    print("搜索 '可立克':")
    print(mgr.search('可立克'))
    
    print("统计:", mgr.count(), "支")
    print("分组:", mgr.get_groups())
