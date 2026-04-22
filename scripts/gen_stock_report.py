import os
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path
import json

def get_token():
    # 优先从环境变量获取
    token = os.environ.get('TUSHARE_TOKEN', '').strip()
    if token:
        return token
    
    # 尝试从本地配置文件获取
    paths = [
        Path('config/app_config.json'),
        Path('config/app_settings.json')
    ]
    for p in paths:
        if p.exists():
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    # 某些配置可能存在不同 key
                    t = cfg.get('tushare_token') or cfg.get('token')
                    if t: return t
            except: pass
    return None

def get_technical_data(pro, ts_code):
    """获取技术面核心指标"""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=600)).strftime('%Y%m%d') # 稍微多取一点数据
    
    # 1. 日线行情 (包含价格、成交量、成交额)
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty: return None
    df = df.sort_values('trade_date')
    
    # 2. 每日指标 (PE/PB/市值)
    df_basic = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date, 
                              fields='trade_date,pe_ttm,pb,total_mv')
    df_basic = df_basic.sort_values('trade_date')
    
    # 计算 MA
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['ma240'] = df['close'].rolling(240).mean()
    
    # 计算 RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 计算 52周 (一年) 和 半年 高低点
    # 假设一年约 250 个交易日，半年约 120 个交易日
    df_1y = df.tail(250)
    df_6m = df.tail(120)
    
    high_52w = df_1y['high'].max()
    low_52w = df_1y['low'].min()
    high_6m = df_6m['high'].max()
    low_6m = df_6m['low'].min()
    
    last = df.iloc[-1]
    # 匹配日期获取 basic
    last_basic = df_basic[df_basic['trade_date'] == last['trade_date']].iloc[-1] if not df_basic.empty else None
    
    return {
        'price': last['close'],
        'ma20': last.get('ma20', 0),
        'ma60': last.get('ma60', 0),
        'ma240': last.get('ma240', 0),
        'rsi': last.get('rsi', 50),
        'pe_ttm': last_basic['pe_ttm'] if last_basic is not None else 0,
        'pb': last_basic['pb'] if last_basic is not None else 0,
        'total_mv': (last_basic['total_mv'] / 10000) if last_basic is not None else 0, # 亿元
        'vol': last['vol'],
        'amount': (last['amount'] / 100000), # 亿元
        'trade_date': last['trade_date'],
        'high_52w': high_52w,
        'low_52w': low_52w,
        'high_6m': high_6m,
        'low_6m': low_6m
    }

def get_financial_report(pro, ts_code):
    """获取硬核财务数据 (最近8期) - 包含研发绝对值与环比增长"""
    # 1. 抓取四张原始表
    try: df_inc = pro.income(ts_code=ts_code, fields='end_date,total_revenue,n_income,rd_exp')
    except: df_inc = pd.DataFrame()
    
    try: df_bal = pro.balancesheet(ts_code=ts_code, fields='end_date,total_assets,total_liab')
    except: df_bal = pd.DataFrame()
    
    try: df_cash = pro.cashflow(ts_code=ts_code, fields='end_date,n_cashflow_act,c_pay_acq_const_fiolta')
    except: df_cash = pd.DataFrame()
    
    # 增加环比字段: tr_qoq, n_income_qoq
    try: df_ind = pro.fina_indicator(ts_code=ts_code, fields='end_date,roe_dt,grossprofit_margin,netprofit_margin,tr_yoy,n_income_yoy,tr_qoq,n_income_qoq')
    except: df_ind = pd.DataFrame()
    
    # 2. 收集所有非空的报告期
    all_dates = set()
    raw_dfs = [df_inc, df_bal, df_cash, df_ind]
    for d in raw_dfs:
        if d is not None and not d.empty and 'end_date' in d.columns:
            all_dates.update(d['end_date'].dropna().tolist())
    
    if not all_dates:
        print(f"Warning: {ts_code} 未查询到任何财务报告期数据。")
        return None

    # 3. 以日期为基准进行外连接合并
    df_final = pd.DataFrame({'end_date': sorted(list(all_dates), reverse=True)})
    
    for i, d in enumerate(raw_dfs):
        if d is not None and not d.empty:
            d = d.drop_duplicates('end_date')
            df_final = pd.merge(df_final, d, on='end_date', how='left')
    
    # 4. 补全缺失列并填充 0
    required_cols = [
        'total_revenue', 'n_income', 'rd_exp', 
        'total_assets', 'total_liab', 
        'n_cashflow_act', 'c_pay_acq_const_fiolta',
        'roe_dt', 'grossprofit_margin', 'netprofit_margin',
        'tr_yoy', 'n_income_yoy', 'tr_qoq', 'n_income_qoq'
    ]
    for col in required_cols:
        if col not in df_final.columns:
            df_final[col] = 0
    
    df_final = df_final.fillna(0).head(8) 
    
    # 5. 计算衍生指标
    df_final['debt_to_assets'] = np.where(df_final['total_assets'] != 0, 
                                         (df_final['total_liab'] / df_final['total_assets']) * 100, 0)
    df_final['rd_intensity'] = np.where(df_final['total_revenue'] != 0,
                                       (df_final['rd_exp'] / df_final['total_revenue']) * 100, 0)
    
    # 重命名方便正文渲染
    df_final = df_final.rename(columns={'end_date': 'period'})
    return df_final

def safe_val(val, fmt="{:.2f}", default="-"):
    """安全格式化数值，处理 None 和 NaN"""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return fmt.format(val)
    except:
        return str(val)

