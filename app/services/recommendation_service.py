"""Rank catalog matches against a shopper's preferences and budget."""

from __future__ import annotations

from app.repositories.factory import repository
from app.repositories.interfaces import BaseRepository

repo = repository


class RecommendationService:
    """Select and score products using only product data in the repository."""

    def __init__(self, repository: BaseRepository | None = None):
        self.repository = repository or repo

    def get_recommendations(self, *, query: str | None = None, budget: float | None = None,
                            skin_type: str | None = None, concern: str | None = None,
                            category: str | None = None, limit: int = 3) -> list[dict]:
        candidates = self.repository.search_products(
            query=query,
            category=category,
            skin_type=skin_type,
            concern=concern,
            max_price=budget,
            active_only=True,
        )

        def score(product: dict) -> tuple[int, float, float]:
            # Stable, explainable signals prioritize stated needs before popularity/price.
            text = f"{product['name']} {product['description']} {' '.join(product.get('benefits', []))} {' '.join(product.get('concerns', []))}".lower()
            score = 0
            if query:
                query_tokens = query.lower().split()
                score += sum(3 for token in query_tokens if token in text)
            if skin_type and skin_type.lower() in [item.lower() for item in product.get('skin_types', [])]:
                score += 10
            if concern and concern.lower() in [item.lower() for item in product.get('concerns', [])]:
                score += 10
            if budget:
                if product['price'] <= budget:
                    score += 5
            score += int(product.get('rating', 0) * 10)
            return (score, product['price'], -product['rating'])

        ordered = sorted(candidates, key=score, reverse=True)
        return ordered[:limit]
