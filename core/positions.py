import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path


class StopLossProfitManager:
    """
    动态止盈止损管理器
    适用于高弹性股票（AI硬件/机器人/固态电池等）
    
    支持策略类型：
    - 止损：固定止损(fixed)、移动止损(trailing)、ATR波动止损(atr)
    - 止盈：移动止盈(trailing)、分批止盈(tiered)、RSI超买预警(rsi)
    """
    
    # 策略类型常量
    STOP_LOSS_TYPES = ['fixed', 'trailing', 'atr']
    PROFIT_EXIT_TYPES = ['trailing', 'tiered', 'rsi', 'fixed']
    TRAILING_MODES = ['strict', 'loose']
    
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'stock_data.db'
        else:
            self.db_path = Path(db_path)
    
    def _row_to_dict(self, row, columns):
        """将数据库行转换为字典"""
        return dict(zip(columns, row)) if row else None
    
    def get_position(self, pos_id):
        """获取单个持仓记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM positions WHERE id = ?", (int(pos_id),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_positions(self):
        """获取所有持仓"""
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM positions", conn)
    
    def update_strategy(self, pos_id, **kwargs):
        """
        修改单个持仓的止盈止损策略
        
        可用参数：
        - stop_loss_type: 'fixed', 'trailing', 'atr'
        - stop_loss_value: 止损比例 (如 0.10 表示 10%)
        - profit_exit_type: 'trailing', 'tiered', 'rsi', 'fixed'
        - profit_exit_value: 止盈比例
        - trailing_mode: 'strict', 'loose'
        - atr_multiplier: ATR倍数 (用于ATR止损)
        - tiered_profit_1/2/3: 分批止盈点位
        - rsi_overbought_level: RSI超买预警线
        - stop_loss_price: 固定止损价格（仅用于fixed类型）
        - target_price: 目标价格（仅用于fixed类型）
        """
        allowed_keys = [
            'stop_loss_type', 'stop_loss_value', 'profit_exit_type', 'profit_exit_value',
            'trailing_mode', 'atr_multiplier', 'tiered_profit_1', 'tiered_profit_2', 
            'tiered_profit_3', 'rsi_overbought_level', 'stop_loss_price', 'target_price'
        ]
        
        # 过滤只允许的字段
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_keys and v is not None}
        
        if not update_fields:
            return False
        
        # 设置 last_updated
        update_fields['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
        params = list(update_fields.values()) + [int(pos_id)]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE positions SET {set_clause} WHERE id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_default_strategy(self):
        """获取默认策略参数"""
        return {
            'stop_loss_type': 'trailing',
            'stop_loss_value': 0.10,  # 从高点回落10%止损
            'profit_exit_type': 'tiered',
            'profit_exit_value': 0.15,  # 第一批止盈15%
            'trailing_mode': 'strict',
            'atr_multiplier': 3.0,
            'tiered_profit_1': 0.15,   # 第一批止盈15%
            'tiered_profit_2': 0.25,   # 第二批止盈25%
            'tiered_profit_3': 0.40,   # 第三批止盈40%（移动止损）
            'rsi_overbought_level': 80.0,
            'stop_loss_price': None,
            'target_price': None
        }
    
    def calc_trailing_stop(self, highest_price, current_price, stop_loss_pct, mode='strict'):
        """
        计算移动止损触发价
        
        Args:
            highest_price: 买入后最高价
            current_price: 当前价格
            stop_loss_pct: 止损比例 (如 0.10 表示 10%)
            mode: 'strict' 严格要求 | 'loose' 宽松模式(有2%容忍)
        
        Returns:
            trigger_price: 触发卖出的价格
        """
        trigger_price = highest_price * (1 - stop_loss_pct)
        
        if mode == 'loose':
            # 宽松模式：额外2%容忍，减少震荡洗盘被震出
            tolerance = highest_price * 0.02
            trigger_price = trigger_price - tolerance
        
        return trigger_price
    
    def calc_atr_stop(self, highest_price, atr, atr_multiplier=3.0):
        """
        计算ATR波动止损
        更适合高波动股票
        
        Args:
            highest_price: 买入后最高价
            atr: 平均真实波幅
            atr_multiplier: ATR倍数 (激进2.5, 保守3.0)
        
        Returns:
            trigger_price: 触发卖出的价格
        """
        return highest_price - atr_multiplier * atr
    
    def check_stop_loss(self, pos_data, current_price, rsi=None, atr=None):
        """
        检查止损是否触发
        
        Returns:
            dict: {'triggered': True/False, 'action': 'STOP_LOSS', 'trigger_price': xxx, 'reason': xxx}
        """
        stop_loss_type = pos_data.get('stop_loss_type', 'fixed')
        stop_loss_value = pos_data.get('stop_loss_value', 0.10)
        stop_loss_price = pos_data.get('stop_loss_price')
        cost_price = pos_data.get('cost_price', 0)
        highest_since_buy = pos_data.get('highest_since_buy', 0) or cost_price
        trailing_mode = pos_data.get('trailing_mode', 'strict')
        atr_multiplier = pos_data.get('atr_multiplier', 3.0)
        
        triggered = False
        trigger_price = None
        reason = None
        
        if stop_loss_type == 'fixed' and stop_loss_price:
            # 固定止损：价格 <= 止损价
            trigger_price = stop_loss_price
            if current_price <= trigger_price:
                triggered = True
                reason = f'固定止损 {trigger_price:.2f}'
        
        elif stop_loss_type == 'trailing':
            # 移动止损：从最高点回落
            trigger_price = self.calc_trailing_stop(
                highest_since_buy, current_price, stop_loss_value, trailing_mode
            )
            if current_price <= trigger_price:
                triggered = True
                reason = f'移动止损 从{highest_since_buy:.2f}回落{stop_loss_value*100:.0f}%到{trigger_price:.2f}'
        
        elif stop_loss_type == 'atr':
            # ATR波动止损
            if atr:
                trigger_price = self.calc_atr_stop(highest_since_buy, atr, atr_multiplier)
                if current_price <= trigger_price:
                    triggered = True
                    reason = f'ATR止损 {atr_multiplier}*ATR={atr:.2f} 触发价{trigger_price:.2f}'
        
        return {
            'triggered': triggered,
            'action': 'STOP_LOSS' if triggered else None,
            'trigger_price': trigger_price,
            'reason': reason
        }
    
    def check_profit_exit(self, pos_data, current_price, rsi=None):
        """
        检查止盈是否触发
        
        Returns:
            dict: {'triggered': True/False, 'action': 'SELL_ALL/SELL_HALF/SELL_THIRD/CONSIDER_SELL', 'reason': xxx}
        """
        profit_exit_type = pos_data.get('profit_exit_type', 'tiered')
        profit_exit_value = pos_data.get('profit_exit_value', 0.15)
        cost_price = pos_data.get('cost_price', 0)
        highest_since_buy = pos_data.get('highest_since_buy', 0) or cost_price
        rsi_overbought_level = pos_data.get('rsi_overbought_level', 80.0)
        
        # 计算当前盈利比例
        profit_pct = (current_price - cost_price) / cost_price if cost_price > 0 else 0
        
        tiered_profit_1 = pos_data.get('tiered_profit_1', 0.15)
        tiered_profit_2 = pos_data.get('tiered_profit_2', 0.25)
        tiered_profit_3 = pos_data.get('tiered_profit_3', 0.40)
        
        triggered = False
        action = None
        reason = None
        
        if profit_exit_type == 'trailing':
            # 移动止盈：从最高点回落指定比例
            trigger_price = highest_since_buy * (1 - profit_exit_value)
            if current_price <= trigger_price:
                triggered = True
                action = 'SELL_ALL'
                reason = f'移动止盈 从{highest_since_buy:.2f}回落{profit_exit_value*100:.0f}%'
        
        elif profit_exit_type == 'tiered':
            # 分批止盈
            if profit_pct >= tiered_profit_3:
                # 第三批：从高点回落8%止盈（留仓让利润奔跑）
                trigger_price = highest_since_buy * 0.92
                if current_price <= trigger_price:
                    triggered = True
                    action = 'SELL_ALL'
                    reason = f'分批止盈第三批(涨{tiered_profit_3*100:.0f}%) 从高点回落8%'
            elif profit_pct >= tiered_profit_2:
                # 第二批：再卖1/3
                triggered = True
                action = 'SELL_THIRD'
                reason = f'分批止盈第二批(涨{tiered_profit_2*100:.0f}%)'
            elif profit_pct >= tiered_profit_1:
                # 第一批：卖1/3
                triggered = True
                action = 'SELL_THIRD'
                reason = f'分批止盈第一批(涨{tiered_profit_1*100:.0f}%)'
        
        elif profit_exit_type == 'rsi':
            # RSI超买预警
            if rsi and rsi >= 90:
                triggered = True
                action = 'FORCE_SELL'
                reason = f'RSI极度超买({rsi:.1f}) 强制卖出'
            elif rsi and rsi >= rsi_overbought_level:
                triggered = True
                action = 'CONSIDER_SELL'
                reason = f'RSI超买({rsi:.1f}) 考虑卖出'
        
        elif profit_exit_type == 'fixed':
            target_price = pos_data.get('target_price')
            if target_price and current_price >= target_price:
                triggered = True
                action = 'SELL_ALL'
                reason = f'达到目标价 {target_price:.2f}'
        
        return {
            'triggered': triggered,
            'action': action,
            'reason': reason,
            'profit_pct': profit_pct
        }
    
    def update_highest_price(self, pos_id, current_price):
        """更新持仓的历史最高价"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT highest_since_buy, cost_price FROM positions WHERE id = ?",
                (int(pos_id),)
            )
            row = cursor.fetchone()
            if row:
                current_highest = row[0] or 0
                cost_price = row[1] or 0
                # 更新为当前最高价（取较大值）
                new_highest = max(current_highest, current_price, cost_price)
                if new_highest != current_highest:
                    conn.execute(
                        "UPDATE positions SET highest_since_buy = ? WHERE id = ?",
                        (new_highest, int(pos_id))
                    )
                    conn.commit()
                    return new_highest
            return None
    
    def check_position(self, pos_id, current_price, rsi=None, atr=None):
        """
        综合检查持仓状态，返回操作建议
        
        Returns:
            dict: {
                'stop_loss': {...},
                'profit_exit': {...},
                'action': 'HOLD'/'STOP_LOSS'/'SELL_ALL'/'SELL_THIRD'/'CONSIDER_SELL',
                'summary': str
            }
        """
        pos_data = self.get_position(pos_id)
        if not pos_data:
            return {'error': f'未找到持仓 ID: {pos_id}'}
        
        # 先更新最高价
        self.update_highest_price(pos_id, current_price)
        # 重新获取（更新后的）
        pos_data = self.get_position(pos_id)
        
        # 检查止损
        stop_loss_result = self.check_stop_loss(pos_data, current_price, rsi, atr)
        
        # 检查止盈
        profit_result = self.check_profit_exit(pos_data, current_price, rsi)
        
        # 综合判断：止损优先于止盈
        # 逻辑：
        # 1. 如果止损触发（价格跌破防线）→ 强制止损，忽略止盈
        # 2. 如果止盈触发 → 执行相应止盈操作
        # 3. 如果同时触发 → 止损优先（本金安全第一）
        action = 'HOLD'
        summary_parts = []
        
        if stop_loss_result['triggered']:
            # 止损优先：任何时候止损触发都第一优先级
            action = 'STOP_LOSS'
            summary_parts.append(f"⚠️ {stop_loss_result['reason']}")
        elif profit_result['triggered']:
            # 止盈：只有止损未触发时才执行
            action = profit_result['action']
            summary_parts.append(f"🎯 {profit_result['reason']}")
        
        if not summary_parts:
            summary_parts.append(f"✅ 持有中 盈亏{profit_result['profit_pct']*100:.1f}%")
        
        return {
            'stop_loss': stop_loss_result,
            'profit_exit': profit_result,
            'action': action,
            'summary': ' | '.join(summary_parts),
            'highest_price': pos_data.get('highest_since_buy'),
            'profit_pct': profit_result['profit_pct']
        }
    
    def get_strategy_display(self, pos_data):
        """获取策略显示字符串"""
        sl_type = pos_data.get('stop_loss_type', 'fixed')
        sl_value = pos_data.get('stop_loss_value', 0.10)
        pe_type = pos_data.get('profit_exit_type', 'tiered')
        pe_value = pos_data.get('profit_exit_value', 0.15)
        
        sl_display = {
            'fixed': f'固定{pos_data.get("stop_loss_price", "-")}',
            'trailing': f'移动{sl_value*100:.0f}%',
            'atr': f'ATR{pos_data.get("atr_multiplier", 3.0):.1f}倍'
        }.get(sl_type, sl_type)
        
        pe_display = {
            'fixed': f'目标{pos_data.get("target_price", "-")}',
            'trailing': f'移动{pe_value*100:.0f}%',
            'tiered': f'分批({pos_data.get("tiered_profit_1", 0.15)*100:.0f}/{pos_data.get("tiered_profit_2", 0.25)*100:.0f}/{pos_data.get("tiered_profit_3", 0.40)*100:.0f}%)',
            'rsi': f'RSI{pos_data.get("rsi_overbought_level", 80):.0f}'
        }.get(pe_type, pe_type)
        
        return f"止损:{sl_display} 止盈:{pe_display}"