def run_report(ts_code, name=None):
    token = get_token()
    if not token:
        print("Error: Tushare token not found.")
        return
    
    pro = ts.pro_api(token)
    
    # 如果没传名称，自动查一下
    if not name:
        basic = pro.stock_basic(ts_code=ts_code, fields='name')
        name = basic['name'].iloc[0] if not basic.empty else ts_code

    print(f"正在生成 {name} ({ts_code}) 的深度报告...")
    
    tech = get_technical_data(pro, ts_code)
    fin = get_financial_report(pro, ts_code)
    
    if tech is None or fin is None:
        print("数据获取失败，请检查网络或 Token 权限。")
        return

    now_date = datetime.now().strftime('%Y-%m-%d')
    latest_period = fin['period'].iloc[0]
    
    p_str = f"{latest_period[:4]}-{latest_period[4:6]}-{latest_period[6:]}"
    filename = f"{now_date}-{ts_code}_{name}_财务深度分析.md"
    
    output_dir = Path("output/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# 🔍 {name} ({ts_code}) 深度财务体检报告\n\n")
        f.write(f"**报告生成日期:** {now_date} | **最新交易日:** {tech['trade_date']}\n\n")
        f.write(f"> **依据最新财报 {p_str} 数据生成**\n\n")
        
        f.write("## 📈 技术面即时看板 (Real-time Technical)\n")
        f.write("| 指标 | 当前值 | 状态/备注 |\n")
        f.write("| :--- | :--- | :--- |\n")
        f.write(f"| **最新收盘价** | {safe_val(tech['price'])} | |\n")
        f.write(f"| **52周 最高/最低** | {safe_val(tech['high_52w'])} / {safe_val(tech['low_52w'])} | 距离最高点跌幅 {safe_val((tech['price']/tech['high_52w']-1)*100)}% |\n")
        f.write(f"| **近6个月 最高/最低** | {safe_val(tech['high_6m'])} / {safe_val(tech['low_6m'])} | |\n")
        f.write(f"| **MA20 (20日线)** | {safe_val(tech['ma20'])} | {'上方' if tech['price'] > tech['ma20'] else '下方'} |\n")
        f.write(f"| **MA60 (决策线)** | {safe_val(tech['ma60'])} | {'强势' if tech['price'] > tech['ma60'] else '整理'} |\n")
        f.write(f"| **MA240 (牛熊线)** | {safe_val(tech['ma240'])} | {'牛市区域' if tech['price'] > tech['ma240'] else '熊市区域'} |\n")
        f.write(f"| **RSI (14)** | {safe_val(tech['rsi'])} | {'超买(>70)' if tech['rsi'] > 70 else '超卖(<30)' if tech['rsi'] < 30 else '中性'} |\n")
        f.write(f"| **PE (TTM)** | {safe_val(tech['pe_ttm'])} | {'未盈利' if tech['pe_ttm'] is None else ''} |\n")
        f.write(f"| **PB (市净率)** | {safe_val(tech['pb'])} | |\n")
        f.write(f"| **总市值 (亿)** | {safe_val(tech['total_mv'])} | |\n")
        f.write(f"| **当日成交额 (亿)** | {safe_val(tech['amount'])} | |\n\n")

        # 核心增长率表格 (增加环比)
        f.write("## 📊 季度核心成长指标 (Quarterly Growth)\n")
        f.write("| 报告期 | 营收(亿) | 同比% | 环比% | 净利润(万) | 同比% | 环比% | ROE_dt% |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for _, row in fin.head(6).iterrows():
            f.write(f"| {row['period']} | {safe_val(row['total_revenue']/1e8)} | {safe_val(row['tr_yoy'])} | {safe_val(row['tr_qoq'])} | {safe_val(row['n_income']/1e4, fmt='{:.0f}')} | {safe_val(row['n_income_yoy'])} | {safe_val(row['n_income_qoq'])} | {safe_val(row['roe_dt'])} |\n")
        
        # 财务质量表 (增加研发费用绝对值)
        f.write("\n## 💰 财务质量趋势 (Financial Quality - 近8期)\n")
        f.write("| 报告期 | 毛利率% | 净利率% | 负债率% | 研发费用(万) | 研发强度% | 经营现金流(万) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for _, row in fin.iterrows():
            f.write(f"| {row['period']} | {safe_val(row['grossprofit_margin'])} | {safe_val(row['netprofit_margin'])} | {safe_val(row['debt_to_assets'])} | {safe_val(row['rd_exp']/1e4, fmt='{:.0f}')} | {safe_val(row['rd_intensity'])} | {safe_val(row['n_cashflow_act']/1e4, fmt='{:.0f}')} |\n")
        
        f.write("\n\n----- \n")
        f.write("### 💡 专家提示：\n")
        f.write("1. **高位回撤：** 若当前价距离 52周最高点回撤超过 30% 且基本面（如季度营收环比）出现好转，可能是左侧埋伏机会。\n")
        f.write("2. **营收与净利错配：** 若营收增长远高于净利增长，需警惕毛利率下滑或费用失控。\n")
        f.write("3. **收现比：** 建议结合经营现金流与净利润对比，现金流/净利润 > 1 通常意味着利润含金量高。\n")
        f.write("4. **研发强度：** 高科技企业通常维持在 15% 以上。\n\n")
        f.write("*报告由 LW_Stock_System 自动生成，数据来源 Tushare。*")
    
    print(f"✅ 报告生成成功: {output_path}")

if __name__ == "__main__":
    import sys
    import io
    
    # 强制 stdout 使用 utf-8 并在 Windows 上尝试兼容 gbk
    # 这在 Popen 捕获输出时能减少很多麻烦
    try:
        if sys.platform == 'win32':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass

    code = sys.argv[1] if len(sys.argv) > 1 else '301389.SZ'
    run_report(code)
