# Open-Source AI Sales Chatbot for Shopify and Custom Stores

This project is a self-hostable FastAPI backend for an AI shopping assistant. It includes a Thai Naturals demo catalog, but store owners can connect a Shopify catalog, a custom REST catalog, or a SQL catalog and choose persistent SQL storage for chatbot data.

A separate TanStack Start frontend is available in [`frontend/`](./frontend/README.md) for exercising the API through a small shopping-assistant interface.

## Use it in a Shopify store

### What the current Shopify integration does

| Works now | Not included yet |
| --- | --- |
| Reads published Shopify products through the Storefront API | Shopify theme app extension or floating chat bubble |
| Displays products in the hosted assistant frontend | Add-to-cart in the Shopify storefront cart |
| Answers product questions with Gemini when configured | Shopify checkout/order creation, fulfillment, or webhooks |
| Can be embedded as a hosted assistant page in a Shopify theme | Merchant sign-in, per-customer identity, or production payment processing |

**Important:** this repository is a developer demo, not ready to handle live Shopify customers or orders. Its chat/order APIs do not authenticate visitors, the demo shares a customer identity, and checkout/payment links are simulated. Do not expose the demo checkout on a live store or collect real customer data. Use a Shopify development store while evaluating it.

### 1. Create Shopify Storefront API credentials

Create a Shopify custom app for your store and grant it Storefront API permission to read product listings. Generate a **Storefront API access token**; do not use an Admin API token. Publish the products you want the assistant to see to the relevant storefront/sales channel.

Keep the token on the backend. Never put it in frontend code, a `VITE_` variable, or a Shopify theme snippet.

### 2. Configure and run the backend

From the repository root, install the Python requirements and copy the environment template:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit the matching entries in `.env` (replace the demo defaults rather than adding duplicate keys):

```env
STORE_NAME=Your Store Name
CURRENCY=USD

CATALOG_PROVIDER=shopify
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_STOREFRONT_ACCESS_TOKEN=your_storefront_access_token
SHOPIFY_API_VERSION=2026-10
CATALOG_CACHE_SECONDS=60

LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_available_model_name

# Persistent app data; use PostgreSQL for a deployed instance.
STORAGE_BACKEND=sql
DATABASE_URL=sqlite:///./store.db

# Match the origin where the frontend is hosted.
CORS_ORIGINS=http://localhost:3000
```

Set `CURRENCY` to the Shopify product price currency (three-letter ISO code). For production, use a managed PostgreSQL URL for `DATABASE_URL`, put credentials in the hosting provider's secret manager, and set `CORS_ORIGINS` to the exact frontend origin. `CATALOG_CACHE_SECONDS` controls how often the backend refreshes products; `0` disables caching.

Start FastAPI:

```bash
uvicorn app.main:app --reload
```

Check that the server is using your store settings and that it can read products:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/config
curl http://127.0.0.1:8000/api/v1/products
```

The products endpoint should return your Shopify products, prices, images, and availability. Product inventory is unknown when Shopify does not report an exact quantity.

### 3. Run the assistant locally

In another terminal:

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Open `http://localhost:3000`. For local use, `VITE_API_BASE_URL` should point to `http://localhost:8000`. Try a product question and confirm the answer/cards match the Shopify catalog. Keep `.env` files and tokens out of source control.

### 4. Deploy and embed in your Shopify theme

1. Deploy the FastAPI app to a public HTTPS URL. Configure the backend environment variables above in the hosting provider; set `CORS_ORIGINS` to the frontend's origin.
2. Deploy the `frontend/` app to a host that supports the project's TanStack Start/Nitro build. Set `VITE_API_BASE_URL` to the deployed FastAPI base URL **at build time**, for example `https://api.example.com`. Build with `npm run build`.
3. In Shopify, open **Online Store → Themes → Customize**, add a **Custom liquid** section to a page/template, and paste the following. Replace the URL with the deployed frontend URL:

```liquid
<iframe
  src="https://assistant.example.com/"
  title="Chat with our shopping assistant"
  loading="lazy"
  style="display:block;width:100%;height:760px;border:0;border-radius:12px;"
></iframe>
```

4. Preview the page in your Shopify development store and test product discovery. This embeds the **whole hosted assistant app in an iframe**; it is not a native Shopify theme app extension or a small floating chat widget. The frontend host must permit your shop to frame it. If the browser blocks the iframe, configure that host's framing/security headers to allow your Shopify storefront domain. Backend CORS must allow the frontend origin, not the Shopify page origin, because the iframe makes the API requests.

