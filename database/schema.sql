-- MarketView Database Schema
-- Phase 2: Historical Data Storage

CREATE TABLE IF NOT EXISTS ohlc_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, timestamp)
);

CREATE INDEX idx_ticker_timestamp ON ohlc_data(ticker, timestamp DESC);
CREATE INDEX idx_ticker ON ohlc_data(ticker);

-- Metadata table to track ingestion status
CREATE TABLE IF NOT EXISTS ticker_metadata (
    ticker VARCHAR(10) PRIMARY KEY,
    last_updated TIMESTAMP,
    data_start_date TIMESTAMP,
    data_end_date TIMESTAMP,
    total_candles INTEGER DEFAULT 0
);
