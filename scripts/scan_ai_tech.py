"""
AI科技股投资系统 - 完整选股扫描器
基于《A股科技股投资系统建设报告》的策略逻辑

功能：
1. 从AI硬件 + 人形机器人板块扫描
2. 财务指标过滤（扣非净利增速、毛利率、ROE等）
3. 技术指标过滤（均线多头、RSI区间、成交量放大、52周高点距离）
4. 仓位分配建议（AI硬件65% / 机器人30%）
5. 输出评分排名
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "database"
SYS_CONFIG = PROJECT_ROOT / "config" / "app_settings.json"
STRATEGY_FILE = PROJECT_ROOT / "config" / "strategies" / "AI科技股投资系统.json"


class A股Scanner:
    """AI科技股投资系统 - 选股扫描器"""

    def __init__(self):
        self.conn_stock = sqlite3.connect(str(DB_PATH / "stock_data.db"))
        self.conn_fin = sqlite3.connect(str(DB_PATH / "financial_data.db"))
        self.conn_daily = sqlite3.connect(str(DB_PATH / "daily_data.db"))
        self.strategy = self._load_strategy()
        self.results = []

    def _load_strategy(self):
        if STRATEGY_FILE.exists():
            with open(STRATEGY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    # ---- 板块/标签过滤 ----
    def _get_sector_stocks(self, sector_name):
        """根据板块名称或标签获取股票列表"""
        conn = self.conn_stock
        
        # 如果是标签池（tag:开头），从stock_tags表查询
        if sector_name.startswith("tag:"):
            tag_name = sector_name[4:]
            df = pd.read_sql_query(
                "SELECT st.ts_code, w.name, ? as sector FROM stock_tags st "
                "LEFT JOIN watchlist w ON w.ts_code = st.ts_code "
                "WHERE st.tag_name = ?",
                conn, params=(sector_name, tag_name)
            )
            # 处理没有对应watchlist记录的股票（从stocks_basic补全名称）
            if df.empty:
                return df
            # 补充名称为空的
            missing = df[df['name'].isna()]
            if not missing.empty:
                cur = conn.execute(
                    "SELECT ts_code, name FROM stocks_basic WHERE ts_code IN (" 
                    + ",".join("?"*len(missing)) + ")",
                    [r for r in missing['ts_code']]
                )
                name_map = {r[0]: r[1] for r in cur.fetchall()}
                for idx in missing.index:
                    ts = missing.loc[idx, 'ts_code']
                    if ts in name_map:
                        df.loc[idx, 'name'] = name_map[ts]
            return df
        
        # 普通板块：从 watchlist 读取用户自定义板块
        df = pd.read_sql_query(
            "SELECT ts_code, name, sector FROM watchlist WHERE sector LIKE ?",
            conn, params=(f"%{sector_name}%",)
        )
        if df.empty:
            # 尝试模糊匹配行业字段
            df = pd.read_sql_query(
                "SELECT ts_code, name, industry as sector FROM stocks_basic WHERE industry LIKE ?",
                conn, params=(f"%{sector_name}%",)
            )
        return df

    # ---- 财务过滤 ----
    def _get_latest_financial(self, ts_code):
        """获取最新财报（单季度）"""
        df = pd.read_sql_query("""
            SELECT * FROM financial_indicators
            WHERE ts_code = ? AND period = (
                SELECT MAX(period) FROM financial_indicators WHERE ts_code = ?
            )
            LIMIT 1
        """, self.conn_fin, params=(ts_code, ts_code))
        return df.iloc[0] if not df.empty else None

    def _financial_filter(self, fin_row):
        """检查财务指标是否满足条件"""
        if fin_row is None:
            return False, "无财务数据"
        p = self.strategy.get('params', {}).get('financial_filters', {})

        # 扣非净利增速
        dt_netprofit_yoy = fin_row.get('dt_netprofit_yoy')
        min_yoy = p.get('dt_netprofit_yoy_min', 30)
        if dt_netprofit_yoy is None or pd.isna(dt_netprofit_yoy):
            return False, "无扣非净利增速"
        if dt_netprofit_yoy < min_yoy:
            return False, f"扣非净利增速{dt_netprofit_yoy:.1f}% < {min_yoy}%"

        # 毛利率
        gpm = fin_row.get('grossprofit_margin')
        min_gpm = p.get('grossprofit_margin_min', 25)
        if gpm is not None and not pd.isna(gpm) and gpm < min_gpm:
            return False, f"毛利率{gpm:.1f}% < {min_gpm}%"

        # ROE
        roe_dt = fin_row.get('roe_dt')
        min_roe = p.get('roe_dt_min', 15)
        if roe_dt is not None and not pd.isna(roe_dt) and roe_dt < min_roe:
            return False, f"ROE{roe_dt:.1f}% < {min_roe}%"

        # 资产负债率
        debt_ratio = fin_row.get('debt_to_assets')
        max_debt = p.get('debt_to_assets_max', 65)
        if debt_ratio is not None and not pd.isna(debt_ratio) and debt_ratio > max_debt:
            return False, f"资产负债率{debt_ratio:.1f}% > {max_debt}%"

        # 净利润为正（必须是盈利的）
        netprofit = fin_row.get('dt_netprofit_yoy')  # 用增速字段间接验证
        # 更准确：检查营收
        return True, "OK"

    # ---- 技术指标计算 ----
    def _get_daily_data(self, ts_code, days=252):
        """获取最近N个交易日日线数据"""
        df = pd.read_sql_query("""
            SELECT * FROM daily_trade
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT ?
        """, self.conn_daily, params=(ts_code, days))
        if df.empty:
            return None
        return df.sort_values('trade_date', ascending=True).reset_index(drop=True)

    def _tech_filter(self, ts_code):
        """检查技术指标是否满足条件"""
        daily = self._get_daily_data(ts_code, 260)
        if daily is None or len(daily) < 60:
            return False, "无足够日线数据", {}

        sys.path.insert(0, str(PROJECT_ROOT))
        from core.indicators import Indicators

        tp = self.strategy.get('params', {}).get('tech_params', {})
        if not tp:
            tp = {
                'ma_periods': [50, 150, 200],
                'rsi_periods': [6, 12],
                'vma_periods': [5, 10]
            }

        signals = Indicators.get_signals(daily, tp)
        tech_p = self.strategy.get('params', {}).get('tech_params', {})

        # 1. 均线多头排列
        if tech_p.get('require_ma_order') and not signals.get('ma_long_order', False):
            return False, "均线未多头排列", signals

        # 2. RSI区间
        rsi_s_min = tech_p.get('rsi_s_min', 50)
        rsi_s_max = tech_p.get('rsi_s_max', 85)
        rsi_val = signals.get('rsi6', 50)
        if rsi_val < rsi_s_min or rsi_val > rsi_s_max:
            return False, f"RSI({rsi_val:.1f})不在{rsi_s_min}-{rsi_s_max}区间", signals

        # 3. 成交量放大（VMA金叉）
        if tech_p.get('require_vma_cross') and not signals.get('vma_gold_cross', False):
            return False, "成交量未放大", signals

        # 4. 52周高点距离
        price_vs_52w = signals.get('pct_from_52w_high', 0)
        max_pct = tech_p.get('price_vs_52w_high_pct_max', 25)
        if price_vs_52w is not None and not pd.isna(price_vs_52w):
            # pct_from_52w_high 是负值（低于高点）
            pct_below = abs(price_vs_52w)
            if pct_below > max_pct:
                return False, f"距52周高点{pct_below:.1f}% > {max_pct}%", signals

        return True, "OK", signals

    # ---- 板块配置 ----
    def _get_sector_config(self):
        """获取板块配置（支持标签池）"""
        params = self.strategy.get('params', {})
        sectors = params.get('sectors', ['AI 硬件'])
        tag_pools = params.get('tag_pools', [])
        
        # 合并：普通板块 + 标签板块（tag:前缀）
        all_groups = sectors.copy()
        for tag in tag_pools:
            tag_key = f"tag:{tag}"
            if tag_key not in all_groups:
                all_groups.append(tag_key)
        
        weights = {
            'AI 硬件': params.get('position_rules', {}).get('ai_hardware_weight', 65),
            '人形机器人': params.get('position_rules', {}).get('robot_weight', 30),
        }
        return all_groups, weights

    # ---- 扫描主函数 ----
    def scan(self, sector=None):
        """执行扫描"""
        sectors, weights = self._get_sector_config()
        target_sectors = [sector] if sector else sectors
        all_passed_dict = {}  # ts_code -> item (去重字典)

        for sec in target_sectors:
            stocks = self._get_sector_stocks(sec)
            # 干净的分隔名称（用于显示）
            disp_name = sec[4:] if sec.startswith("tag:") else sec
            print(f"\n📊 扫描板块: {disp_name} ({len(stocks)} 只股票)")

            for _, row in stocks.iterrows():
                ts_code = row['ts_code']
                name = row['name'] or ""

                # 跳过已有的（已通过其他板块找到的不要重复添加）
                if ts_code in all_passed_dict:
                    continue

                # 财务过滤
                fin = self._get_latest_financial(ts_code)
                fin_ok, fin_msg = self._financial_filter(fin)

                # 技术过滤
                tech_ok, tech_msg, signals = self._tech_filter(ts_code)

                if fin_ok and tech_ok:
                    pct_from_52w = signals.get('pct_from_52w_high', 0)
                    rsi6 = signals.get('rsi6', 0)
                    rsi12 = signals.get('rsi12', 0)
                    ma_long = signals.get('ma_long_order', False)
                    vma_cross = signals.get('vma_gold_cross', False)
                    ma50 = signals.get('ma50', 0)
                    ma150 = signals.get('ma150', 0)
                    ma200 = signals.get('ma200', 0)

                    # 计算综合评分（100分制）
                    score = 0
                    if fin is not None:
                        # 扣非净利增速（最多30分）
                        yoy = fin.get('dt_netprofit_yoy', 0) or 0
                        score += min(30, yoy * 0.6)
                        # 毛利率（最多20分）
                        gpm = fin.get('grossprofit_margin', 0) or 0
                        score += min(20, gpm * 0.4) if gpm > 0 else 0
                        # ROE（最多20分）
                        roe = fin.get('roe_dt', 0) or 0
                        score += min(20, roe * 0.8)

                    # 技术指标（最多30分）
                    if ma_long: score += 10
                    if rsi6 >= 50 and rsi6 <= 70: score += 8  # 最佳启动区
                    if vma_cross: score += 7
                    if pct_from_52w is not None and abs(pct_from_52w) <= 15: score += 5

                    all_passed_dict[ts_code] = {
                        'ts_code': ts_code,
                        'name': name,
                        'sector': disp_name,
                        'score': round(score, 1),
                        'pct_from_52w': round(abs(pct_from_52w), 2) if pct_from_52w else None,
                        'rsi6': round(rsi6, 1),
                        'ma_long': ma_long,
                        'vma_cross': vma_cross,
                        'dt_netprofit_yoy': fin.get('dt_netprofit_yoy') if fin is not None else None,
                        'grossprofit_margin': fin.get('grossprofit_margin') if fin is not None else None,
                        'roe_dt': fin.get('roe_dt') if fin is not None else None,
                        'fin_msg': fin_msg,
                        'tech_msg': tech_msg,
                    }

        # 按评分排序
        all_passed = sorted(all_passed_dict.values(), key=lambda x: x['score'], reverse=True)
        self.results = all_passed
        return all_passed

    # ---- 输出报告 ----
    def print_report(self):
        """打印扫描报告"""
        if not self.results:
            print("\n⚠️ 没有找到符合条件的股票")
            return

        print(f"\n{'='*80}")
        print(f"AI科技股投资系统 - 扫描报告")
        print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*80}")
        print(f"\n✅ 符合条件股票共 {len(self.results)} 只：\n")

        print(f"{'序号':<4} {'股票名称':<12} {'所属板块':<10} {'综合评分':<8} {'距52周高点':<10} {'RSI(6)':<8} {'扣非净利增速':<12} {'毛利率':<8}")
        print('-' * 90)

        for i, r in enumerate(self.results):
            yoy = f"{r['dt_netprofit_yoy']:.1f}%" if r.get('dt_netprofit_yoy') else '-'
            gpm = f"{r['grossprofit_margin']:.1f}%" if r.get('grossprofit_margin') else '-'
            pct = f"{r['pct_from_52w']}%" if r.get('pct_from_52w') is not None else '-'
            print(
                f"{i+1:<4} {r['name']:<12} {r['sector']:<10} {r['score']:<8.1f} "
                f"{pct:<10} {r['rsi6']:<8.1f} {yoy:<12} {gpm:<8}"
            )

        # 分类别建议仓位
        ai_hw = [r for r in self.results if r['sector'] == 'AI 硬件']
        robot = [r for r in self.results if r['sector'] == '人形机器人']

        print(f"\n{'='*80}")
        print("📌 仓位分配建议（基于25万本金）")
        print(f"{'='*80}")

        if ai_hw:
            print(f"\n🤖 AI硬件（建议65% ≈ 16万元，最多3-4只）")
            per_stock = 160000 / min(len(ai_hw), 4)
            for i, r in enumerate(ai_hw[:4]):
                print(f"  {i+1}. {r['name']} ({r['ts_code']}) - 评分{r['score']:.1f} - 建议仓位约{per_stock/10000:.1f}万元")

        if robot:
            print(f"\n🔧 人形机器人（建议30% ≈ 7.5万元，最多2只）")
            per_stock = 75000 / min(len(robot), 2)
            for i, r in enumerate(robot[:2]):
                print(f"  {i+1}. {r['name']} ({r['ts_code']}) - 评分{r['score']:.1f} - 建议仓位约{per_stock/10000:.1f}万元")

        print(f"\n💰 现金储备（5% ≈ 1.25万元）")

        print(f"\n{'='*80}")
        print("⚠️ 风险提示：以上仅为系统筛选结果，不构成投资建议")
        print(f"{'='*80}")

    def save_report(self, path=None):
        """保存报告到文件"""
        if not self.results:
            return
        if path is None:
            path = PROJECT_ROOT / "output" / "reports" / f"AI科技股扫描报告_{datetime.now().strftime('%Y%m%d')}.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# AI科技股投资系统 - 扫描报告",
            f"",
            f"**扫描时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**符合条件股票**: {len(self.results)} 只",
            f"",
            f"## 评分排名",
            f"",
            f"| 序号 | 股票代码 | 名称 | 板块 | 综合评分 | 距52周高点 | RSI(6) | 均线多头 | 放量突破 | 扣非净利增速 | 毛利率 | ROE |",
            f"|---|---|---|---|---|---|---|---|---|---|---|---|---|"
        ]
        for i, r in enumerate(self.results):
            yoy = f"{r['dt_netprofit_yoy']:.1f}%" if r.get('dt_netprofit_yoy') else '-'
            gpm = f"{r['grossprofit_margin']:.1f}%" if r.get('grossprofit_margin') else '-'
            roe = f"{r['roe_dt']:.1f}%" if r.get('roe_dt') else '-'
            pct = f"{r['pct_from_52w']}%" if r.get('pct_from_52w') is not None else '-'
            lines.append(
                f"| {i+1} | {r['ts_code']} | {r['name']} | {r['sector']} | {r['score']:.1f} | "
                f"{pct} | {r['rsi6']} | {'是' if r['ma_long'] else '否'} | {'是' if r['vma_cross'] else '否'} | "
                f"{yoy} | {gpm} | {roe} |"
            )

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"✅ 报告已保存: {path}")


def main():
    scanner = A股Scanner()
    results = scanner.scan()
    scanner.print_report()
    scanner.save_report()
    return results


if __name__ == "__main__":
    main()
