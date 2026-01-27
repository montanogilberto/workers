# SmartLoans Workers - Azure Functions Project

## 📋 Project Overview

SmartLoans Workers is an Azure Functions-based project that automates data collection from MercadoLibre and Amazon, processes exchange rates, and manages publish jobs. The workers run on scheduled timers and store data in Azure SQL Database.

### Key Features
- **MercadoLibre Listings Extraction**: Fetches product listings based on keywords, categories, and seller IDs
- **Amazon Listings Extraction**: Fetches product listings from Amazon (placeholder for API integration)
- **Exchange Rates**: Daily fetch of MXN→USD exchange rates from Frankfurter API
- **Publish Jobs**: Processes pending jobs for publishing to external platforms

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Functions (Python)                      │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ publish_jobs_timer│  │ ml_competitor   │  │ amazon_listings│ │
│  │    (every 30s)    │  │   _timer (5m)   │  │   _timer (15m) │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                    │          │
│           └─────────────────────┼────────────────────┘          │
│                                 ▼                               │
│                    ┌─────────────────────────┐                  │
│                    │   Shared Utilities      │                  │
│                    │  - ml_api.py            │                  │
│                    │  - db.py                │                  │
│                    │  - retry.py             │                  │
│                    │  - fx.py                │                  │
│                    │  - selllistings_mapper  │                  │
│                    └─────────────────────────┘                  │
│                                 │                               │
│                                 ▼                               │
│                    ┌─────────────────────────┐                  │
│                    │    Azure SQL Database   │                  │
│                    │    (smartloans DB)      │                  │
│                    └─────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
smartloans_workers/
├── .gitignore
├── .vscode/
│   ├── extensions.json
│   └── settings.json
├── README.md
├── PROJECT_DOCUMENTATION.md          # This file
├── requirements.txt
├── host.json                         # Azure Functions host config
├── local.settings.json               # Local dev settings
├── production.settings.json          # Production settings template
├── function_app.py                   # Main function entry point
├── deploy_to_production.sh           # Automated deployment script
├── PROD_TESTING_PLAN.md              # Testing strategy
├── PROD_TESTING_IMPLEMENTATION.md    # Implementation guide
├── TODO.md                           # Development tasks
│
├── amazonListingsWorker/
│   └── __init__.py                   # Amazon listings worker
│
├── exchangeRatesWorker/
│   └── __init__.py                   # Exchange rates worker
│
├── mlSellListingsWorker/
│   └── __init__.py                   # MercadoLibre listings worker
│
├── publishJobsWorker/
│   └── __init__.py                   # Publish jobs worker
│
└── shared/
    ├── db.py                         # Azure SQL database utilities
    ├── fx.py                         # Exchange rate utilities
    ├── ml_api.py                     # MercadoLibre API client
    ├── notes.txt                     # Development notes
    ├── retry.py                      # Retry logic utilities
    └── selllistings_mapper.py        # Data mapping utilities
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FUNCTIONS_WORKER_RUNTIME` | Azure Functions runtime | `python` | ✅ |
| `AzureWebJobsStorage` | Azure Storage connection string | - | ✅ |
| `AZURE_SQL_CONNECTION_STRING` | Azure SQL DB connection | - | ✅ |
| `SMARTLOANS_BACKEND_URL` | Backend API base URL | `https://api.mercadolibre.com` | ✅ |
| `ML_SITE_ID` | MercadoLibre site ID | `MLM` | ✅ |
| `ML_MARKET` | Marketplace code | `MX` | ✅ |
| `ML_KEYWORDS` | Search keywords (comma-separated) | `iphone,ps5,airpods` | ✅ |
| `ML_CATEGORIES` | ML categories (comma-separated) | `` | ❌ |
| `ML_SELLER_IDS` | Seller IDs (comma-separated) | `` | ❌ |
| `ML_LIMIT` | Results per page | `50` | ❌ |
| `ML_MAX_PAGES` | Maximum pages to fetch | `10` | ❌ |
| `ML_TIMEOUT_SECONDS` | API timeout | `25` | ❌ |
| `ML_CALL_ITEMS_DETAIL` | Fetch item details (1=true) | `1` | ❌ |
| `ML_CODE_VERIFIER` | OAuth code verifier | - | ❌ |
| `ML_CLIENT_ID` | OAuth client ID | - | ❌ |
| `ML_CLIENT_SECRET` | OAuth client secret | - | ❌ |
| `ML_REDIRECT_URI` | OAuth redirect URI | - | ❌ |
| `ML_ACCESS_TOKEN` | OAuth access token | - | ❌ |
| `ML_REFRESH_TOKEN` | OAuth refresh token | - | ❌ |
| `WEBSITE_RUN_FROM_PACKAGE` | Run from package | `1` | ❌ |

