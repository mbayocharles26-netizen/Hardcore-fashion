"""
AI-Powered Product Recommendations
====================================
Three-tier recommendation engine using real ML models.

Strategy 1 — SVD Matrix Factorization (collaborative filtering)
  Builds a user-product purchase matrix from OrderItem data, decomposes it
  with TruncatedSVD to learn latent product embeddings, then finds the most
  similar products to the target in that latent space.
  "Customers who bought this also bought…"

Strategy 2 — Semantic Content Similarity (sentence-transformers)
  Encodes product name + description into dense embeddings using a pre-trained
  transformer model, then finds the most semantically similar products via
  cosine similarity.
  "Similar items based on what this product is about…"

Strategy 3 — Trending (global fallback)
  Most-ordered active products site-wide. Always produces results even on a
  brand-new store with no purchase history.

Strategies are blended: SVD fills slots first, then semantic similarity fills
remaining slots, then trending fills any remainder.

Models are cached in-process after first build. Call invalidate_cache() after
bulk product/order changes (e.g. from a management command or signal).
"""

import logging
import threading
from collections import defaultdict

import numpy as np
from django.db.models import Count
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OrderItem, Product
from .serializers import ProductSerializer

logger = logging.getLogger(__name__)

RECOMMENDATION_LIMIT = 8

# ── In-process model cache ─────────────────────────────────────────────────────
_cache_lock = threading.Lock()
_svd_cache: dict = {}          # keys: 'matrix', 'product_ids', 'embeddings'
_semantic_cache: dict = {}     # keys: 'product_ids', 'embeddings'


def invalidate_cache():
    """Call this after bulk product or order changes."""
    with _cache_lock:
        _svd_cache.clear()
        _semantic_cache.clear()


# ── Strategy 1: SVD Matrix Factorization ──────────────────────────────────────

def _build_svd_model():
    """
    Build a user-product co-purchase matrix and decompose it with TruncatedSVD.
    Returns (product_ids, item_embeddings) where item_embeddings[i] is the
    latent vector for product_ids[i].
    """
    from scipy.sparse import csr_matrix
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    # Fetch all order items: (user_id, product_id)
    rows = list(
        OrderItem.objects
        .select_related('order')
        .values_list('order__user_id', 'product_id')
    )

    if len(rows) < 5:
        return None, None

    # Build index maps
    user_ids  = sorted({r[0] for r in rows if r[0] is not None})
    prod_ids  = sorted({r[1] for r in rows})

    if len(prod_ids) < 2:
        return None, None

    user_idx = {u: i for i, u in enumerate(user_ids)}
    prod_idx = {p: i for i, p in enumerate(prod_ids)}

    # Sparse user × product matrix (binary: bought or not)
    data, row_ind, col_ind = [], [], []
    for user_id, product_id in rows:
        if user_id is None:
            continue
        data.append(1)
        row_ind.append(user_idx[user_id])
        col_ind.append(prod_idx[product_id])

    if not data:
        return None, None

    matrix = csr_matrix(
        (data, (row_ind, col_ind)),
        shape=(len(user_ids), len(prod_ids)),
        dtype=np.float32,
    )

    # Number of components: min(50, rank - 1) to avoid over-decomposition
    n_components = min(50, min(matrix.shape) - 1)
    if n_components < 1:
        return None, None

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    # Decompose: item embeddings are the right singular vectors (VT transposed)
    svd.fit(matrix)
    item_embeddings = normalize(svd.components_.T)  # shape: (n_products, n_components)

    return prod_ids, item_embeddings


def _get_svd_cache():
    with _cache_lock:
        if _svd_cache:
            return _svd_cache.get('product_ids'), _svd_cache.get('embeddings')

    product_ids, embeddings = _build_svd_model()

    with _cache_lock:
        if product_ids is not None:
            _svd_cache['product_ids'] = product_ids
            _svd_cache['embeddings'] = embeddings

    return product_ids, embeddings


def _svd_similar(product_id: int, exclude_ids: list[int], limit: int) -> list[int]:
    """Return product IDs most similar to product_id in SVD latent space."""
    product_ids, embeddings = _get_svd_cache()

    if product_ids is None or product_id not in product_ids:
        return []

    idx = product_ids.index(product_id)
    target_vec = embeddings[idx]                          # (n_components,)
    scores = embeddings @ target_vec                      # cosine similarity for all products

    # Rank by score, exclude target and already-selected
    exclude_set = set(exclude_ids) | {product_id}
    ranked = sorted(
        [(product_ids[i], float(scores[i])) for i in range(len(product_ids))
         if product_ids[i] not in exclude_set],
        key=lambda x: x[1],
        reverse=True,
    )
    return [pid for pid, _ in ranked[:limit]]


