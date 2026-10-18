# Thai Naturals AI Shopping Assistant

This project is a FastAPI-based backend for a Thai Naturals skincare shopping assistant. It uses an in-memory repository for demo data, a modular service layer, and a provider-based AI architecture that can switch between Gemini and a mock provider.

A separate TanStack Start frontend is available in [`frontend/`](./frontend/README.md) for exercising the API through a small shopping-assistant interface.

The current `/chat` service is a deterministic demo conversation flow and does not yet call Gemini; configuring a Gemini key alone will not make chat replies model-generated.

## Features

- Product catalog with 10 demo skincare products
- Product search and recommendation logic
- Conversational chat flow with history persistence
- Cart management and total calculation
- Order preview and confirmation flow
- Demo payment link generation
- Order status and tracking responses
- Swagger UI via FastAPI docs

## Project structure

- `app/main.py` – FastAPI app entry point
- `app/api/v1/` – API routes for chat, products, cart, orders, and demo payments
- `app/services/` – business logic for products, cart, orders, chat, and tracking
- `app/repositories/` – in-memory repository implementation
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

With Gemini selected, chat requests use the Google Gen AI SDK and its tool calls to retrieve catalog details, recommend products, and perform validated cart operations. Checkout remains a separate confirmed API flow; the model cannot create orders or mark demo payments as paid.

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

The frontend provides the chat and conversation-history flow, searchable product catalog and details, cart quantity controls, order preview and confirmation, payment-link display, demo-payment simulation, and order/tracking lookup. All payment and tracking actions are simulations; the backend's in-memory data is lost when it restarts.

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
  -d '{"conversation_id":"conv_123","confirmed":true}'
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

- This project intentionally uses an in-memory repository to keep setup simple and demo-friendly.
- Payment and order tracking are clearly labeled as demo/simulation flows.
- The architecture is designed to be replaceable with a real persistent database, real payment provider, or LLM adapter.
