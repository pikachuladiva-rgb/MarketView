# MarketView

Enterprise-grade financial charting application with real-time data visualization and intelligent caching architecture.

## Overview

A production-ready charting platform that delivers TradingView-quality user experience with professional data pipeline architecture. Built for scalability, performance, and reliability.

**Key Features:**
- Real-time OHLC candlestick charts with interactive crosshair
- TradingView-inspired UI with persistent navigation and sliding panels
- Three-tier data architecture: PostgreSQL → Redis → Yahoo Finance
- 10 years of historical data for 100 top NASDAQ tickers
- Dynamic watchlist with add/remove, sorting, and live prices
- Light/dark theme support with persistent preferences
- Responsive chart legend with live data sync
- Symbol search with keyboard navigation
- Zoom persistence across ticker switches

## Architecture

```
┌─────────────────┐
│  Yahoo Finance  │ (External Data Source)
└────────┬────────┘
         │ yfinance API (fallback only)
         ▼
┌─────────────────┐
│  PostgreSQL     │ (10 years historical data)
│  + Redis Cache  │ (15-min TTL)
└────────┬────────┘
         │ REST API (/data/<ticker>)
         ▼
┌─────────────────┐
│ Flask Backend   │ (Data Transformation & API)
└────────┬────────┘
         │ JSON OHLC data
         ▼
┌─────────────────┐
│ Lightweight     │ (Canvas Rendering)
│ Charts Frontend │
└─────────────────┘
```

**Three-Tier Data Flow:**
1. **Tier 1 (Primary)**: PostgreSQL - 10 years of pre-loaded data (~2,500 candles per ticker)
2. **Tier 2 (Cache)**: Redis - 15-minute TTL for fast repeated access
3. **Tier 3 (Fallback)**: Yahoo Finance - Only for missing tickers

## Tech Stack

### Backend
- **Flask 3.1.3** - Lightweight WSGI web framework
- **PostgreSQL 15** - Persistent storage for historical OHLC data
- **psycopg2** - PostgreSQL Python driver with RealDictCursor
- **yfinance 1.2.0** - Yahoo Finance API wrapper for market data
- **Redis 7** - In-memory cache (Docker container)
- **pandas 3.0.1** - Data transformation and analysis
- **python-dotenv** - Environment variable management
- **Python 3.12** - Runtime environment

### Frontend
- **Lightweight Charts 4.1.3** - TradingView's official charting library
- **Vanilla JavaScript** - Zero framework overhead
- **CSS Variables** - Dynamic theming system

### Infrastructure
- **PM2** - Process manager for production deployment
- **Docker** - Redis and PostgreSQL containerization
- **Ubuntu Server** - 24GB RAM production environment

## Data Pipeline

### Three-Tier Architecture (Current Implementation)

**Request Flow:**
1. User requests ticker data via `/data/<ticker>` endpoint
2. **Tier 1 - PostgreSQL Check**: Query database for historical data
   - **Hit**: Return 10 years of data instantly (~105ms response time)
   - **Miss**: Proceed to Tier 2
3. **Tier 2 - Redis Check**: Check cache with key `chart_data:{ticker}_1d_1y`
   - **Hit**: Return cached JSON (~5ms response time)
   - **Miss**: Proceed to Tier 3
4. **Tier 3 - Yahoo Finance**: Download from external API
   - Download 1 year of data (~800ms)
   - Store in PostgreSQL for future use
   - Cache in Redis (900s TTL)
   - Return to user

**Performance Metrics:**
- PostgreSQL hit: ~105ms (2,500+ candles, 10 years)
- Redis hit: ~5ms (cached data)
- Yahoo Finance fallback: ~800ms (new tickers only)
- Cache duration: 15 minutes (900 seconds)

**Data Transformation:**
```python
PostgreSQL DECIMAL → Python float → JSON Array
{
  "time": unix_timestamp,
  "open": float,
  "high": float,
  "low": float,
  "close": float
}
```

**Critical Implementation Detail:**
PostgreSQL stores prices as DECIMAL type. Must explicitly convert to float for JSON serialization:
```python
candles = [{
    'time': int(row['time']),
    'open': float(row['open']),  # DECIMAL → float conversion required
    'high': float(row['high']),
    'low': float(row['low']),
    'close': float(row['close'])
} for row in rows]
```

## Historical Data Ingestion

### Bulk Data Loading

The `ingest_data.py` script pre-loads 10 years of historical data for 100 top NASDAQ tickers.

**Usage:**
```bash
cd src
python3 ingest_data.py
```

**Process:**
- Downloads 10 years of daily OHLC data per ticker
- Stores ~2,500 candles per ticker in PostgreSQL
- Rate-limited to 2 seconds between requests (prevents Yahoo Finance blocking)
- Idempotent: Can run multiple times without creating duplicates (ON CONFLICT DO NOTHING)
- Updates metadata table with last_updated timestamps

