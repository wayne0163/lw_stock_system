# core/indicators.py - 全功能动态引擎
import pandas as pd
import numpy as np

class Indicators:
    """技术指标计算工具类 - 全参数动态化"""
    
    @staticmethod
    def rsi(series, period=14):
        if len(series) < period: return pd.Series([np.nan] * len(series))
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        # RSI 除零保护
        loss = loss.replace(0, 0.001)
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def ma(series, period=20):
        return series.rolling(window=period).mean()

    @staticmethod
    def get_signals(df, tp):
        """
        tp (tech_params): {
            'ma_periods': [20, 120, 240],
            'rsi_periods': [6, 12],
            'vma_periods': [5, 10]
        }
        """
        if df is None or df.empty: return {}
        df = df.copy().sort_values('trade_date', ascending=True)
        count = len(df)
        res = {}

        # 1. 价格均线
        ma_p = tp.get('ma_periods', [20, 120, 240])
        for p in ma_p:
            col = f'ma{p}'
            df[col] = Indicators.ma(df['close'], p)
            res[col] = df[col].iloc[-1] if count >= p else df['close'].iloc[-1]

        # 2. RSI 
        rsi_p = tp.get('rsi_periods', [6, 12])
        for p in rsi_p:
            col = f'rsi{p}'
            df[col] = Indicators.rsi(df['close'], p)
            val = df[col].iloc[-1]
            res[col] = val if not pd.isna(val) else 50

        # 3. 成交量均线 (VMA)
        vma_p = tp.get('vma_periods', [5, 10])
        for p in vma_p:
            col = f'vma{p}'
            df[col] = Indicators.ma(df['vol'], p)
            res[col] = df[col].iloc[-1] if count >= p else df['vol'].iloc[-1]

        # --- 逻辑信号 ---
        # 均线多头 (短 > 中 > 长)
        mas = [res.get(f'ma{p}', 0) for p in ma_p]
        res['ma_long_order'] = all(mas[i] > mas[i+1] for i in range(len(mas)-1)) if len(mas) >= 2 else False
        
        # RSI 状态
        res['rsi_gold_cross'] = res.get(f'rsi{rsi_p[0]}', 0) > res.get(f'rsi{rsi_p[1]}', 0) if len(rsi_p) >= 2 else False
        
        # 成交量状态 (VMA 短 > 长)
        res['vma_gold_cross'] = res.get(f'vma{vma_p[0]}', 0) > res.get(f'vma{vma_p[1]}', 0) if len(vma_p) >= 2 else False
        
        return res