The embed currently includes demo cart/order screens and simulated payments. Do not invite customers to check out through it; it does not add items to Shopify's cart or create Shopify orders. For a live store integration, implement a Shopify theme app extension or storefront widget, visitor/session isolation and API protections, Shopify cart/checkout handoff, and a real payment/order workflow first.

## Features

- Demo product catalog with 10 skincare products
- Configurable product catalog adapters for memory, Shopify Storefront API, REST/GraphQL APIs, and SQL queries
- Pluggable in-memory or persistent SQLite/PostgreSQL storage for conversations, carts, customers, and orders
- Product search and recommendation logic
- Conversational chat flow with history persistence
- Cart management and total calculation
- AI-guided checkout with customer contact and delivery details
- Explicit order confirmation before order creation
- Demo payment link generation
- Payment-status verification, active orders, order history, and tracking
- Swagger UI via FastAPI docs

## Project structure

- `app/main.py` – FastAPI app entry point
- `app/api/v1/` – API routes for chat, products, cart, orders, and demo payments
- `app/services/` – business logic for products, cart, orders, chat, and tracking
- `app/repositories/` – memory/SQL storage and Shopify, REST/GraphQL, and SQL product catalog adapters
- `app/ai/` – AI provider abstractions and tool registry
- `app/payments/` – payment-provider abstraction and demo provider
- `app/data/seed.py` – demo product and policy data
- `tests/` – smoke tests
- `frontend/` – TanStack Start demo UI for chat, catalog, cart, checkout, and order tracking

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Copy the environment template:

```bash
cp .env.example .env
```

4. To use real Gemini responses, set `LLM_PROVIDER=gemini`, add your Gemini API key, and set the model name supported by your account. Restart the backend after changing `.env`. Set `LLM_PROVIDER=mock` to use the deterministic offline provider instead.

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_available_model_name
```

With Gemini selected, chat requests use the Google Gen AI SDK and its tools to retrieve catalog details, recommend products, perform validated cart operations, and guide checkout. The assistant collects the customer's name, email, phone number, and delivery address; presents a backend-calculated order summary; then waits for explicit confirmation in a later message before creating an order and payment link. Payment status is read from the configured provider; the demo provider only supports simulated payments.

## Connect a store's data

The app is currently designed for **one self-hosted store per deployment**. Copy `.env.example` to `.env`, then select the product source with `CATALOG_PROVIDER`. Catalog records are normalized to the chatbot's product shape (`id`, `name`, `price`, and optional `stock_quantity`, `is_active`, description, category, benefits, ingredients, skin types, concerns, and image URL). If an integration does not provide a stock count, inventory is treated as unknown rather than fabricated; cart quantity checks then rely on the integration's availability flag.

Set `STORE_NAME`, `CURRENCY`, `DEFAULT_SHIPPING_FEE`, and `DEFAULT_FREE_SHIPPING_THRESHOLD` for your shop. `CURRENCY` must match the currency returned by Shopify or used by the connected catalog. Store policies can be supplied as a JSON object in `STORE_POLICIES_JSON`, for example `{"shipping":{"shipping_fee":5,"free_shipping_threshold":100},"returns":{"policy":"Returns within 14 days"},"support":{"email":"help@example.com"}}`. When using an external catalog without explicit policies, the assistant only receives the configured shipping fee and threshold; it will not be given the demo return/support policies.

### Persist chatbot data

Set `STORAGE_BACKEND=sql` and configure `DATABASE_URL` to persist conversations, carts, customers, and orders. SQLite and PostgreSQL are supported:

```env
STORAGE_BACKEND=sql
DATABASE_URL=sqlite:///./store.db
# Or: DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/store
```

The app creates its own tables and initializes the demo catalog/customer when those tables are empty. This database is for chatbot application data; choose a separate product catalog provider below to read the store's existing catalog.

### Shopify catalog

Create a Shopify custom app with Storefront API product-read access, then provide its Storefront access token and the shop's `*.myshopify.com` hostname:

```env
CATALOG_PROVIDER=shopify
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_STOREFRONT_ACCESS_TOKEN=your_storefront_access_token
SHOPIFY_API_VERSION=2026-10
```

The Shopify adapter reads product title, description, type, tags, image, price, and `availableForSale`, preserving fractional prices. Shopify's Storefront API does not provide exact inventory counts here, so the bot treats stock as unknown when a product is available. Set `CURRENCY` to match the Shopify price currency. It does not create Shopify carts or orders; checkout and payments remain the existing demo flow.

### Custom REST API catalog

The endpoint should return either an array of products or `{"products": [...]}` using the normalized product shape above. Fractional prices are preserved. An optional bearer token is sent in the `Authorization` header:

```env
CATALOG_PROVIDER=rest
CATALOG_API_URL=https://store.example/api/products
CATALOG_API_TOKEN=your_api_token
CATALOG_API_TYPE=rest
```

For GraphQL, set `CATALOG_API_TYPE=graphql` and provide `CATALOG_API_QUERY`. The query must return canonical product fields under a `products` field (either a list or a connection with `edges { node { ... } }`):

```env
CATALOG_API_TYPE=graphql
CATALOG_API_QUERY=query { products { id name price stock_quantity description category } }
```

### Existing SQL product catalog

Use a **read-only database account** and provide a `SELECT` whose result columns use the normalized product field names. Required columns are `id`, `name`, and `price`; optional columns include `stock_quantity`, `category`, `description`, `benefits`, `ingredients`, `skin_types`, `concerns`, `image_url`, and `is_active`. Array-valued fields should be returned as JSON arrays.

```env
CATALOG_PROVIDER=sql
CATALOG_DATABASE_URL=postgresql+psycopg://readonly:password@localhost:5432/store
CATALOG_SQL_QUERY=SELECT sku AS id, title AS name, unit_price AS price, inventory AS stock_quantity FROM products
```

Catalog results are cached for `CATALOG_CACHE_SECONDS` (default 60; set to `0` to disable). Keep API tokens and database URLs private in `.env` or your deployment's secret manager; do not commit secrets. The SQL catalog query is configuration supplied by the operator, and the database credentials should enforce read-only access.

5. Start the server:

```bash
uvicorn app.main:app --reload
```

6. Open the API docs at `http://127.0.0.1:8000/docs`.

