import argparse
import sys
import os
from pathlib import Path
import logging

# 确保能找到 core 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.watchlist import WatchlistManager
from core.stock_manager import StockManager
from core.daily_data import DailyDataManager
from core.positions import PositionManager
from scripts.gen_stock_report import run_report

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="LW_Stock_System 自动化任务网关 (CLI/AI 友好版)")
    
    # 1. 自选股操作
    parser.add_argument('--add-watchlist', type=str, help="批量添加股票代码，用逗号分隔 (如: 301389.SZ,002463.SZ)")
    parser.add_argument('--group', type=str, default="自选股", help="自选股分组名称 (默认: 自选股)")
    
    # 2. 报告操作
    parser.add_argument('--gen-reports', type=str, choices=['positions', 'watchlist', 'codes'], 
                        help="批量生成报告模式: positions(当前持仓), watchlist(所有自选), codes(指定代码)")
    parser.add_argument('--codes', type=str, help="当模式为 codes 时，指定股票代码列表，逗号分隔")
    
    # 3. 审计与数据同步
    parser.add_argument('--ai-audit', action='store_true', help="运行全账户持仓 AI 智能审计报告")
    parser.add_argument('--sync-market', action='store_true', help="同步全市场最新日线行情数据")

    # 如果没有任何参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()
    wm = WatchlistManager()
    sm = StockManager()
    pm = PositionManager()

    # 执行：批量添加自选
    if args.add_watchlist:
        codes = args.add_watchlist.split(',')
        count = 0
        for code in codes:
            code = code.strip().upper()
            if not code: continue
            info = sm.get_stock_info(code)
            name = info['name'] if info else code
            if wm.add_stock(code, name=name, source=args.group):
                logger.info(f"✓ 已加入: {name} ({code}) -> {args.group}")
                count += 1
        logger.info(f"✅ 批量操作完成：成功添加 {count} 只股票。")

    # 执行：批量生成深度报告
    if args.gen_reports:
        target_codes = []
        if args.gen_reports == 'positions':
            df_pos = pm.get_all()
            if not df_pos.empty:
                target_codes = df_pos['ts_code'].tolist()
                logger.info(f"📍 模式：当前持仓股票 (共 {len(target_codes)} 只)")
            else:
                logger.warning("⚠️ 当前无持仓股票，无法生成报告。")
        elif args.gen_reports == 'watchlist':
            df_watch = wm.get_all()
            if not df_watch.empty:
                target_codes = df_watch['ts_code'].tolist()
                logger.info(f"📍 模式：所有自选股 (共 {len(target_codes)} 只)")
            else:
                logger.warning("⚠️ 自选股列表为空。")
        elif args.gen_reports == 'codes':
            if args.codes:
                target_codes = [c.strip().upper() for c in args.codes.split(',') if c.strip()]
                logger.info(f"📍 模式：手动指定代码 (共 {len(target_codes)} 只)")
            else:
                logger.error("❌ 错误：使用 codes 模式必须提供 --codes 参数。")
        
        if target_codes:
            logger.info(f"🚀 开始批量生成报告，预计耗时 {len(target_codes) * 2} 秒...")
            for code in target_codes:
                try:
                    # 调用之前写好的生成逻辑
                    run_report(code)
                except Exception as e:
                    logger.error(f"❌ {code} 生成失败: {e}")
            logger.info("✅ 批量报告生成任务结束。请在 output/reports/ 查看。")

    # 执行：AI 审计 (持仓复盘)
    if args.ai_audit:
        logger.info("🤖 启动持仓 AI 智能审计流水线...")
        import subprocess
        # 设置 PYTHONPATH 确保脚本能找到 core 模块
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        try:
            subprocess.run([sys.executable, "scripts/prepare_ai_analysis.py"], env=env, check=True)
            logger.info("✅ AI 审计报告生成成功！路径: output/reports/AI_Audit_Report.md")
        except Exception as e:
            logger.error(f"❌ AI 审计运行失败: {e}")

    # 执行：全市场行情同步
    if args.sync_market:
        from core.config import config
        token = config.get_tushare_token()
        if not token:
            logger.error("❌ 未找到 TUSHARE_TOKEN，请检查环境变量或配置文件。")
            return
        
        ddm = DailyDataManager()
        logger.info("🔄 正在从 Tushare 云端同步全市场最新日线行情...")
        try:
            count = ddm.sync_market_data(token)
            logger.info(f"✅ 行情同步完成，本地数据库新增 {count} 条记录。")
        except Exception as e:
            logger.error(f"❌ 行情同步失败: {e}")

if __name__ == "__main__":
    main()
