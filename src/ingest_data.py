#!/usr/bin/env python3
"""
MarketView Data Ingestion Script
Downloads 10 years of historical data for top NASDAQ tickers
"""
import psycopg2
import yfinance as yf
import pandas as pd
import time
from datetime import datetime
from tickers import TOP_TICKERS
from dotenv import load_dotenv
import os

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# PostgreSQL connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'marketview'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 5432))
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def ingest_ticker(ticker, conn):
    """Download and store 10 years of data for a ticker"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Downloading {ticker}...")

    try:
        df = yf.download(ticker, period='10y', interval='1d', progress=False)

        if df.empty:
            print(f"  ⚠️  No data for {ticker}")
            return 0

        # Handle MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)

        cursor = conn.cursor()
        inserted = 0

        for idx, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO ohlc_data (ticker, timestamp, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, timestamp) DO NOTHING
                """, (
                    ticker,
                    int(idx.timestamp()),
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume']) if 'Volume' in row else 0
                ))
                inserted += 1
            except Exception as e:
                print(f"  ⚠️  Error inserting row: {e}")
                continue

        conn.commit()

        # Update metadata
        cursor.execute("""
            INSERT INTO ticker_metadata (ticker, last_updated, data_start_date, data_end_date, total_candles)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET
                last_updated = EXCLUDED.last_updated,
                data_end_date = EXCLUDED.data_end_date,
                total_candles = EXCLUDED.total_candles
        """, (
            ticker,
            datetime.now(),
            df.index[0].to_pydatetime(),
            df.index[-1].to_pydatetime(),
            inserted
        ))
        conn.commit()

        print(f"  ✓ {ticker}: {inserted} candles stored")
        return inserted

    except Exception as e:
        print(f"  ✗ {ticker} failed: {e}")
        conn.rollback()
        return 0

def main():
    """Main ingestion loop"""
    conn = get_db_connection()
    print(f"Starting ingestion of {len(TOP_TICKERS)} tickers...")
    print(f"Estimated time: {len(TOP_TICKERS) * 2 / 60:.1f} minutes\n")

    total_candles = 0
    success_count = 0

    for i, ticker in enumerate(TOP_TICKERS, 1):
        candles = ingest_ticker(ticker, conn)
        if candles > 0:
            success_count += 1
            total_candles += candles

        # Rate limiting: 2 seconds between requests
        if i < len(TOP_TICKERS):
            time.sleep(2)

        # Progress update every 10 tickers
        if i % 10 == 0:
            print(f"\n--- Progress: {i}/{len(TOP_TICKERS)} ({i/len(TOP_TICKERS)*100:.1f}%) ---\n")

    conn.close()
    print(f"\n✓ Ingestion complete!")
    print(f"  Success: {success_count}/{len(TOP_TICKERS)} tickers")
    print(f"  Total candles: {total_candles:,}")

if __name__ == '__main__':
    main()
