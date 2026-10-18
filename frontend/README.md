# Thai Naturals demo frontend

This separate TanStack Start frontend exercises the Thai Naturals FastAPI backend.

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

The interface includes chat and conversation history, product search and details, cart operations, assistant-led checkout, active orders and order history, payment-status refresh, order lookup and tracking, and a demo payment page with simulated success and failure. After creating an order, the assistant sends a link to `/payment/{reference}`. The customer can complete a simulated payment, return to chat, and click **I’ve paid — verify my order**; the assistant verifies the provider status, reports success, or resends the link after failure. The assistant collects contact and delivery details, shows the verified total, and waits for explicit confirmation before creating a pending-payment order. Product and order data uses in-memory demo storage; payments and tracking are not real services.

The chat language selector supports English, Tamil, Malayalam, and Hindi. The selected language is remembered in the browser and sent with every chat request as a preference. Gemini also detects the language and writing style the customer actually uses, including mixed-language conversations and Manglish, Tanglish, and Hinglish typed in Latin letters, and mirrors the customer's transliteration/script where possible. The user message appears immediately while the response is loading; failed sends remain visible and can be retried. Gemini `**bold**` text is rendered as emphasis.

The frontend calls the `/chat` API. Set `LLM_PROVIDER=gemini` in the project-root `.env` and restart FastAPI to use the configured Gemini model. `LLM_PROVIDER=mock` selects deterministic offline replies. This demo uses a shared customer identity and simulated payment links only; it is not production-ready for real customer records or payments.

## Build

```bash
npm run build
```
