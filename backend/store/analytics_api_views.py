"""Authenticated JSON feeds used by the dashboard and reports charts."""
from datetime import date, datetime, time, timedelta

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .admin_api import IsPlatformAdmin
from .models import Order, OrderItem


# A pending or cancelled order is not a completed sale. Flutterwave marks an
# order as ``processing`` once payment succeeds, so it is included here.
SALE_STATUSES = ('processing', 'shipped', 'delivered')


def _bounded_int(request, name, default, minimum, maximum):
    """Read a bounded integer query parameter without turning bad input into 500s."""
    try:
        value = int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _month_shift(value, amount):
    """Return the first day of the month ``amount`` months from ``value``."""
    month_index = (value.year * 12 + value.month - 1) + amount
    return date(month_index // 12, month_index % 12 + 1, 1)


def _bucket_date(value):
    return value.date() if hasattr(value, 'date') else value


def _sales_trend_payload(request, forced_range=None):
    """Build a zero-filled weekly or monthly sales series for a Chart.js line chart."""
    range_ = forced_range or (request.query_params.get('range') or 'weekly').lower()
    if range_ not in {'weekly', 'monthly'}:
        range_ = 'weekly'

    today = timezone.localdate()
    if range_ == 'monthly':
        months = _bounded_int(request, 'months', 12, 1, 36)
        current_month = today.replace(day=1)
        buckets = [_month_shift(current_month, offset) for offset in range(-(months - 1), 1)]
        start_date = buckets[0]
        truncate = TruncMonth('order_date')
        labels = [bucket.strftime('%b %Y') for bucket in buckets]
    else:
        weeks = _bounded_int(request, 'weeks', 8, 1, 52)
        current_week = today - timedelta(days=today.weekday())
        buckets = [current_week - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)]
        start_date = buckets[0]
        truncate = TruncWeek('order_date')
        labels = [bucket.strftime('%b %d') for bucket in buckets]

    start = timezone.make_aware(datetime.combine(start_date, time.min))
    rows = (
        Order.objects.filter(status__in=SALE_STATUSES, order_date__gte=start)
        .annotate(bucket=truncate)
        .values('bucket')
        .annotate(revenue=Sum('total_price'), orders=Count('id'))
        .order_by('bucket')
    )
    values_by_bucket = {_bucket_date(row['bucket']): row for row in rows}

    return {
        'range': range_,
        'labels': labels,
        'revenue': [float((values_by_bucket.get(bucket) or {}).get('revenue') or 0) for bucket in buckets],
        'orders': [int((values_by_bucket.get(bucket) or {}).get('orders') or 0) for bucket in buckets],
    }


def _top_products_payload(request, forced_metric=None):
    metric = forced_metric or (request.query_params.get('metric') or 'revenue').lower()
    if metric not in {'revenue', 'quantity'}:
        metric = 'revenue'

    days = _bounded_int(request, 'days', 30, 1, 730)
    limit = _bounded_int(request, 'limit', 10, 1, 50)
    start = timezone.now() - timedelta(days=days)

    items = (
        OrderItem.objects.filter(
            order__status__in=SALE_STATUSES,
            order__order_date__gte=start,
        )
        .values('product_id', 'product__name')
        # Define revenue first: otherwise Django resolves F('quantity') to the
        # same-call ``quantity`` aggregate rather than OrderItem.quantity.
        .annotate(revenue=Sum(F('price') * F('quantity')), quantity=Sum('quantity'))
        .order_by('-quantity' if metric == 'quantity' else '-revenue')[:limit]
    )

    return {
        'metric': metric,
        'days': days,
        'items': [
            {
                'product_id': row['product_id'],
                'name': row['product__name'] or 'Unknown product',
                'quantity': int(row['quantity'] or 0),
                'revenue': float(row['revenue'] or 0),
            }
            for row in items
        ],
    }


class SalesTrendView(APIView):
    permission_classes = [IsPlatformAdmin]
    def get(self, request):
        return Response(_sales_trend_payload(request))


class TopProductsView(APIView):
    permission_classes = [IsPlatformAdmin]
    def get(self, request):
        return Response(_top_products_payload(request))


class MonthlySalesView(APIView):
    permission_classes = [IsPlatformAdmin]
    def get(self, request):
        return Response(_sales_trend_payload(request, forced_range='monthly'))


class ProductPerformanceView(APIView):
    permission_classes = [IsPlatformAdmin]
    def get(self, request):
        return Response(_top_products_payload(request, forced_metric='revenue'))


class TotalRevenueView(APIView):
    """Total revenue KPIs with optional date-range filter."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Order.objects.filter(status__in=SALE_STATUSES)
        date_from = request.query_params.get('from')
        date_to   = request.query_params.get('to')
        category  = request.query_params.get('category')
        vendor_id = request.query_params.get('vendor')
        if date_from:
            try:
                qs = qs.filter(order_date__date__gte=date_from)
            except Exception:
                pass
        if date_to:
            try:
                qs = qs.filter(order_date__date__lte=date_to)
            except Exception:
                pass
        if category:
            qs = qs.filter(items__product__category__slug=category)
        if vendor_id:
            qs = qs.filter(items__product__vendor_id=vendor_id)
        agg = qs.aggregate(
            total=Sum('total_price'),
            count=Count('id', distinct=True),
        )
        return Response({
            'total_revenue': float(agg['total'] or 0),
            'order_count':   int(agg['count']  or 0),
        })


class RevenuePerUserView(APIView):
    """Top customers by total spending — bar chart data."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from django.contrib.auth.models import User
        limit = _bounded_int(request, 'limit', 10, 1, 50)
        rows = (
            Order.objects.filter(status__in=SALE_STATUSES, user__isnull=False)
            .values('user__id', 'user__username', 'user__email')
            .annotate(total=Sum('total_price'), orders=Count('id'))
            .order_by('-total')[:limit]
        )
        return Response([
            {
                'user_id':  row['user__id'],
                'username': row['user__username'] or 'Unknown',
                'email':    row['user__email']    or '',
                'total':    float(row['total']  or 0),
                'orders':   int(row['orders']   or 0),
            }
            for row in rows
        ])


class RevenuePerVendorView(APIView):
    """Vendor earnings and commission breakdown."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from .models import VendorOrder
        rows = (
            VendorOrder.objects
            .values('vendor__id', 'vendor__store_name', 'vendor__commission_rate')
            .annotate(gross=Sum('subtotal'), net=Sum('vendor_earnings'), orders=Count('id'))
            .order_by('-gross')
        )
        return Response([
            {
                'vendor_id':       row['vendor__id'],
                'store_name':      row['vendor__store_name'] or 'Unknown',
                'commission_rate': float(row['vendor__commission_rate'] or 0),
                'gross':           float(row['gross']   or 0),
                'net':             float(row['net']     or 0),
                'commission':      float((row['gross'] or 0) - (row['net'] or 0)),
                'orders':          int(row['orders']   or 0),
            }
            for row in rows
        ])
