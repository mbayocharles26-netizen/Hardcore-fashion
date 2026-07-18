"""
Vendor Dashboard API
All endpoints require the authenticated user to have an approved Vendor profile.
Vendors only ever see their own products, orders, and payouts.
"""
import csv
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Category, Order, OrderItem, Product, Shipment,
    VendorNotification, VendorOrder, VendorPayout, Vendor,
)
from .throttles import VendorRateThrottle


def push_vendor_notification(notification: VendorNotification):
    """Push a saved VendorNotification to the vendor's live WebSocket group."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'vendor_{notification.vendor_id}',
        {
            'type': 'vendor_notification',
            'payload': {
                'id':         notification.id,
                'type':       notification.type,
                'title':      notification.title,
                'body':       notification.body,
                'link':       notification.link,
                'is_read':    notification.is_read,
                'created_at': notification.created_at.isoformat(),
            },
        },
    )


# ── Permission ─────────────────────────────────────────────────────────────────

class IsApprovedVendor(permissions.BasePermission):
    message = 'You must be an approved vendor to access this resource.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        vendor = getattr(request.user, 'vendor_profile', None)
        return vendor is not None and vendor.status == 'approved'


def _vendor(request):
    return request.user.vendor_profile


class VendorThrottleAPIView(APIView):
    throttle_classes = [VendorRateThrottle]


class VendorAccountStatusView(APIView):
    """Return the signed-in user's vendor application status.

    This endpoint does not grant access to any vendor resources. It allows the
    client to distinguish a pending or rejected vendor application from a
    regular customer account before choosing where to send the user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        vendor = getattr(request.user, 'vendor_profile', None)
        return Response({
            'is_vendor': vendor is not None,
            'status': vendor.status if vendor else None,
        })


# ── Serializers ────────────────────────────────────────────────────────────────

class VendorProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'compare_at_price',
            'stock', 'image', 'category', 'category_name',
            'is_featured', 'is_active', 'shipping_days', 'created_at',
        ]
        read_only_fields = ['created_at']


class VendorOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price']


class VendorOrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    customer_name  = serializers.CharField(source='order.customer_name',  read_only=True)
    customer_email = serializers.CharField(source='order.customer_email', read_only=True)
    order_date     = serializers.DateTimeField(source='order.order_date',  read_only=True)

    class Meta:
        model = VendorOrder
        fields = [
            'id', 'order', 'status', 'subtotal',
            'customer_name', 'customer_email', 'order_date', 'items',
        ]

    def get_items(self, obj):
        vendor = obj.vendor
        items = obj.order.items.filter(product__vendor=vendor).select_related('product')
        return VendorOrderItemSerializer(items, many=True).data


class VendorPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorPayout
        fields = ['id', 'amount', 'method', 'status', 'reference', 'requested_at', 'processed_at', 'notes']
        read_only_fields = ['status', 'reference', 'requested_at', 'processed_at']


class VendorNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorNotification
        fields = ['id', 'type', 'title', 'body', 'is_read', 'link', 'created_at']


# ── Dashboard ──────────────────────────────────────────────────────────────────

class VendorDashboardView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def get(self, request):
        vendor = _vendor(request)
        now = timezone.now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        vendor_orders = VendorOrder.objects.filter(vendor=vendor)
        month_orders  = vendor_orders.filter(order__order_date__gte=start)

        revenue_total = vendor_orders.aggregate(t=Sum('subtotal'))['t'] or Decimal('0')
        revenue_month = month_orders.aggregate(t=Sum('subtotal'))['t'] or Decimal('0')

        top_products = (
            OrderItem.objects
            .filter(product__vendor=vendor)
            .values('product__name')
            .annotate(qty=Sum('quantity'), rev=Sum(F('price') * F('quantity')))
            .order_by('-qty')[:5]
        )

        monthly_trend = (
            vendor_orders
            .annotate(month=TruncMonth('order__order_date'))
            .values('month')
            .annotate(revenue=Sum('subtotal'), orders=Count('id'))
            .order_by('month')
        )

        unread_notifications = VendorNotification.objects.filter(vendor=vendor, is_read=False).count()

        return Response({
            'store_name': vendor.store_name,
            'metrics': {
                'revenue_total':   float(revenue_total),
                'revenue_month':   float(revenue_month),
                'orders_total':    vendor_orders.count(),
                'orders_pending':  vendor_orders.filter(status='pending').count(),
                'products_active': Product.objects.filter(vendor=vendor, is_active=True).count(),
                'low_stock':       Product.objects.filter(vendor=vendor, stock__lte=5).count(),
                'unread_notifications': unread_notifications,
            },
            'top_products': [
                {'name': r['product__name'], 'quantity': r['qty'], 'revenue': float(r['rev'] or 0)}
                for r in top_products
            ],
            'monthly_trend': [
                {'label': r['month'].strftime('%b %Y'), 'orders': r['orders'], 'revenue': float(r['revenue'] or 0)}
                for r in monthly_trend
            ],
        })


