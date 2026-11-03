"""HTTP endpoints for listing, filtering, and retrieving catalog products."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import AppError
from app.services.product_service import ProductService
from app.repositories.factory import repository as repo

router = APIRouter()
service = ProductService(repo)

# Catalog HTTP handlers keep query parsing separate from search behavior.
@router.get("/products")
def list_products(category: str | None = None, skin_type: str | None = None,
                  concern: str | None = None, max_price: float | None = Query(default=None, ge=0),
                  available_only: bool = True):
    try:
        products = service.search_products(category=category, skin_type=skin_type, concern=concern, max_price=max_price)
        if available_only:
            products = [
                product for product in products
                if product.get("is_active", True)
                and (product.get("stock_quantity") is None or product.get("stock_quantity", 0) > 0)
            ]
        return {"products": products}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.get("/products/search")
def search_products(
    q: str | None = None,
    category: str | None = None,
    skin_type: str | None = None,
    concern: str | None = None,
    max_price: float | None = Query(default=None, ge=0),
):
    try:
        products = service.search_products(query=q, category=category, skin_type=skin_type, concern=concern, max_price=max_price)
        return {"products": products}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.get("/products/{product_id}")
def get_product(product_id: str):
    try:
        return {"product": service.get_product(product_id)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc
