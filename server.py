from flask import Flask, jsonify
import yfinance as yf
import pandas as pd
import redis
import json

app = Flask(__name__)
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@app.route('/')
def index():
    return open('index.html').read()

@app.route('/data/<ticker>')
def get_data(ticker):
    cache_key = f'chart_data:{ticker}_1d_1y'

    # Check cache first
    cached = redis_client.get(cache_key)
    if cached:
        return jsonify(json.loads(cached))

    # Cache miss - download from Yahoo Finance
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

    # Save to cache with 15-minute TTL
    redis_client.setex(cache_key, 900, json.dumps(candles))

    return jsonify(candles)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4012)