# ── Products ───────────────────────────────────────────────────────────────────

class VendorProductListCreateView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        qs = Product.objects.filter(vendor=_vendor(request)).select_related('category')
        return Response(VendorProductSerializer(qs, many=True).data)

    def post(self, request):
        serializer = VendorProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=_vendor(request))
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VendorProductDetailView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]

    def _get_product(self, request, product_id):
        return Product.objects.filter(id=product_id, vendor=_vendor(request)).first()

    def patch(self, request, product_id):
        product = self._get_product(request, product_id)
        if not product:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = VendorProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, product_id):
        product = self._get_product(request, product_id)
        if not product:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorProductBulkImportView(VendorThrottleAPIView):
    """CSV bulk import: name, slug, category_slug, price, stock, description"""
    permission_classes = [IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'file': 'CSV file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        vendor = _vendor(request)
        rows = csv.DictReader(upload.read().decode('utf-8-sig').splitlines())
        count = 0
        for row in rows:
            category = Category.objects.filter(slug=row.get('category', '')).first()
            if not category:
                continue
            Product.objects.update_or_create(
                slug=row['slug'],
                defaults={
                    'vendor':      vendor,
                    'name':        row.get('name', ''),
                    'category':    category,
                    'description': row.get('description', ''),
                    'price':       row.get('price') or 0,
                    'stock':       row.get('stock') or 0,
                    'is_active':   str(row.get('is_active', 'true')).lower() in {'true', '1', 'yes'},
                },
            )
            count += 1
        return Response({'imported': count})


# ── Orders ─────────────────────────────────────────────────────────────────────

class VendorOrderListView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def get(self, request):
        qs = (
            VendorOrder.objects
            .filter(vendor=_vendor(request))
            .select_related('order')
            .order_by('-order__order_date')
        )
        return Response(VendorOrderSerializer(qs, many=True).data)


class VendorOrderStatusView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def patch(self, request, vendor_order_id):
        vo = VendorOrder.objects.filter(id=vendor_order_id, vendor=_vendor(request)).first()
        if not vo:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        new_status = request.data.get('status')
        valid = {s[0] for s in VendorOrder.STATUS_CHOICES}
        if new_status not in valid:
            return Response({'status': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        vo.status = new_status
        vo.save(update_fields=['status'])
        # Push real-time notification to vendor
        notif = VendorNotification.objects.create(
            vendor=vo.vendor,
            type=VendorNotification.TYPE_NEW_ORDER,
            title=f'Order #{vo.order_id} updated to {new_status}',
            body=f'Sub-order #{vo.id} status changed to {new_status}.',
            link=f'/vendor/orders/',
        )
        push_vendor_notification(notif)
        return Response(VendorOrderSerializer(vo).data)


class VendorPaymentConfirmView(VendorThrottleAPIView):
    """Vendor confirms or rejects payment for a pending order.
    On confirm: order moves to 'processing', a Shipment with tracking code is created.
    On reject:  order moves to 'cancelled'.
    """
    permission_classes = [IsApprovedVendor]

    def patch(self, request, vendor_order_id):
        vo = VendorOrder.objects.filter(id=vendor_order_id, vendor=_vendor(request)).select_related('order').first()
        if not vo:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action not in ('confirm', 'reject'):
            return Response({'detail': 'action must be confirm or reject.'}, status=status.HTTP_400_BAD_REQUEST)

        order = vo.order
        tracking_number = None

        if action == 'confirm':
            order.status = 'processing'
            vo.status = 'processing'
            # Create shipment with tracking code if not already present
            shipment, _ = Shipment.objects.get_or_create(
                order=order,
                defaults={'status': Shipment.STATUS_PENDING},
            )
            tracking_number = shipment.tracking_number
        else:
            order.status = 'cancelled'
            vo.status = 'cancelled'

        order.save(update_fields=['status'])
        vo.save(update_fields=['status'])

        # Notify vendor
        notif_title = f'Payment {"confirmed" if action == "confirm" else "rejected"} for Order #{order.id}'
        notif = VendorNotification.objects.create(
            vendor=vo.vendor,
            type=VendorNotification.TYPE_PAYMENT,
            title=notif_title,
            body=f'Tracking: {tracking_number}' if tracking_number else '',
            link='/vendor/orders/',
        )
        push_vendor_notification(notif)

        return Response({
            'order_id': order.id,
            'order_status': order.status,
            'tracking_number': tracking_number,
        })


class VendorInvoiceView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def get(self, request, vendor_order_id):
        vo = VendorOrder.objects.filter(id=vendor_order_id, vendor=_vendor(request)).select_related('order').first()
        if not vo:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        vendor = _vendor(request)
        items = vo.order.items.filter(product__vendor=vendor).select_related('product')
        lines = [
            f'Invoice — Sub-Order #{vo.id}',
            f'Store: {vendor.store_name}',
            f'Customer: {vo.order.customer_name} <{vo.order.customer_email}>',
            f'Status: {vo.status}',
            '',
            'Items:',
        ]
        for item in items:
            lines.append(f'  {item.product.name}: {item.quantity} x £{item.price}')
        lines += ['', f'Subtotal: £{vo.subtotal}']
        response = HttpResponse('\n'.join(lines), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename=vendor-invoice-{vo.id}.txt'
        return response


# ── Payouts ────────────────────────────────────────────────────────────────────

class VendorPayoutListCreateView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def get(self, request):
        qs = VendorPayout.objects.filter(vendor=_vendor(request)).order_by('-requested_at')
        return Response(VendorPayoutSerializer(qs, many=True).data)

    def post(self, request):
        serializer = VendorPayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(vendor=_vendor(request), status='requested')
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Notifications ──────────────────────────────────────────────────────────────

class VendorNotificationListView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def get(self, request):
        qs = VendorNotification.objects.filter(vendor=_vendor(request)).order_by('-created_at')[:50]
        return Response(VendorNotificationSerializer(qs, many=True).data)


class VendorNotificationMarkReadView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def patch(self, request, notification_id):
        n = VendorNotification.objects.filter(id=notification_id, vendor=_vendor(request)).first()
        if not n:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        n.is_read = True
        n.save(update_fields=['is_read'])
        return Response({'status': 'ok'})


class VendorNotificationMarkAllReadView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def post(self, request):
        VendorNotification.objects.filter(vendor=_vendor(request), is_read=False).update(is_read=True)
        return Response({'status': 'ok'})


class VendorNotificationClearView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def delete(self, request):
        VendorNotification.objects.filter(vendor=_vendor(request)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorEarningsSummaryView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]

    def get(self, request):
        vendor = _vendor(request)
        payouts = VendorPayout.objects.filter(vendor=vendor)
        total_earned = VendorOrder.objects.filter(vendor=vendor).aggregate(
            t=Sum('vendor_earnings'))['t'] or Decimal('0')
        paid_out = payouts.filter(status='completed').aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        pending = payouts.filter(status__in=['requested', 'processing']).aggregate(
            t=Sum('amount'))['t'] or Decimal('0')
        return Response({
            'total_earned': float(total_earned),
            'paid_out':     float(paid_out),
            'pending':      float(pending),
        })


# ── Profile ────────────────────────────────────────────────────────────────────

class VendorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            'id', 'store_name', 'description', 'email', 'phone',
            'address', 'logo', 'commission_rate', 'payout_method',
            'payout_details', 'status', 'created_at',
        ]
        read_only_fields = ['commission_rate', 'status', 'created_at']


class VendorProfileView(VendorThrottleAPIView):
    permission_classes = [IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        return Response(VendorProfileSerializer(_vendor(request)).data)

    def patch(self, request):
        serializer = VendorProfileSerializer(_vendor(request), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class VendorAvatarView(VendorThrottleAPIView):
    """Dedicated endpoint for vendor profile picture (separate from store logo)."""
    permission_classes = [IsApprovedVendor]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        vendor = _vendor(request)
        avatar = request.FILES.get('avatar')
        if not avatar:
            return Response({'avatar': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        # Reuse the logo field as the vendor's profile picture
        if vendor.logo:
            vendor.logo.delete(save=False)
        vendor.logo = avatar
        vendor.save(update_fields=['logo'])
        return Response({'avatar_url': request.build_absolute_uri(vendor.logo.url)})

    def delete(self, request):
        vendor = _vendor(request)
        if vendor.logo:
            vendor.logo.delete(save=False)
            vendor.logo = None
            vendor.save(update_fields=['logo'])
        return Response(status=status.HTTP_204_NO_CONTENT)
