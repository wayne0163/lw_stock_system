import sqlite3
import pandas as pd
from pathlib import Path

def get_stock_financials(ts_code):
    db_path = Path('database/financial_data.db')
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    with sqlite3.connect(db_path) as conn:
        # Get column names
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(financial_indicators)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Available columns: {columns}")

        # Fetch last 5 periods for the given stock
        query = f"""
            SELECT * FROM financial_indicators 
            WHERE ts_code = ? 
            ORDER BY period DESC 
            LIMIT 5
        """
        df = pd.read_sql_query(query, conn, params=(ts_code,))
        
        if df.empty:
            print(f"No data found for {ts_code}")
        else:
            print(f"\nFinancial data for {ts_code}:")
            # Select relevant columns if they exist
            # Common Tushare mapping:
            # tr: Total Revenue
            # n_income: Net Income
            # grossprofit_margin: Gross Profit Margin
            # netprofit_margin: Net Profit Margin
            # roe_dt: ROE (deducted)
            # n_cashflow_act: Net cash flow from operating activities
            # debt_to_assets: Debt to Asset ratio
            # rd_exp: R&D expenses
            
            interesting_cols = ['ts_code', 'period', 'roe_dt', 'tr', 'n_income', 'grossprofit_margin', 
                                'netprofit_margin', 'debt_to_assets', 'n_cashflow_act', 'rd_exp']
            
            existing_interesting = [c for c in interesting_cols if c in df.columns]
            print(df[existing_interesting].to_string())

if __name__ == "__main__":
    get_stock_financials('301389.SZ')
