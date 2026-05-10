# gui/stock_chart.py
# K线图 + 成交量 + RSI 图表对话框

import tkinter as tk
from tkinter import ttk
import sqlite3
import pandas as pd
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.daily_data import DailyDataManager
from gui.theme import Colors, Fonts
from gui.utils import center_window


def show_stock_chart(parent, ts_code, name=None):
    """弹出股票K线图窗口"""
    dialog = tk.Toplevel(parent)
    title = f"{name or ts_code} K线图" if name else f"{ts_code} K线图"
    dialog.title(title)
    dialog.geometry("1000x700")
    dialog.minsize(800, 550)
    dialog.transient(parent)
    dialog.grab_set()

    # 顶部信息栏
    header = ttk.Frame(dialog, padding=(15, 10, 15, 5))
    header.pack(fill=tk.X)

    lbl_title = ttk.Label(header, text=title, font=Fonts.CN_TITLE,
                          foreground=Colors.PRIMARY_DARK)
    lbl_title.pack(side=tk.LEFT)

    status_var = tk.StringVar(value="正在加载数据...")
    lbl_status = ttk.Label(header, textvariable=status_var, font=Fonts.UI_SMALL,
                           foreground=Colors.TEXT_SECONDARY)
    lbl_status.pack(side=tk.RIGHT, padx=10)

    # 图表容器
    chart_frame = ttk.Frame(dialog, padding=(15, 5, 15, 10))
    chart_frame.pack(fill=tk.BOTH, expand=True)

    center_window(dialog, parent)

    # 后台加载数据并绘图
    def load_worker():
        try:
            daily_mgr = DailyDataManager()
            with sqlite3.connect(daily_mgr.db_path) as conn:
                df = pd.read_sql_query(
                    """SELECT trade_date, open, high, low, close, vol
                       FROM daily_trade
                       WHERE ts_code = ?
                       ORDER BY trade_date DESC
                       LIMIT 350""",
                    conn, params=(ts_code,)
                )

            if df.empty:
                dialog.after(0, lambda: status_var.set("❌ 无行情数据"))
                return

            df = df.sort_values('trade_date').reset_index(drop=True)

            # 计算基本信息
            latest = df.iloc[-1]
            highest = df['high'].max()
            lowest = df['low'].min()
            pct_chg = ((latest['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close'] * 100) if len(df) > 1 else 0

            info_text = (f" 最新: {latest['close']:.2f}  "
                         f"涨跌: {pct_chg:+.2f}%  "
                         f"最高: {highest:.2f}  "
                         f"最低: {lowest:.2f}  "
                         f"成交量: {latest['vol']:.0f}")

            # 准备 mplfinance 数据
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df_mpl = df.rename(columns={
                'trade_date': 'Date', 'open': 'Open', 'high': 'High',
                'low': 'Low', 'close': 'Close', 'vol': 'Volume'
            })
            df_mpl.set_index('Date', inplace=True)

            # 计算 RSI
            def calc_rsi(series, period=14):
                delta = series.diff()
                gain = delta.clip(lower=0)
                loss = -delta.clip(upper=0)
                avg_gain = gain.rolling(window=period, min_periods=period).mean()
                avg_loss = loss.rolling(window=period, min_periods=period).mean()
                rs = avg_gain / avg_loss.replace(0, 1e-10)
                return 100 - (100 / (1 + rs))

            rsi = calc_rsi(df_mpl['Close'])
            latest_rsi = rsi.iloc[-1]

            # 绘图（必须在主线程）
            dialog.after(0, lambda: _plot_chart(
                dialog, chart_frame, df_mpl, rsi, info_text, latest_rsi, status_var
            ))

        except Exception as e:
            import traceback
            traceback.print_exc()
            dialog.after(0, lambda: status_var.set(f"❌ 加载失败: {e}"))

    import threading
    threading.Thread(target=load_worker, daemon=True).start()


def _plot_chart(dialog, chart_frame, df, rsi, info_text, latest_rsi, status_var):
    """在主线程中绘制图表"""
    # 延迟导入，避免拖慢启动
    import matplotlib
    matplotlib.use('TkAgg')
    matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
    matplotlib.rcParams['axes.unicode_minus'] = False

    import mplfinance as mpf

    # 构建自定义样式
    mc = mpf.make_marketcolors(
        up='red', down='green',
        wick={'up': 'red', 'down': 'green'},
        volume={'up': '#ff6b6b', 'down': '#51cf66'},
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridaxis='both', gridstyle=':',
        gridcolor='#e0dcd4',
        facecolor='#ffffff',
        edgecolor='#e0dcd4',
        figcolor='#f5f3ef',
        rc={
            'font.family': 'Microsoft YaHei',
            'axes.unicode_minus': False,
        }
    )

    # 构建 RSI addplot
    rsi_ma = rsi.rolling(window=6).mean()
    ap_rsi = mpf.make_addplot(
        rsi, panel=2, color='#0d6efd', width=1.2,
        ylabel='RSI'
    )
    ap_rsi_ma = mpf.make_addplot(
        rsi_ma, panel=2, color='#fd7e14', width=0.8, alpha=0.7
    )

    # 添加 RSI 超买超卖线
    ap_ob = mpf.make_addplot(
        pd.Series(70, index=df.index), panel=2,
        color='#dc3545', width=0.6, alpha=0.4, secondary_y=False
    )
    ap_os = mpf.make_addplot(
        pd.Series(30, index=df.index), panel=2,
        color='#28a745', width=0.6, alpha=0.4, secondary_y=False
    )

    # 创建图表
    fig, axes = mpf.plot(
        df, type='candle', volume=True, addplot=[ap_rsi, ap_rsi_ma, ap_ob, ap_os],
        style=style,
        figsize=(11, 7),
        panel_ratios=(3, 1, 1.5),
        returnfig=True,
        volume_panel=1,
        xrotation=0,
        tight_layout=True,
    )

    # 更新信息栏
    status_var.set(info_text + f"  |  RSI(14): {latest_rsi:.1f}")

    # 嵌入到 Tkinter
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    for w in chart_frame.winfo_children():
        w.destroy()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()

    toolbar = NavigationToolbar2Tk(canvas, chart_frame)
    toolbar.update()

    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