# ── Strategy 2: Semantic Content Similarity ───────────────────────────────────

def _build_semantic_model():
    """
    Encode all active product (name + description) into sentence embeddings.
    Returns (product_ids, embeddings).
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning('sentence-transformers not installed — semantic strategy disabled.')
        return None, None

    products = list(
        Product.objects
        .filter(is_active=True)
        .values_list('id', 'name', 'description')
    )

    if len(products) < 2:
        return None, None

    prod_ids = [p[0] for p in products]
    texts    = [f"{p[1]}. {p[2]}" for p in products]

    # all-MiniLM-L6-v2: fast, lightweight, 384-dim embeddings — good for CPU
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    return prod_ids, embeddings


def _get_semantic_cache():
    with _cache_lock:
        if _semantic_cache:
            return _semantic_cache.get('product_ids'), _semantic_cache.get('embeddings')

    product_ids, embeddings = _build_semantic_model()

    with _cache_lock:
        if product_ids is not None:
            _semantic_cache['product_ids'] = product_ids
            _semantic_cache['embeddings'] = embeddings

    return product_ids, embeddings


def _semantic_similar(product_id: int, exclude_ids: list[int], limit: int) -> list[int]:
    """Return product IDs most semantically similar to product_id."""
    product_ids, embeddings = _get_semantic_cache()

    if product_ids is None or product_id not in product_ids:
        return []

    idx = product_ids.index(product_id)
    target_vec = embeddings[idx]
    scores = embeddings @ target_vec                      # cosine similarity

    exclude_set = set(exclude_ids) | {product_id}
    ranked = sorted(
        [(product_ids[i], float(scores[i])) for i in range(len(product_ids))
         if product_ids[i] not in exclude_set],
        key=lambda x: x[1],
        reverse=True,
    )
    return [pid for pid, _ in ranked[:limit]]


# ── Strategy 3: Trending fallback ─────────────────────────────────────────────

def _trending(exclude_ids: list[int], limit: int) -> list[int]:
    """Most-ordered active products site-wide."""
    return list(
        Product.objects
        .filter(is_active=True)
        .exclude(id__in=exclude_ids)
        .annotate(order_count=Count('orderitem'))
        .order_by('-order_count', '-created_at')
        .values_list('id', flat=True)[:limit]
    )


# ── Blended recommendation entry point ────────────────────────────────────────

def get_recommendations(product_id: int, limit: int = RECOMMENDATION_LIMIT) -> list:
    """
    Blend all three strategies and return an ordered list of Product objects.
    """
    try:
        Product.objects.get(id=product_id, is_active=True)
    except Product.DoesNotExist:
        return []

    selected: list[int] = []

    # Strategy 1 — SVD collaborative filtering
    try:
        svd_ids = _svd_similar(product_id, selected, limit)
        selected += svd_ids
    except Exception:
        logger.exception('SVD recommendation failed — falling through to semantic.')

    # Strategy 2 — Semantic content similarity (fill remaining slots)
    remaining = limit - len(selected)
    if remaining > 0:
        try:
            sem_ids = _semantic_similar(product_id, selected, remaining)
            selected += sem_ids
        except Exception:
            logger.exception('Semantic recommendation failed — falling through to trending.')

    # Strategy 3 — Trending (fill any remaining slots)
    remaining = limit - len(selected)
    if remaining > 0:
        selected += _trending([product_id] + selected, remaining)

    if not selected:
        return []

    # Preserve ranking order via a CASE expression
    from django.db.models import Case, IntegerField, When
    ordering = Case(
        *[When(id=pid, then=pos) for pos, pid in enumerate(selected)],
        output_field=IntegerField(),
    )
    return list(
        Product.objects
        .filter(id__in=selected, is_active=True)
        .select_related('category')
        .order_by(ordering)
    )


# ── REST API View ──────────────────────────────────────────────────────────────

class ProductRecommendationsView(APIView):
    """
    GET /api/products/<product_id>/recommendations/
    GET /api/products/<product_id>/recommendations/?limit=4
    Public — no authentication required.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        limit = min(int(request.query_params.get('limit', RECOMMENDATION_LIMIT)), 20)
        products = get_recommendations(product_id, limit)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)