### Timer Schedules

| Function | Schedule (UTC) | Description |
|----------|---------------|-------------|
| `publish_jobs_timer` | `*/30 * * * * *` | Every 30 seconds |
| `ml_competitor_timer` | `0 */5 * * * *` | Every 5 minutes |
| `amazon_listings_timer` | `0 */15 * * * *` | Every 15 minutes |
| `exchange_rates_timer` | `0 5 16 * * *` | Daily at 16:05 UTC (09:05 Hermosillo) |

---

## 🐍 Workers Details

### 1. MercadoLibre Listings Worker (`mlSellListingsWorker`)

**Purpose**: Fetches product listings from MercadoLibre and stores them in the database.

**Configuration**:
- `ML_KEYWORDS`: Comma-separated search terms (e.g., "iphone,ps5,airpods")
- `ML_CATEGORIES`: ML category IDs to search
- `ML_SELLER_IDS`: Specific seller IDs to monitor
- `ML_LIMIT`: Results per page (default: 50)
- `ML_MAX_PAGES`: Maximum pages per search (default: 10)

**API Endpoints**:
- Search: `https://api.mercadolibre.com/sites/{site_id}/search`
- Item Details: `https://api.mercadolibre.com/items/{item_id}`

**Flow**:
```
Timer → Fetch Search Results → Get Item Details → Map to Schema → Upsert to DB
```

**Database Stored Procedure**: `sp_sellListings`

---

### 2. Amazon Listings Worker (`amazonListingsWorker`)

**Purpose**: Fetches product listings from Amazon (placeholder for future API integration).

**Configuration**:
- `AMAZON_KEYWORDS`: Comma-separated search terms
- `AMAZON_MARKETPLACE`: Marketplace code (default: MX)
- `AMAZON_API_BASE`: Amazon API base URL
- `AMAZON_API_KEY`: Amazon API authentication key

**Status**: Currently a no-op placeholder. Actual Amazon API integration needed.

---

### 3. Exchange Rates Worker (`exchangeRatesWorker`)

**Purpose**: Fetches MXN→USD exchange rate from Frankfurter API and stores in database.

**Schedule**: Daily at 16:05 UTC (09:05 Hermosillo time)

**API**: `https://api.frankfurter.app/latest?from=MXN&to=USD`

**Database Stored Procedure**: `sp_fxRates`

---

### 4. Publish Jobs Worker (`publishJobsWorker`)

**Purpose**: Processes pending jobs that need to be published to external platforms.

**Schedule**: Every 30 seconds

**Database Stored Procedure**: `sp_publishJobs`

---

## 🗄️ Database

### Azure SQL Database
- **Server**: `sql.bsite.net\MSSQL2016`
- **Database**: `montanogilberto_smartloans`
- **Authentication**: SQL (uid/password)

### Tables & Stored Procedures

| Name | Type | Purpose |
|------|------|---------|
| `sellListings` | Table | Stores product listings from ML/Amazon |
| `fxRates` | Table | Stores exchange rates |
| `publishJobs` | Table | Stores pending publish jobs |
| `sp_sellListings` | SP | Upsert sell listings from JSON payload |
| `sp_fxRates` | SP | Upsert exchange rates |
| `sp_publishJobs` | SP | Process publish jobs |

### Database Connection

```python
# Connection string format
Driver={ODBC Driver 18 for SQL Server};
Server=sql.bsite.net\MSSQL2016;
Database=montanogilberto_smartloans;
Uid=montanogilberto_smartloans;
Pwd=Admin#1914;
Encrypt=yes;
TrustServerCertificate=yes;
Connection Timeout=30;
```

---

## 🔄 Retry Logic

The `shared/retry.py` module provides intelligent retry behavior:

| Status Code | Retry Behavior |
|-------------|----------------|
| 403 (Forbidden) | Fail fast after 2 retries (~7s max) |
| 429 (Too Many Requests) | Exponential backoff |
| 5xx (Server Errors) | Exponential backoff |
| Other errors | Default exponential backoff |

**Backoff Formula**: `delay = min(initial_delay * (2^attempt), max_delay)`

---

## 🚀 Deployment

### Prerequisites
1. Azure CLI installed (`brew install azure-cli`)
2. Azure Functions Core Tools (`npm i -g azure-functions-core-tools@4`)
3. Active Azure subscription

### Deployment Methods

#### Method 1: Using Deployment Script
```bash
./deploy_to_production.sh smartloans-workers-func rg-smartloans-workers
```

#### Method 2: Manual Deployment
```bash
# Using Azure Functions Core Tools
func azure functionapp publish smartloans-workers-func --publish-local-settings

# Or using ZIP deployment
zip -r deploy.zip . -x "*.git*" "*__pycache__*" "*.pyc" "local.settings.json"
az functionapp deployment source config-zip \
  --resource-group rg-smartloans-workers \
  --name smartloans-workers-func \
  --src deploy.zip
```

