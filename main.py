#!/usr/bin/env python3
"""
股票筛选系统 GUI 主入口

用法：
  python main.py                          # 启动 GUI
  python main.py --help                   # 显示帮助
  python main.py --set-token [token]      # 设置 token（临时）
  python main.py --update-stocks          # 更新基础股票列表
  python main.py --update-daily           # 更新自选股行情数据
  python main.py --download-financial [periods...]  # 下载财务数据
  python main.py --update-financial       # 自动更新财务数据
  python main.py --init-all               # 初始化所有基础数据
  python main.py --test                   # 运行自检

示例：
  python main.py --download-financial 20231231 20241231
  python main.py --update-financial
  python main.py --update-daily
  python main.py --set-token your_token_here
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_usage():
    print("""
用法：
  python main.py                          # 启动 GUI
  python main.py --help                   # 显示帮助
  python main.py --set-token [token]      # 设置 token（临时）
  python main.py --update-stocks          # 更新基础股票列表
  python main.py --update-daily           # 更新自选股日线行情
  python main.py --download-financial [periods...]  # 下载财务数据
  python main.py --update-financial       # 自动更新财务数据
  python main.py --init-all               # 初始化所有基础数据
  python main.py --test                   # 运行自检

示例：
  python main.py --download-financial 20231231 20241231
  python main.py --update-financial
  python main.py --update-stocks
  python main.py --update-daily
  python main.py --set-token your_token_here

注意：
  - TUSHARE_TOKEN 建议设置为环境变量（永久）
  - 首次运行会提示输入 token 并指导设置环境变量
    """)

def test_imports():
    """测试模块导入"""
    print("正在测试模块导入...")
    try:
        import pandas
        print("  ✓ pandas 已安装")
    except ImportError:
        print("  ✗ pandas 未安装")
    
    try:
        import tushare
        print("  ✓ tushare 已安装")
    except ImportError:
        print("  ✗ tushare 未安装")
    
    try:
        from core.financial_data import FinancialDataManager
        print("  ✓ financial_data 模块正常")
    except Exception as e:
        print(f"  ✗ financial_data 模块错误: {e}")
    
    try:
        from core.stock_manager import StockManager
        print("  ✓ stock_manager 模块正常")
    except Exception as e:
        print(f"  ✗ stock_manager 模块错误: {e}")
    
    try:
        from core.daily_data import DailyDataManager
        print("  ✓ daily_data 模块正常")
    except Exception as e:
        print(f"  ✗ daily_data 模块错误: {e}")
    
    try:
        from core.config import config
        print("  ✓ config 模块正常")
    except Exception as e:
        print(f"  ✗ config 模块错误: {e}")

def main():
    args = sys.argv[1:]
    
    if not args:
        print("启动 GUI...")
        try:
            from gui.main_window import MainWindow
            app = MainWindow()
            app.run()
        except ImportError as e:
            print(f"GUI 模块导入失败: {e}")
            print("请先安装依赖: pip install tkinter (通常内置)")
            return 1
        except Exception as e:
            print(f"GUI 启动失败: {e}")
            import traceback
            traceback.print_exc()
            return 1
        return 0
    
    if '--help' in args or '-h' in args:
        print_usage()
        return 0
    
    if '--test' in args:
        test_imports()
        return 0
    
    if '--set-token' in args:
        idx = args.index('--set-token')
        if len(args) > idx + 1:
            token = args[idx + 1]
        else:
            token = input("请输入 TUSHARE_TOKEN: ").strip()
        
        if token:
            os.environ['TUSHARE_TOKEN'] = token
            print(f"✓ TUSHARE_TOKEN 已设置为当前会话环境变量")
            print("  永久设置请运行: scripts/set_token.ps1")
            return 0
        else:
            print("❌ Token 不能为空")
            return 1
    
    # 获取 token 用于后续操作
    from core.config import config
    token = config.get_tushare_token()
    
    if '--update-stocks' in args or '--init-all' in args:
        if not token:
            print("❌ 无法获取 TUSHARE_TOKEN，程序退出")
            return 1
            
        from core.stock_manager import StockManager
        sm = StockManager()
        print(f"[{datetime.now()}] 正在更新股票基础列表...")
        count = sm.update_stocks_list(token)
        if count > 0:
            print(f"✓ 成功更新 {count} 支股票信息")
        
        if '--update-stocks' in args:
            return 0

    if '--update-daily' in args or '--init-all' in args:
        if not token:
            print("❌ 无法获取 TUSHARE_TOKEN，程序退出")
            return 1
            
        from core.watchlist import WatchlistManager
        from core.daily_data import DailyDataManager
        
        wm = WatchlistManager()
        codes = wm.get_all()['ts_code'].tolist()
        
        if codes:
            print(f"[{datetime.now()}] 正在同步 {len(codes)} 支自选股行情...")
            ddm = DailyDataManager()
            count = ddm.sync_daily_data(token, codes)
            print(f"✓ 同步完成，新增 {count} 条行情记录")
        else:
            print(f"[{datetime.now()}] ℹ️ 自选股列表为空，跳过行情同步")
            
        if '--update-daily' in args:
            return 0
            
    # 财务数据相关操作
    if '--download-financial' in args or '--update-financial' in args or '--init-all' in args:
        if not token:
            print("❌ 无法获取 TUSHARE_TOKEN，程序退出")
            return 1
        
        from core.financial_data import FinancialDataManager
        manager = FinancialDataManager()
        
        if '--download-financial' in args:
            idx = args.index('--download-financial')
            periods = args[idx+1:] if len(args) > idx+1 else ['20231231', '20241231']
        elif '--init-all' in args:
            periods = ['20231231', '20241231']
        else:
            periods = None  # --update-financial
        
        if periods:
            print(f"[{datetime.now()}] 开始下载财务数据，periods: {periods}")
            count = manager.download_periods(token, periods)
        else:
            print(f"[{datetime.now()}] 开始自动更新财务数据")
            count = manager.update_latest(token)
        
        if count > 0:
            print(f"[{datetime.now()}] ✅ 完成！新增/更新 {count} 条记录")
            stats = manager.get_statistics()
            print(f"数据库状态：{stats['total_stocks']} 支股票，{stats['total_records']} 条记录")
            print(f"Periods: {', '.join(stats['periods'])}")
            print(f"数据库大小: {stats['db_size_mb']:.1f} MB")
        else:
            print(f"[{datetime.now()}] 无需更新")
        
        return 0
    
    print(f"未知参数: {args}")
    print_usage()
    return 1

if __name__ == '__main__':
    sys.exit(main())