class PositionManager:
    """持仓管理与交易记录 - 增强修正版（支持动态止盈止损）"""

    def __init__(self, db_path=None):
        # 基于当前文件位置确定项目根目录,避免相对路径依赖 cwd
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / 'database' / 'stock_data.db'
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
        # 初始化止盈止损管理器
        self.slpm = StopLossProfitManager(db_path)

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 1. 持仓表（增强版 - 支持动态止盈止损）
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
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 增强止盈止损字段 ---
                    stop_loss_type TEXT DEFAULT 'trailing',
                    stop_loss_value REAL DEFAULT 0.10,
                    profit_exit_type TEXT DEFAULT 'tiered',
                    profit_exit_value REAL DEFAULT 0.15,
                    trailing_mode TEXT DEFAULT 'strict',
                    highest_since_buy REAL DEFAULT 0,
                    atr_multiplier REAL DEFAULT 3.0,
                    tiered_profit_1 REAL DEFAULT 0.15,
                    tiered_profit_2 REAL DEFAULT 0.25,
                    tiered_profit_3 REAL DEFAULT 0.40,
                    rsi_overbought_level REAL DEFAULT 80.0
                )
            """)
            
            # 为已存在的表添加新列（如果不存在）
            existing_cols = [desc[1] for desc in conn.execute("PRAGMA table_info(positions)")]
            new_columns = {
                'stop_loss_type': "TEXT DEFAULT 'trailing'",
                'stop_loss_value': 'REAL DEFAULT 0.10',
                'profit_exit_type': "TEXT DEFAULT 'tiered'",
                'profit_exit_value': 'REAL DEFAULT 0.15',
                'trailing_mode': "TEXT DEFAULT 'strict'",
                'highest_since_buy': 'REAL DEFAULT 0',
                'atr_multiplier': 'REAL DEFAULT 3.0',
                'tiered_profit_1': 'REAL DEFAULT 0.15',
                'tiered_profit_2': 'REAL DEFAULT 0.25',
                'tiered_profit_3': 'REAL DEFAULT 0.40',
                'rsi_overbought_level': 'REAL DEFAULT 80.0'
            }
            for col, col_def in new_columns.items():
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE positions ADD COLUMN {col} {col_def}")
            
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
        """核心:全量重算所有流水余额并同步资产表"""
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

    def _get_stock_name(self, ts_code):
        """从 stocks_basic 表查询股票名称，找不到返回 ts_code 本身"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute("SELECT name FROM stocks_basic WHERE ts_code = ?", (ts_code,))
                r = cur.fetchone()
                return r[0] if r else ts_code
        except Exception:
            return ts_code

    def add_position(self, ts_code, name, quantity, price, date=None, notes=None, sl=None, tp=None, env=None):
        """
        买入建仓。
        逻辑：只写 trade_log（唯一真实来源），然后统一次 positions 表。
        如果 name 为空，自动从 stocks_basic 表补全。
        """
        ts_code = self._normalize_ts_code(ts_code)
        # 自动补全名称
        if not name:
            name = self._get_stock_name(ts_code)
        trade_amount = quantity * price
        fee = trade_amount * 0.0003 + 15
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO trade_log (ts_code, name, trade_type, quantity, price, amount, transaction_cost, trade_date, notes, stop_loss, take_profit, market_env)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts_code, name, 'BUY', quantity, price, trade_amount, fee, date or datetime.now().date(), notes, sl, tp, env))
                
                # 重算现金余额
                self._recalculate_balances(cursor)
                conn.commit()
                
                # 🔄 统一次 positions 表（基于 trade_log 计算，保持一致）
                self.rebuild_positions_from_logs()
                return True
            except Exception as e:
                conn.rollback()
                raise e

    def sell_position(self, pos_id, price, qty=None, notes=None, env=None):
        """
        卖出持仓。
        pos_id: positions 表的 id 字段（主键），可以是字符串或整数
        返回: True=成功, False=失败（如持仓不足）
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 🔧 修复：pos_id 必须是整数，SQLite INTEGER PRIMARY KEY 不匹配字符串
        try:
            pos_id = int(pos_id)
        except (ValueError, TypeError):
            logger.error(f"[sell_position] pos_id 必须为整数，得到: {pos_id!r}")
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                logger.info(f"[sell_position] 尝试卖出: pos_id={pos_id}, price={price}, qty={qty}")
                cursor.execute("SELECT ts_code, name, quantity, cost_price FROM positions WHERE id = ?", (pos_id,))
                p = cursor.fetchone()
                if not p:
                    logger.error(f"[sell_position] 未找到 id={pos_id} 的持仓记录")
                    cursor.execute("SELECT id, ts_code, name, quantity FROM positions")
                    all_pos = cursor.fetchall()
                    logger.error(f"[sell_position] 当前所有持仓: {all_pos}")
                    return False
                
                ts_code, name, pos_qty, cost_price = p
                logger.info(f"[sell_position] 找到持仓: {ts_code} 名称={name} 当前数量={pos_qty}")
                
                # 计算实际卖出数量
                if qty is None or qty >= pos_qty:
                    q = pos_qty  # 全部卖出
                else:
                    q = qty
                
                if qty and qty > pos_qty:
                    logger.warning(f"[sell_position] 卖出数量{qty}超过持仓{pos_qty}，将卖出全部{q}股")
                
                # 1. 写入 trade_log（唯一真实来源）
                amt = q * price
                fee = amt * 0.0003 + 15
                cursor.execute("""
                    INSERT INTO trade_log (ts_code, name, trade_type, quantity, price, amount, transaction_cost, trade_date, notes, market_env)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts_code, name, 'SELL', q, price, amt, fee, datetime.now().date(), notes, env))
                logger.info(f"[sell_position] 插入 SELL 记录: {ts_code} {q}@{price} 金额={amt:.2f}")
                
                # 2. 重算现金余额
                self._recalculate_balances(cursor)
                
                # 3. 提交这笔交易
                conn.commit()
                
                # 4. 🔄 统一次 positions 表（基于 trade_log 重新计算）
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
                    # 如果改了价格或数量,重新计算成交额和佣金
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

                # 2. 触发重算:先重算现金余额,再重建positions(确保数据完全一致)
                self._recalculate_balances(cursor)
                # rebuild_positions_from_logs 需要独立连接(避免事务嵌套),在 commit 后调用
                conn.commit()
                self.rebuild_positions_from_logs()
                return True
            except Exception as e: conn.rollback(); raise e

    def delete_trade_log(self, log_id):
        """
        删除指定交易流水（DELETE），并重建持仓表。
        log_id: trade_log 的 id 字段（主键）
        返回: True=成功, False=失败
        """
        import logging
        logger = logging.getLogger(__name__)
        try:
            log_id = int(log_id)
        except (ValueError, TypeError):
            logger.error(f"[delete_trade_log] log_id 必须为整数，得到: {log_id!r}")
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                # 先查一下这条记录是什么（用于日志）
                cursor.execute("SELECT id, ts_code, name, trade_type, quantity FROM trade_log WHERE id = ?", (log_id,))
                row = cursor.fetchone()
                if not row:
                    logger.error(f"[delete_trade_log] 未找到 id={log_id} 的流水记录")
                    return False
                
                logger.info(f"[delete_trade_log] 删除流水: id={row[0]} {row[1]} {row[3]} {row[4]}股")
                cursor.execute("DELETE FROM trade_log WHERE id = ?", (log_id,))
                logger.info(f"[delete_trade_log] DELETE 影响行数: {cursor.rowcount}")
                
                self._recalculate_balances(cursor)
                conn.commit()
                
                # 🔄 重建持仓表
                self.rebuild_positions_from_logs()
                logger.info(f"[delete_trade_log] 删除完成，持仓表已重建")
                return True
            except Exception as e:
                logger.error(f"[delete_trade_log] 异常: {e}", exc_info=True)
                conn.rollback()
                raise

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
        """返回持仓汇总,包含现金和总资产。"""
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
            # 批量更新:先获取所有需要更新的持仓的成本和数量
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
        根据 trade_log 中的所有 BUY/SELL 记录,全量重新计算 positions 表。
        用途:
        1. 删除/修改交易记录后修复持仓不一致
        2. 数据迁移或手动修复
        3. 定期校验(每周)
        """
        import pandas as pd
        from datetime import datetime

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 读取所有持仓相关交易(包含手续费)
            df = pd.read_sql_query("""
                SELECT ts_code, name, trade_type, quantity, price, amount, transaction_cost
                FROM trade_log
                WHERE trade_type IN ('BUY', 'SELL')
                ORDER BY trade_date ASC, id ASC
            """, conn)

            # 按时间顺序模拟,计算每只股票的最终持仓和成本
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
                        # 异常:卖出数量大于当前持仓,强制清零(该条SELL仍计入,确保最终持仓为0)
                        print(f"⚠️  数据异常:{code} 卖出{qty}股,但仅持有{h['qty']}股,强制清零")
                        h['qty'] = 0
                        h['total_cost'] = 0.0

            # 清空旧持仓
            cursor.execute("DELETE FROM positions")

            # 加载股票代码映射(补全后缀)
            code_map = {}
            try:
                cursor.execute("SELECT ts_code, symbol FROM stocks_basic")
                for row in cursor.fetchall():
                    ts_code, symbol = row
                    code_map[symbol] = ts_code
            except:
                pass

            # 插入新持仓(仅数量 > 0 的)
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
                        INSERT INTO positions (ts_code, name, quantity, cost_price, buy_date, last_updated, target_price, stop_loss_price, highest_since_buy)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ts_code_final, h['name'], h['qty'], round(cost_price, 3),
                        today, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        tp, sl, cost_price  # 买入时的成本价作为初始历史最高价
                    ))
                    inserted += 1

            # 🔄 重建后重算现金余额
            self._recalculate_balances(cursor)

            conn.commit()
            return inserted
