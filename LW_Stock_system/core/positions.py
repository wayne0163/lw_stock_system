import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path

class PositionManager:
    """持仓管理与交易记录 - 增强修正版"""
    
    def __init__(self, db_path=None):
        # 基于当前文件位置确定项目根目录，避免相对路径依赖 cwd
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'stock_data.db'
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 1. 持仓表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    name TEXT,
                    quantity INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    current_price REAL,
                    pnl REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    buy_date DATE DEFAULT CURRENT_DATE,
                    target_price REAL,
                    stop_loss_price REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 2. 核心流水表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    name TEXT,
                    trade_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    transaction_cost REAL DEFAULT 0,
                    post_balance REAL,
                    trade_date DATE DEFAULT CURRENT_DATE,
                    notes TEXT,
                    stop_loss REAL,
                    take_profit REAL,
                    market_env TEXT,
                    benchmark_price REAL
                )
            """)
            # 3. 资产表
            conn.execute("CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY CHECK (id = 1), cash REAL NOT NULL DEFAULT 0)")
            conn.execute("INSERT OR IGNORE INTO assets (id, cash) VALUES (1, 0)")
            conn.commit()

    def _recalculate_balances(self, cursor):
        """核心：全量重算所有流水余额并同步资产表"""
        df = pd.read_sql_query("SELECT id, trade_type, amount, transaction_cost FROM trade_log ORDER BY trade_date ASC, id ASC", cursor.connection)
        running_bal = 0.0
        for _, row in df.iterrows():
            t = row['trade_type']
            a = row['amount']
            f = row['transaction_cost'] or 0
            if t == 'BUY': running_bal -= (a + f)
            elif t == 'SELL': running_bal += (a - f)
            elif t in ['DEPOSIT', '外部资金']: running_bal += a
            elif t == 'WITHDRAW': running_bal -= a
            cursor.execute("UPDATE trade_log SET post_balance = ? WHERE id = ?", (running_bal, row['id']))
        cursor.execute("UPDATE assets SET cash = ? WHERE id = 1", (running_bal,))

    def get_cash(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT cash FROM assets WHERE id = 1").fetchone()[0]

    def _normalize_ts_code(self, ts_code):
        """确保股票代码带有交易所后缀 (.SH 或 .SZ)"""
        if not ts_code or ts_code == 'CASH':
            return ts_code
        if '.' in ts_code:
            return ts_code.upper()
        
        # 简单逻辑判断
        if ts_code.startswith('60') or ts_code.startswith('688') or ts_code.startswith('900'):
            return f"{ts_code}.SH"
        elif ts_code.startswith('00') or ts_code.startswith('30') or ts_code.startswith('200'):
            return f"{ts_code}.SZ"
        elif ts_code.startswith('8') or ts_code.startswith('4'):
            return f"{ts_code}.BJ"
        return ts_code.upper()

    def add_position(self, ts_code, name, quantity, price, date=None, notes=None, sl=None, tp=None, env=None):
        ts_code = self._normalize_ts_code(ts_code)
        trade_amount = quantity * price
        fee = trade_amount * 0.0003 + 15
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO trade_log (ts_code, name, trade_type, quantity, price, amount, transaction_cost, trade_date, notes, stop_loss, take_profit, market_env)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts_code, name, 'BUY', quantity, price, trade_amount, fee, date or datetime.now().date(), notes, sl, tp, env))
                self._recalculate_balances(cursor)
                
                # 更新/插入持仓 (简化逻辑：仅为显示，AI诊断主要看流水)
                cursor.execute("SELECT quantity, cost_price FROM positions WHERE ts_code = ?", (ts_code,))
                row = cursor.fetchone()
                if row:
                    new_qty = row[0] + quantity
                    new_cost = (row[0]*row[1] + trade_amount) / new_qty
                    cursor.execute("UPDATE positions SET quantity=?, cost_price=?, target_price=?, stop_loss_price=? WHERE ts_code=?", (new_qty, new_cost, tp, sl, ts_code))
                else:
                    cursor.execute("INSERT INTO positions (ts_code, name, quantity, cost_price, buy_date, target_price, stop_loss_price) VALUES (?,?,?,?,?,?,?)",
                                  (ts_code, name, quantity, price, date or datetime.now().date(), tp, sl))
                
                conn.commit()
                
                # 🔄 重建持仓表，确保与 trade_log 完全一致（应对可能的外部修改或历史数据问题）
                self.rebuild_positions_from_logs()
                
                return True
            except Exception as e: conn.rollback(); raise e

    def sell_position(self, pos_id, price, qty=None, notes=None, env=None):
        """
        卖出持仓。
        pos_id: positions 表的 id 字段（主键）
        返回: True=成功, False=失败（如持仓不足)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                logger.info(f"[sell_position] 尝试卖出: pos_id={pos_id}, price={price}, qty={qty}")
                cursor.execute("SELECT ts_code, name, quantity, cost_price FROM positions WHERE id = ?", (pos_id,))
                p = cursor.fetchone()
                if not p:
                    logger.error(f"[sell_position] 未找到 id={pos_id} 的持仓记录")
                    # 列出当前所有持仓便于调试
                    cursor.execute("SELECT id, ts_code, name, quantity FROM positions")
                    all_pos = cursor.fetchall()
                    logger.error(f"[sell_position] 当前所有持仓: {all_pos}")
                    return False
                ts_code, name, pos_qty, cost_price = p
                logger.info(f"[sell_position] 找到持仓: {ts_code} 名称={name} 当前数量={pos_qty}")
                
                q = qty if qty and qty < pos_qty else pos_qty
                if qty and qty > pos_qty:
                    logger.warning(f"[sell_position] 卖出数量{qty}超过持仓{pos_qty}，将卖出全部{q}股")
                
                amt = q * price
                fee = amt * 0.0003 + 15
                cursor.execute("""
                    INSERT INTO trade_log (ts_code, name, trade_type, quantity, price, amount, transaction_cost, trade_date, notes, market_env)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts_code, name, 'SELL', q, price, amt, fee, datetime.now().date(), notes, env))
                logger.info(f"[sell_position] 插入 SELL 记录: {ts_code} {q}@{price} 金额={amt:.2f}")
                
                # 重算余额
                self._recalculate_balances(cursor)
                logger.info(f"[sell_position] 余额重算完成")
                
                # 更新/删除持仓
                if q >= pos_qty:
                    cursor.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
                    logger.info(f"[sell_position] 删除持仓记录 id={pos_id}")
                else:
                    cursor.execute("UPDATE positions SET quantity = quantity - ? WHERE id = ?", (q, pos_id))
                    logger.info(f"[sell_position] 更新持仓数量: -{q}")
                
                # 重算现金余额
                self._recalculate_balances(cursor)
                conn.commit()
                
                # 🔄 重建持仓表，确保与 trade_log 完全一致（解决不同步问题）
                self.rebuild_positions_from_logs()
                
                logger.info(f"[sell_position] 交易提交成功")
                return True
            except Exception as e:
                logger.error(f"[sell_position] 异常: {e}", exc_info=True)
                conn.rollback()
                raise

    def edit_trade_log(self, log_id, **kwargs):
        """修正任意流水字段并全量重算余额"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                # 1. 动态构造更新语句
                if 'price' in kwargs or 'quantity' in kwargs:
                    # 如果改了价格或数量，重新计算成交额和佣金
                    p = float(kwargs.get('price')) if 'price' in kwargs else None
                    q = int(kwargs.get('quantity')) if 'quantity' in kwargs else None
                    if p is None or q is None:
                        cursor.execute("SELECT price, quantity FROM trade_log WHERE id = ?", (log_id,))
                        old = cursor.fetchone()
                        p = p if p is not None else old[0]
                        q = q if q is not None else old[1]
                    amt = p * q
                    kwargs['amount'] = amt
                    kwargs['transaction_cost'] = amt * 0.0003 + 15
                
                set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                params = list(kwargs.values()) + [log_id]
                cursor.execute(f"UPDATE trade_log SET {set_clause} WHERE id = ?", params)
                
                # 2. 触发重算：先重算现金余额，再重建positions（确保数据完全一致）
                self._recalculate_balances(cursor)
                # rebuild_positions_from_logs 需要独立连接（避免事务嵌套），在 commit 后调用
                conn.commit()
                self.rebuild_positions_from_logs()
                return True
            except Exception as e: conn.rollback(); raise e

    def manual_cash_op(self, amount, op_type='DEPOSIT', notes="", date=None):
        """外部资金存取"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO trade_log (ts_code, name, trade_type, quantity, price, amount, transaction_cost, trade_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ('CASH', '外部资金', op_type, 0, amount, amount, 0, date or datetime.now().date(), notes))
                self._recalculate_balances(cursor)
                conn.commit()
                return True
            except Exception as e: conn.rollback(); raise e

    def get_all(self):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM positions ORDER BY buy_date DESC", conn)

    def get_position_summary(self):
        """返回持仓汇总，包含现金和总资产。"""
        df = self.get_all(); cash = self.get_cash()
        if df.empty:
            return {
                'count': 0, 'total_cost': 0, 'total_value': 0,
                'positions_pnl': 0, 'positions_pnl_pct': 0,
                'cash': cash, 'total_assets': cash,
                'account_pnl': cash - 250000, 'account_pnl_pct': (cash/250000-1)*100 if 250000>0 else 0
            }
        cost = (df['cost_price'] * df['quantity']).sum()
        val = (df.get('current_price', 0).fillna(df['cost_price']) * df['quantity']).sum()
        positions_pnl = val - cost
        positions_pnl_pct = (val/cost-1)*100 if cost>0 else 0
        total_assets = val + cash
        # 账户总盈亏 = 当前总资产 - 初始本金 250,000
        account_pnl = total_assets - 250000
        account_pnl_pct = (total_assets/250000-1)*100 if 250000>0 else 0
        return {
            'count': len(df),
            'total_cost': cost,
            'total_value': val,
            'positions_pnl': positions_pnl, 'positions_pnl_pct': positions_pnl_pct,
            'cash': cash,
            'total_assets': total_assets,
            'account_pnl': account_pnl, 'account_pnl_pct': account_pnl_pct
        }

    def update_prices_bulk(self, p_dict):
        if not p_dict: return
        with sqlite3.connect(self.db_path) as conn:
            # 批量更新：先获取所有需要更新的持仓的成本和数量
            ts_codes = list(p_dict.keys())
            placeholders = ','.join(['?'] * len(ts_codes))
            existing = pd.read_sql_query(
                f"SELECT ts_code, cost_price, quantity FROM positions WHERE ts_code IN ({placeholders})",
                conn, params=ts_codes
            )
            
            # 构建更新参数列表
            update_params = []
            for _, row in existing.iterrows():
                code = row['ts_code']
                if code in p_dict:
                    p = p_dict[code]
                    cost = row['cost_price']
                    qty = row['quantity']
                    pnl = (p - cost) * qty
                    pnl_pct = (p / cost - 1) * 100 if cost and cost > 0 else 0
                    update_params.append((p, pnl, pnl_pct, code))
            
            if update_params:
                conn.executemany(
                    "UPDATE positions SET current_price = ?, pnl = ?, pnl_pct = ? WHERE ts_code = ?",
                    update_params
                )
                conn.commit()

    def rebuild_positions_from_logs(self):
        """
        根据 trade_log 中的所有 BUY/SELL 记录，全量重新计算 positions 表。
        用途：
        1. 删除/修改交易记录后修复持仓不一致
        2. 数据迁移或手动修复
        3. 定期校验（每周）
        """
        import pandas as pd
        from datetime import datetime
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 读取所有持仓相关交易（包含手续费）
            df = pd.read_sql_query("""
                SELECT ts_code, name, trade_type, quantity, price, amount, transaction_cost
                FROM trade_log 
                WHERE trade_type IN ('BUY', 'SELL')
                ORDER BY trade_date ASC, id ASC
            """, conn)
            
            # 按时间顺序模拟，计算每只股票的最终持仓和成本
            holdings = {}  # {ts_code: {'qty': int, 'total_cost': float, 'name': str}}
            
            for _, row in df.iterrows():
                code = row['ts_code']
                name = row['name']
                t = row['trade_type']
                qty = row['quantity']
                amt = row['amount']
                fee = row['transaction_cost'] or 0
                
                if code not in holdings:
                    holdings[code] = {'qty': 0, 'total_cost': 0.0, 'name': name}
                
                h = holdings[code]
                if t == 'BUY':
                    h['qty'] += qty
                    h['total_cost'] += (amt + fee)   # 成本 = 成交额 + 手续费
                elif t == 'SELL':
                    if h['qty'] >= qty:
                        cost_ratio = qty / h['qty'] if h['qty'] > 0 else 0
                        h['total_cost'] *= (1 - cost_ratio)
                        h['qty'] -= qty
                    else:
                        # 异常：卖出数量大于当前持仓，强制清零（该条SELL仍计入，确保最终持仓为0）
                        print(f"⚠️  数据异常：{code} 卖出{qty}股，但仅持有{h['qty']}股，强制清零")
                        h['qty'] = 0
                        h['total_cost'] = 0.0
            
            # 清空旧持仓
            cursor.execute("DELETE FROM positions")
            
            # 加载股票代码映射（补全后缀）
            code_map = {}
            try:
                cursor.execute("SELECT ts_code, symbol FROM stocks_basic")
                for row in cursor.fetchall():
                    ts_code, symbol = row
                    code_map[symbol] = ts_code
            except:
                pass
            
            # 插入新持仓（仅数量 > 0 的）
            today = datetime.now().strftime('%Y-%m-%d')
            inserted = 0
            for code, h in holdings.items():
                if h['qty'] > 0:
                    ts_code_final = code
                    if '.' not in code and code in code_map:
                        ts_code_final = code_map[code]
                    
                    cost_price = h['total_cost'] / h['qty'] if h['qty'] > 0 else 0
                    
                    # 从 trade_log 中查找最近一次 BUY 的止损止盈
                    cursor.execute(
                        "SELECT stop_loss, take_profit FROM trade_log WHERE ts_code = ? AND trade_type = 'BUY' ORDER BY trade_date DESC, id DESC LIMIT 1",
                        (code,)
                    )
                    sl_tp = cursor.fetchone()
                    sl = sl_tp[0] if sl_tp and sl_tp[0] is not None else None
                    tp = sl_tp[1] if sl_tp and sl_tp[1] is not None else None
                    
                    cursor.execute("""
                        INSERT INTO positions (ts_code, name, quantity, cost_price, buy_date, last_updated, target_price, stop_loss_price)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ts_code_final, h['name'], h['qty'], round(cost_price, 3),
                        today, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        tp, sl
                    ))
                    inserted += 1
            
            # 🔄 重建后重算现金余额
            self._recalculate_balances(cursor)
            
            conn.commit()
            return inserted