## Run the frontend

Keep the FastAPI server running in one terminal. In another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000`. The frontend defaults to `http://localhost:8000` for the API. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend is running elsewhere. The backend's `CORS_ORIGINS` setting must include the frontend's origin when using another port or hostname.

The frontend provides chat-guided checkout, searchable product catalog and details, cart quantity controls, order payment links, a demo payment page with successful/failed outcomes, active orders and history, payment-status refresh, and order/tracking lookup. Customers can return to chat and use the payment-verification action to have the assistant check provider status. Payment and tracking are simulations; order/contact data uses in-memory storage and is cleared when the backend restarts. The current demo uses one shared customer identity and is not suitable for production or real payments.

## Example requests

List products:

```bash
curl http://127.0.0.1:8000/api/v1/products
```

Search products:

```bash
curl "http://127.0.0.1:8000/api/v1/products/search?q=oily&max_price=1000"
```

Start a chat:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hi! I have oily skin and acne marks."}'
```

Add item to cart:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/cart/conv_123/items \
  -H "Content-Type: application/json" \
  -d '{"product_id":"prod_001","quantity":1}'
```

Preview order:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/orders/preview \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"conv_123"}'
```

Create a confirmed order:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"conv_123","customer_name":"Demo Customer","email":"customer@example.com","phone":"+91 98765 43210","shipping_address":"12 Lotus Avenue, Bengaluru, Karnataka 560001","confirmed":true}'
```

List active orders and order history:

```bash
curl http://127.0.0.1:8000/api/v1/orders
```

Verify payment status with the configured provider:

```bash
curl http://127.0.0.1:8000/api/v1/orders/TN-12345678/payment-status
```

Check tracking:

```bash
curl http://127.0.0.1:8000/api/v1/orders/TN-12345678/tracking
```

## Tests

```bash
pytest -q
```

## Notes

- The default configuration uses in-memory storage and demo products for simple local testing.
- The demo provider does not collect real payments; use the order view's simulation control to test a successful payment.
- Customer identity is shared in this demo. Do not use this flow for real customer data until authentication, customer-scoped storage, and a real payment provider/webhook are configured.
- A deployment is for a single store; this project does not yet include a hosted multi-tenant merchant dashboard, Shopify checkout/order creation, authentication, or a production payment provider/webhook.
