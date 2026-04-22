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
    def price_to_52w_high(close, daily_df):
        """
        计算当前价距52周高点的百分比距离。
        close: 当前收盘价（scalar）
        daily_df: 含 'high' 和 'trade_date' 列的 DataFrame，必须已按日期升序排列
        返回: (距52周高点百分比, 52周高点价格)，若无数据返回 (nan, nan)
        """
        if daily_df is None or daily_df.empty or pd.isna(close) or close <= 0:
            return np.nan, np.nan
        recent = daily_df.tail(252)
        if len(recent) < 20:
            return np.nan, np.nan
        high_52w = recent['high'].max()
        if high_52w <= 0:
            return np.nan, np.nan
        pct = (close - high_52w) / high_52w * 100  # 负值=低于高点
        return pct, high_52w

    @staticmethod
    def price_to_52w_low(close, daily_df):
        """
        计算当前价距52周低点的百分比距离（高于低点多少%）。
        close: 当前收盘价（scalar）
        daily_df: 含 'low' 和 'trade_date' 列的 DataFrame，必须已按日期升序排列
        返回: (距52周低点百分比, 52周低点价格)，若无数据返回 (nan, nan)
        """
        if daily_df is None or daily_df.empty or pd.isna(close) or close <= 0:
            return np.nan, np.nan
        recent = daily_df.tail(252)
        if len(recent) < 20:
            return np.nan, np.nan
        low_52w = recent['low'].min()
        if low_52w <= 0:
            return np.nan, np.nan
        pct = (close - low_52w) / low_52w * 100  # 正值=高于低点
        return pct, low_52w

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

        # 52周高低点距离
        close = df['close'].iloc[-1]
        pct_from_52w, high_52w = Indicators.price_to_52w_high(close, df)
        pct_from_52w_low, low_52w = Indicators.price_to_52w_low(close, df)
        res['pct_from_52w_high'] = pct_from_52w
        res['high_52w'] = high_52w
        res['pct_from_52w_low'] = pct_from_52w_low
        res['low_52w'] = low_52w

        return res