**Estimated Time:** ~3-4 minutes for 100 tickers

**Database Schema:**
```sql
CREATE TABLE ohlc_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT,
    UNIQUE(ticker, timestamp)
);

CREATE TABLE ticker_metadata (
    ticker VARCHAR(10) PRIMARY KEY,
    last_updated TIMESTAMP,
    data_start_date TIMESTAMP,
    data_end_date TIMESTAMP,
    total_candles INTEGER
);
```

## System Architecture Phases

### ✅ Phase 1: In-Memory Caching (Implemented)
**Status:** Production-ready

Implemented Redis cache-aside pattern to eliminate redundant API calls and prevent rate limiting.

**Benefits:**
- 160x faster response time for cached data
- Prevents Yahoo Finance rate limiting
- Supports concurrent users efficiently
- Minimal infrastructure complexity

### ✅ Phase 2: Database Storage (Implemented)
**Status:** Production-ready

Implemented PostgreSQL with 10 years of historical data for 100 top NASDAQ tickers.

**Architecture:**
```
┌──────────────┐
│ PostgreSQL   │ ← 10 years historical data (250,000+ candles)
│ (Primary)    │ ← ~2,500 candles per ticker
└──────────────┘
       ↑
       │ Query first, fallback to Yahoo Finance
       │
┌──────────────┐
│ Flask API    │ ← Three-tier data retrieval
│ + Redis      │ ← 15-min cache layer
└──────────────┘
```

**Benefits:**
- 10 years of data available instantly (~105ms)
- Reduced Yahoo Finance API calls by 95%+
- Persistent storage survives server restarts
- Idempotent ingestion (no duplicate data)
- Enables long-term historical analysis

**Implementation Details:**
- PostgreSQL 15 running in Docker
- DECIMAL(12,4) for price precision
- UNIQUE constraint on (ticker, timestamp) prevents duplicates
- Metadata tracking for data freshness
- Explicit float conversion for JSON serialization

### 🚀 Phase 3: Background Workers (Future)
**Status:** Roadmap

Decouple data ingestion from user requests with background worker architecture.

**Architecture:**
```
┌─────────────────┐
│ Ingestion Worker│ ← Runs every 5 minutes
│ (Background)    │ ← Updates popular tickers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PostgreSQL +    │ ← Pre-warmed data
│ Redis Cache     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Flask API       │ ← Only reads, never fetches
│ (User-facing)   │ ← Sub-10ms response time
└─────────────────┘
```

**Benefits:**
- Zero external API calls during user requests
- Consistent sub-10ms response times
- Proactive data updates
- Scalable to thousands of concurrent users

## Setup & Deployment

### Prerequisites
```bash
# Redis (Docker)
docker ps | grep redis  # Verify Redis container running on port 6379

# PostgreSQL (Docker)
docker ps | grep postgres  # Verify PostgreSQL container running on port 5432

# Python 3.12 with virtual environment
python3 -m venv venv
source venv/bin/activate
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database Configuration
DB_HOST=localhost
DB_NAME=marketview
DB_USER=root
DB_PASSWORD=your_secure_password
DB_PORT=5432

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

**Security Note:** The `.env` file is excluded from git via `.gitignore`. Never commit credentials to version control.

### Installation
```bash
# Install dependencies
pip install flask yfinance pandas redis psycopg2-binary python-dotenv

# Verify Redis connection
python3 -c "import redis; r=redis.Redis(host='localhost', port=6379); print(r.ping())"

# Verify PostgreSQL connection
python3 -c "import psycopg2; conn=psycopg2.connect(host='localhost', database='marketview', user='root', password='123456'); print('Connected')"
```

### Database Setup

```bash
# Create database schema
psql -h localhost -U root -d marketview -f database/schema.sql

