from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import redis
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__, static_folder='../public', static_url_path='')
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=int(os.getenv('REDIS_DB', 0)),
    decode_responses=True
)

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

@app.route('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')).read()

@app.route('/data/<ticker>')
def get_data(ticker):
    timeframe = request.args.get('timeframe', '1d')
    cache_key = f'chart_data:{ticker}_{timeframe}'

    # Tier 1: Check PostgreSQL
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if timeframe == '1d':
            cursor.execute("""
                SELECT timestamp as time, open, high, low, close, volume
                FROM ohlc_data
                WHERE ticker = %s
                ORDER BY timestamp ASC
            """, (ticker.upper(),))
        elif timeframe == '1w':
            cursor.execute("""
                SELECT
                    EXTRACT(EPOCH FROM date_trunc('week', to_timestamp(timestamp)))::bigint as time,
                    (array_agg(open ORDER BY timestamp ASC))[1] as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    (array_agg(close ORDER BY timestamp DESC))[1] as close,
                    SUM(volume) as volume
                FROM ohlc_data
                WHERE ticker = %s
                GROUP BY date_trunc('week', to_timestamp(timestamp))
                ORDER BY time ASC
            """, (ticker.upper(),))
        elif timeframe == '1mo':
            cursor.execute("""
                SELECT
                    EXTRACT(EPOCH FROM date_trunc('month', to_timestamp(timestamp)))::bigint as time,
                    (array_agg(open ORDER BY timestamp ASC))[1] as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    (array_agg(close ORDER BY timestamp DESC))[1] as close,
                    SUM(volume) as volume
                FROM ohlc_data
                WHERE ticker = %s
                GROUP BY date_trunc('month', to_timestamp(timestamp))
                ORDER BY time ASC
            """, (ticker.upper(),))

        rows = cursor.fetchall()
        conn.close()

        if rows:
            candles = [{
                'time': int(row['time']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']) if row['volume'] else 0
            } for row in rows]
            print(f"PostgreSQL: Returning {len(candles)} {timeframe} candles for {ticker}")
            redis_client.setex(cache_key, 900, json.dumps(candles))
            return jsonify(candles)
        else:
            print(f"PostgreSQL: No data found for {ticker}")
    except Exception as e:
        print(f"PostgreSQL error: {e}")

    # Tier 2: Check Redis cache
    cached = redis_client.get(cache_key)
    if cached:
        return jsonify(json.loads(cached))

    # Tier 3: Download from Yahoo Finance
    df = yf.download(ticker, period='1y', interval='1d', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    candles = []
    for idx, row in df.iterrows():
        candles.append({
            'time': int(idx.timestamp()),
            'open': float(row.Open),
            'high': float(row.High),
            'low': float(row.Low),
            'close': float(row.Close)
        })

    # Store in PostgreSQL for future use
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for candle in candles:
            cursor.execute("""
                INSERT INTO ohlc_data (ticker, timestamp, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, timestamp) DO NOTHING
            """, (
                ticker.upper(),
                candle['time'],
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                0
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"PostgreSQL insert error: {e}")

    # Cache in Redis
    redis_client.setex(cache_key, 900, json.dumps(candles))

    return jsonify(candles)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4012)
