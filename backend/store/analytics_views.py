from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncDay
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.contrib.admin.views.decorators import staff_member_required

from .models import Order, OrderItem, ProductView


@require_POST
@staff_member_required
def product_view_track(request):
    # Staff-protected endpoint for now (to avoid anonymous spam while we implement session/anon tracking).
    # Payload: {"product_id": 123}
    try:
        import json

        body = json.loads(request.body.decode("utf-8") or "{}")
        product_id = body.get("product_id")
    except Exception:
        product_id = None

    if not product_id:
        return JsonResponse({"error": "product_id required"}, status=400)

    # user may be absent if auth cookie missing; still allow tracking.
    ProductView.objects.create(user=getattr(request, "user", None), product_id=product_id)
    return JsonResponse({"ok": True})


@require_GET
@staff_member_required
def analytics_dashboard_kpis(request):
    # Optional query param: days (default 30)
    days = int(request.GET.get("days", 30))
    end = timezone.now()
    start = end - timedelta(days=days)

    base_orders = Order.objects.filter(order_date__gte=start, order_date__lte=end)

    revenue_total = base_orders.aggregate(total=Sum("total_price")).get("total") or 0

    # Orders per day
    orders_by_day = (
        base_orders.annotate(day=TruncDay("order_date"))
        .values("day")
        .annotate(total=Sum("total_price"), orders=Sum("id"))
        .order_by("day")
    )

    # Top products by revenue
    top_items_qs = (
        OrderItem.objects.filter(order__order_date__gte=start, order__order_date__lte=end)
        .values("product_id", "product__name")
        .annotate(quantity=Sum("quantity"), revenue=Sum("price") * Sum("quantity"))
        .order_by("-revenue")[:5]
    )

    # Product views per day
    pv_qs = (
        ProductView.objects.filter(viewed_at__gte=start, viewed_at__lte=end)
        .annotate(day=TruncDay("viewed_at"))
        .values("day")
        .annotate(views=Sum("id"))
        .order_by("day")
    )

    return JsonResponse(
        {
            "days": days,
            "revenue_total": float(revenue_total),
            "orders_by_day": [
                {"day": o["day"].isoformat(), "total": float(o["total"] or 0), "orders": int(o["orders"] or 0)}
                for o in orders_by_day
            ],
            "top_products": [
                {"product_id": r["product_id"], "name": r["product__name"], "quantity": int(r["quantity"] or 0)}
                for r in top_items_qs
            ],
            "product_views_by_day": [
                {"day": o["day"].isoformat(), "views": int(o["views"] or 0)}
                for o in pv_qs
            ],
        },
        safe=False,
    )