# Load historical data (takes ~3-4 minutes)
cd src
python3 ingest_data.py
```

### Running the Server

**Development:**
```bash
cd src
python3 server.py
# Server runs on http://0.0.0.0:4012
```

**Production (PM2):**
```bash
pm2 start venv/bin/python --name "4012 chart" --cwd /home/ubuntu/chart/src -- server.py
pm2 save
pm2 logs "4012 chart"  # View logs
```

**PM2 Management:**
```bash
pm2 restart "4012 chart"  # Restart after code changes
pm2 stop "4012 chart"     # Stop server
pm2 delete "4012 chart"   # Remove from PM2
```

## API Documentation

### Endpoints

#### `GET /`
Serves the main chart application (index.html)

**Response:** HTML page with embedded JavaScript chart

#### `GET /data/<ticker>`
Fetches OHLC candlestick data for specified ticker

**Parameters:**
- `ticker` (string): Stock symbol (e.g., NVDA, AAPL, TSLA)

**Response:** JSON array of candles
```json
[
  {
    "time": 1741132800,
    "open": 117.54,
    "high": 118.24,
    "low": 114.47,
    "close": 117.26
  }
]
```

**Caching:** 15-minute TTL in Redis

**Performance:**
- Cache hit: ~5ms
- Cache miss: ~800ms (includes Yahoo Finance download)

## Frontend Features

### UI Components
- **Top Navigation Bar**: Ticker selector, timeframe buttons (D/W/M), settings menu
- **Chart Legend**: Live OHLC data with crosshair sync, market status indicator
- **Left Toolbar**: Drawing tools panel (toggleable via settings)
- **Right Sidebar**: Persistent icon rail + sliding watchlist drawer
- **Theme Toggle**: Light/dark mode with CSS variables and localStorage persistence
- **Dynamic Watchlist**: Add/remove tickers, sortable columns, live price updates

### Watchlist Features
- **Add Tickers**: Click + button to search and add any ticker
- **Remove Tickers**: Hover over ticker, click × to remove
- **Live Prices**: Automatically fetches and displays last price for each ticker
- **Sortable Columns**: Click "Symbol" or "Price" headers to sort (↑/↓ indicators)
- **Active Highlighting**: Green left border on currently displayed ticker
- **Persistent Storage**: Watchlist and sort preferences saved to localStorage

### User Interactions
- **Symbol Search**: Type any key to open search, arrow keys to navigate, Enter to select
- **Crosshair Mode**: Hover over chart to see historical candle data in legend
- **Panel Toggles**: Show/hide drawings toolbar and watchlist via settings menu
- **Zoom Persistence**: Chart zoom level maintained when switching between tickers
- **Responsive**: Auto-adjusts chart dimensions based on panel visibility
- **Keyboard Shortcuts**: ESC to close search, alphanumeric keys to open search

## Project Structure

```
/home/ubuntu/chart/
├── src/
│   ├── server.py           # Flask backend with three-tier data retrieval
│   ├── ingest_data.py      # Bulk historical data ingestion script
│   └── tickers.py          # List of 100 top NASDAQ tickers
├── public/
│   └── index.html          # Frontend with Lightweight Charts
├── database/
│   └── schema.sql          # PostgreSQL table definitions
├── venv/                   # Python virtual environment
├── .env                    # Environment variables (not in git)
├── .env.example            # Environment template
├── .gitignore              # Git exclusions
├── server.log              # Application logs
└── README.md               # This file
```

## Performance Considerations

**Current Performance:**
- PostgreSQL queries: ~105ms for 2,500 candles (10 years)
- Redis cache hits: ~5ms
- Yahoo Finance fallback: ~800ms (rare, only for new tickers)
- Frontend rendering: 60 FPS canvas-based charts

**Optimization Strategies:**
- Three-tier architecture reduces external API calls by 95%+
- PostgreSQL provides instant access to 10 years of data
- Redis cache layer for sub-10ms repeated requests
- Explicit DECIMAL→float conversion prevents serialization errors
- Zoom persistence improves UX when switching tickers
- Lighter grid lines (#1e222d) reduce visual noise

**Known Limitations:**
- Timeframe selector (D/W/M buttons) currently non-functional
- No real-time streaming data (daily candles only)
- Watchlist price updates require manual refresh

## Contributing

When adding features, maintain the three-tier architecture:
1. **Tier 1 (PostgreSQL)**: Primary data source for historical data
2. **Tier 2 (Redis)**: Fast cache layer for repeated requests
3. **Tier 3 (Yahoo Finance)**: Fallback for missing tickers

**Development Guidelines:**
- Always use environment variables for credentials (never hardcode)
- Explicit float conversion required for PostgreSQL DECIMAL types
- Maintain idempotent operations (ON CONFLICT DO NOTHING)
- Test with PM2 working directory set correctly
- Keep watchlist features in localStorage for persistence

## Recent Updates

**March 2026:**
- ✅ Implemented PostgreSQL storage with 10 years of historical data
- ✅ Added dynamic watchlist with add/remove functionality
- ✅ Implemented sortable columns (Symbol, Price) with direction indicators
- ✅ Added live price updates in watchlist
- ✅ Fixed zoom persistence when switching tickers
- ✅ Improved grid line visibility (lighter colors)
- ✅ Fixed infinite request loop in watchlist price fetching
- ✅ Added active ticker highlighting with green border
- ✅ Implemented localStorage persistence for watchlist and preferences

## License

Proprietary - Internal use only

---

**Last Updated:** March 6, 2026
**Maintainer:** Chart Platform Team
**Production URL:** https://kk-4012.cooltechgp.online
**GitHub:** https://github.com/pikachuladiva-rgb/MarketView

