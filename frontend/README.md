# AI sales assistant frontend

This TanStack Start frontend exercises the FastAPI backend. It loads the store name and currency from the public `/api/v1/config` endpoint and displays the configured product catalog.

For the Shopify Storefront API setup, deployment steps, and theme iframe snippet, follow the main repository's [Shopify developer guide](../README.md#use-it-in-a-shopify-store). The current frontend is a hosted demo app embedded in an iframe, not a native Shopify theme extension or floating widget.

## Run locally

Start the backend in a terminal from the project root:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Then, in another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000`. The default API address is `http://localhost:8000`. Set `VITE_API_BASE_URL` in `.env` to change it. If the frontend runs on another origin, include that origin in the backend's `CORS_ORIGINS`.

The interface includes chat and conversation history, product search and details, cart operations, assistant-led checkout, active orders and order history, payment-status refresh, order lookup and tracking, and a demo payment page with simulated success and failure. After creating an order, the assistant sends a link to `/payment/{reference}`. The customer can complete a simulated payment, return to chat, and click **I’ve paid — verify my order**; the assistant verifies the provider status, reports success, or resends the link after failure. The assistant collects contact and delivery details, shows the verified total, and waits for explicit confirmation before creating a pending-payment order. Payments and tracking are demo services.

The chat language selector supports English, Tamil, Malayalam, and Hindi. The selected language is remembered in the browser and sent with every chat request as a preference. Gemini also detects the language and writing style the customer actually uses, including mixed-language conversations and Manglish, Tanglish, and Hinglish typed in Latin letters, and mirrors the customer's transliteration/script where possible. The user message appears immediately while the response is loading; failed sends remain visible and can be retried. Gemini `**bold**` text is rendered as emphasis.

The frontend calls the `/chat` API. Set `LLM_PROVIDER=gemini` in the project-root `.env` and restart FastAPI to use the configured Gemini model. `LLM_PROVIDER=mock` selects deterministic offline replies. The default configuration uses demo data and a shared customer identity. SQL-backed storage and external product catalogs can be configured through the backend environment, but simulated payment links only are available; this is not production-ready for real customer records or payments.

## Build

```bash
npm run build
```

## Deploy to Vercel

Import the repository into Vercel and set the project **Root Directory** to
`frontend`. Keep the detected Nitro build configuration (build command
`npm run build`); do not configure the app as a static site or add an
`index.html` fallback. The Nitro Vite plugin generates the Vercel server
function and client assets for TanStack Start.
