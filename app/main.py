from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import cart, chat, config, orders, payments, products
from app.core.config import settings
from app.core.exceptions import AppError

app = FastAPI(title=settings.app_name, version="1.0.0", debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_exception_handler(_, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message, "error_code": exc.error_code},
    )


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}


app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(config.router, prefix=settings.api_prefix)
app.include_router(products.router, prefix=settings.api_prefix)
app.include_router(cart.router, prefix=settings.api_prefix)
app.include_router(orders.router, prefix=settings.api_prefix)
app.include_router(payments.router, prefix=settings.api_prefix)