### Azure Resources

| Resource | Type | Description |
|----------|------|-------------|
| `smartloans-workers-func` | Function App | Azure Functions hosting |
| `rg-smartloans-workers` | Resource Group | Resource container |
| `smartloans-workers-funcstorage` | Storage Account | Function app storage |

---

## 📊 Monitoring

### View Logs
```bash
# Real-time logs
az functionapp logstream --name smartloans-workers-func --resource-group rg-smartloans-workers
```

### Check Status
```bash
# Function app status
az functionapp show --name smartloans-workers-func --resource-group rg-smartloans-workers

# List functions
az functionapp function list --name smartloans-workers-func --resource-group rg-smartloans-workers

# Restart function app
az functionapp restart --name smartloans-workers-func --resource-group rg-smartloans-workers
```

### Azure Portal
```
https://portal.azure.com/#@/resource/subscriptions/{subscription-id}/resourceGroups/rg-smartloans-workers/providers/Microsoft.Web/sites/smartloans-workers-func
```

---

## 🛠️ Development

### Local Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run locally
func start
```

### Test Workers Locally
```bash
# Test ML worker
python -m mlSellListingsWorker

# Test Amazon worker
python -m amazonListingsWorker

# Test exchange rates
python -m exchangeRatesWorker
```

### Code Structure
- All timer triggers defined in `function_app.py`
- Worker logic in respective `*/__init__.py` files
- Shared utilities in `shared/` directory

---

## 🔒 Security

### Current Security Status
- ❌ Credentials stored in environment variables (acceptable for Azure Functions)
- ⚠️ Sensitive values visible in `local.settings.json` (gitignored)
- ⚠️ ML API credentials hardcoded in Azure settings

### Recommendations
1. Use Azure Key Vault for sensitive credentials
2. Implement proper OAuth token refresh logic
3. Enable Azure AD authentication for function app
4. Use Managed Identity for database access

---

## 📝 API Reference

### MercadoLibre API

#### Search Items
```
GET https://api.mercadolibre.com/sites/{site_id}/search
Parameters:
  - q: Search query
  - category: Category ID
  - seller_id: Seller ID
  - offset: Pagination offset
  - limit: Results per page (max 50)
```

#### Get Item Details
```
GET https://api.mercadolibre.com/items/{item_id}
```

#### Response Mapping
| ML Field | Database Field |
|----------|----------------|
| `id` | `channelItemId` |
| `title` | `title` |
| `price` | `sellPriceOriginal` |
| `currency_id` | `currencyOriginal` |
| `condition` | `itemCondition` |
| `thumbnail` | `imageUrl` |
| `permalink` | `itemUrl` |

---

## 🐛 Troubleshooting

### Common Issues

#### "Unable to load some functions"
**Cause**: Mixed function definition types (v1 function.json + v2 decorators)

**Solution**: Remove all `function.json` files from worker directories

#### Functions Not Triggering
1. Check timer syntax in Azure Portal
2. Verify function is enabled
3. Check application settings

#### Database Connection Failed
1. Verify connection string in Application Settings
2. Check firewall rules allow Azure IP ranges
3. Confirm credentials are valid

#### 403 Errors from ML API
1. Token expired - refresh OAuth token
2. IP blocked - contact ML support
3. Rate limited - implement backoff

---

## 📈 Performance

### Current Metrics
- **ML Worker**: ~50 items per search, up to 10 pages = 500 items max per keyword
- **Database**: Connection timeout 30s, retry up to 3 times
- **API Timeout**: 25 seconds per request

### Optimization Opportunities
1. Implement pagination with parallel requests
2. Add caching for exchange rates
3. Use batch inserts for database operations
4. Implement circuit breaker for API calls

---

## 🔮 Future Improvements

1. **Amazon API Integration**: Complete the Amazon listings worker with real API
2. **Authentication**: Implement OAuth token refresh automation
3. **Monitoring**: Add Application Insights integration
4. **CI/CD**: Create GitHub Actions workflow for automated deployment
5. **Testing**: Add unit tests and integration tests
6. **Security**: Move credentials to Azure Key Vault
7. **Scalability**: Consider Durable Functions for long-running operations

---

## 📄 License

This project is proprietary software owned by SmartLoans.

---

## 👥 Contributors

- **ria Montano** - Primary Developer

---

## 📞 Support

For issues or questions:
1. Check Azure Function App logs in Azure Portal
2. Review Application Settings configuration
3. Verify database connectivity and permissions
4. Check ML API status and rate limits

---

**Last Updated**: January 2026  
**Version**: 1.0.0

