import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminProfile, Category, Order, OrderItem, Product, Vendor, VendorOrder, VendorPayout


SALE_STATUSES = ('processing', 'shipped', 'delivered')


def _is_admin(user):
    profile = getattr(user, 'admin_profile', None)
    return bool(user and user.is_authenticated and profile and profile.is_active)


class IsPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_admin(request.user)


class IsSuperAdmin(IsPlatformAdmin):
    """Restrict destructive platform-level workflows to super administrators."""

    def has_permission(self, request, view):
        profile = getattr(request.user, 'admin_profile', None)
        return bool(
            super().has_permission(request, view)
            and profile.role == AdminProfile.ROLE_SUPER_ADMIN
        )


class ProductAdminSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'stock', 'image',
            'image_url', 'is_featured', 'is_active', 'category', 'category_name',
            'shipping_days', 'created_at', 'updated_at',
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return ''
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class CategoryAdminSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'product_count']


class OrderAdminSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer_name', 'customer_email', 'customer_phone',
            'customer_address', 'status', 'total_price',
            'flutterwave_transaction_id', 'order_date', 'item_count',
        ]


class CustomerAdminSerializer(serializers.ModelSerializer):
    order_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    admin_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'is_active', 'date_joined',
            'order_count', 'total_spent', 'admin_role',
        ]

    def get_admin_role(self, obj):
        profile = getattr(obj, 'admin_profile', None)
        return profile.role if profile and profile.is_active else ''


class PendingVendorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    product_count = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = ['id', 'store_name', 'email', 'phone', 'username', 'status', 'created_at', 'updated_at', 'product_count', 'total_revenue']

    def get_product_count(self, obj):
        return obj.products.count()

    def get_total_revenue(self, obj):
        result = VendorOrder.objects.filter(vendor=obj).aggregate(t=Sum('subtotal'))['t']
        return float(result or 0)


class AdminDashboardView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        start = now - timedelta(days=30)
        orders = Order.objects.filter(order_date__gte=start, status__in=SALE_STATUSES)
        revenue = orders.aggregate(total=Sum('total_price')).get('total') or Decimal('0')

        top_products = (
            OrderItem.objects.filter(order__status__in=SALE_STATUSES).values('product__name')
            .annotate(revenue=Sum(F('price') * F('quantity')), quantity=Sum('quantity'))
            .order_by('-quantity')[:5]
        )
        trends = (
            orders.annotate(day=TruncDay('order_date'))
            .values('day')
            .annotate(revenue=Sum('total_price'), orders=Count('id'))
            .order_by('day')
        )

        return Response({
            'metrics': {
                'revenue': float(revenue),
                'orders': Order.objects.count(),
                'pending_orders': Order.objects.filter(status='pending').count(),
                'customers': User.objects.count(),
                'low_stock': Product.objects.filter(stock__lte=5).count(),
                'active_products': Product.objects.filter(is_active=True).count(),
            },
            'top_products': [
                {
                    'name': row['product__name'] or 'Unknown',
                    'quantity': int(row['quantity'] or 0),
                    'revenue': float(row['revenue'] or 0),
                }
                for row in top_products
            ],
            'trends': [
                {
                    'label': row['day'].strftime('%b %d'),
                    'orders': int(row['orders'] or 0),
                    'revenue': float(row['revenue'] or 0),
                }
                for row in trends
            ],
        })


class AdminProductListCreateView(APIView):
    permission_classes = [IsPlatformAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        qs = Product.objects.select_related('category').all()
        serializer = ProductAdminSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductAdminSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(APIView):
    permission_classes = [IsPlatformAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        serializer = ProductAdminSerializer(product, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCategoryListCreateView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Category.objects.annotate(product_count=Count('products'))
        return Response(CategoryAdminSerializer(qs, many=True).data)

    def post(self, request):
        serializer = CategoryAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminOrderListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Order.objects.annotate(item_count=Count('items')).order_by('-order_date')
        return Response(OrderAdminSerializer(qs, many=True).data)


class AdminOrderStatusView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        status_value = request.data.get('status')
        valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
        if status_value not in valid_statuses:
            return Response({'status': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        order.status = status_value
        order.save(update_fields=['status'])
        return Response(OrderAdminSerializer(order).data)


class AdminInvoiceView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related('items__product'), id=order_id)
        lines = [
            f'Invoice #{order.id}',
            f'Customer: {order.customer_name} <{order.customer_email}>',
            f'Status: {order.status}',
            '',
            'Items:',
        ]
        for item in order.items.all():
            lines.append(f'- {item.product.name}: {item.quantity} x {item.price}')
        lines.append('')
        lines.append(f'Total: {order.total_price}')
        response = HttpResponse('\n'.join(lines), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename=invoice-{order.id}.txt'
        return response


class AdminCustomerListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = User.objects.annotate(order_count=Count('orders'), total_spent=Sum('orders__total_price')).order_by('-date_joined')
        return Response(CustomerAdminSerializer(qs, many=True).data)


class AdminCustomerStatusView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = bool(request.data.get('is_active'))
        user.save(update_fields=['is_active'])
        return Response(CustomerAdminSerializer(user).data)


class AdminPendingVendorListView(APIView):
    """Return vendor applications that are waiting for a super-admin decision."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        vendors = (
            Vendor.objects.select_related('user')
            .filter(status=Vendor.STATUS_PENDING)
            .order_by('-created_at')
        )
        return Response(PendingVendorSerializer(vendors, many=True).data)


class AdminVendorHistoryListView(APIView):
    """Return every vendor application so decisions remain visible in the dashboard."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        vendors = Vendor.objects.select_related('user').order_by('-updated_at')
        return Response(PendingVendorSerializer(vendors, many=True).data)


class AdminVendorVerificationActionView(APIView):
    """Approve or reject an individual pending vendor application."""

    permission_classes = [IsSuperAdmin]

    def patch(self, request, vendor_id):
        action = (request.data.get('action') or '').lower()
        if action not in {'approve', 'reject'}:
            return Response(
                {'action': 'Use either "approve" or "reject".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = get_object_or_404(
            Vendor.objects.select_related('user'),
            id=vendor_id,
            status=Vendor.STATUS_PENDING,
        )
        approved = action == 'approve'

        with transaction.atomic():
            vendor.status = Vendor.STATUS_APPROVED if approved else Vendor.STATUS_REJECTED
            vendor.save(update_fields=['status', 'updated_at'])
            vendor.user.is_active = approved
            vendor.user.save(update_fields=['is_active'])
            LogEntry.objects.create(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(Vendor).id,
                object_id=str(vendor.id),
                object_repr=str(vendor),
                action_flag=CHANGE,
                change_message=f'Vendor verification action={action} from admin dashboard.',
            )

        return Response({
            'message': f'Vendor {"approved" if approved else "rejected"}.',
            'vendor': PendingVendorSerializer(vendor).data,
        })


class AdminInventoryView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Product.objects.select_related('category').order_by('stock', 'name')
        return Response(ProductAdminSerializer(qs, many=True, context={'request': request}).data)


class AdminInventoryExportView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=inventory.csv'
        writer = csv.writer(response)
        writer.writerow(['name', 'slug', 'category', 'price', 'stock', 'is_active'])
        for product in Product.objects.select_related('category').all():
            writer.writerow([product.name, product.slug, product.category.slug, product.price, product.stock, product.is_active])
        return response


class AdminInventoryImportView(APIView):
    permission_classes = [IsPlatformAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'file': 'CSV file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        rows = csv.DictReader(upload.read().decode('utf-8-sig').splitlines())
        count = 0
        for row in rows:
            category = Category.objects.filter(slug=row.get('category', '')).first()
            if not category:
                continue
            Product.objects.update_or_create(
                slug=row['slug'],
                defaults={
                    'name': row['name'],
                    'category': category,
                    'description': row.get('description', ''),
                    'price': row.get('price') or 0,
                    'stock': row.get('stock') or 0,
                    'is_active': str(row.get('is_active', 'true')).lower() in {'true', '1', 'yes'},
                },
            )
            count += 1
        return Response({'imported': count})


class AdminReportsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        monthly = (
            Order.objects.filter(status__in=SALE_STATUSES).annotate(month=TruncMonth('order_date'))
            .values('month')
            .annotate(revenue=Sum('total_price'), orders=Count('id'))
            .order_by('month')
        )
        product_performance = (
            OrderItem.objects.filter(order__status__in=SALE_STATUSES).values('product__name')
            .annotate(revenue=Sum(F('price') * F('quantity')), quantity=Sum('quantity'))
            .order_by('-revenue')[:10]
        )
        return Response({
            'monthly_sales': [
                {'label': row['month'].strftime('%b %Y'), 'orders': row['orders'], 'revenue': float(row['revenue'] or 0)}
                for row in monthly
            ],
            'product_performance': [
                {'name': row['product__name'] or 'Unknown', 'quantity': row['quantity'], 'revenue': float(row['revenue'] or 0)}
                for row in product_performance
            ],
        })


class AdminSettingsView(APIView):
    permission_classes = [IsPlatformAdmin]

    _defaults = {
        'branding': {'site_name': 'Hardcore Fashion Store', 'theme': 'black-gold'},
        'shipping': {'default': 'Free shipping'},
        'tax': {'enabled': False, 'rate': 0},
        'promotions': [],
        'payments': {'flutterwave': 'configured', 'paypal': 'dependency-installed'},
    }
    # In-memory store (replace with a DB model for persistence across restarts)
    _store: dict = {}

    def _current(self):
        import copy
        base = copy.deepcopy(self._defaults)
        base.update(self._store)
        return base

    def get(self, request):
        return Response(self._current())

    def patch(self, request):
        profile = getattr(request.user, 'admin_profile', None)
        if not profile or profile.role != AdminProfile.ROLE_SUPER_ADMIN:
            return Response({'detail': 'Super admin only.'}, status=status.HTTP_403_FORBIDDEN)
        if not isinstance(request.data, dict):
            return Response({'detail': 'Expected a JSON object.'}, status=status.HTTP_400_BAD_REQUEST)
        AdminSettingsView._store.update(request.data)
        return Response(self._current())


class AdminTransactionsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Order.objects.order_by('-order_date')
        data = [
            {
                'order_id': o.id,
                'customer_name': o.customer_name,
                'customer_email': o.customer_email,
                'transaction_id': o.flutterwave_transaction_id or '—',
                'amount': float(o.total_price),
                'status': o.status,
                'date': o.order_date.strftime('%Y-%m-%d %H:%M'),
            }
            for o in qs
        ]
        return Response(data)


class AdminTransactionActionView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        action = request.data.get('action')
        if action == 'confirm':
            order.status = 'processing'
        elif action == 'reject':
            order.status = 'cancelled'
        else:
            return Response({'detail': 'Invalid action. Use confirm or reject.'}, status=status.HTTP_400_BAD_REQUEST)
        order.save(update_fields=['status'])
        return Response({'order_id': order.id, 'status': order.status})


class AdminCustomerOrdersView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, user_id):
        orders = Order.objects.filter(user_id=user_id).annotate(item_count=Count('items')).order_by('-order_date')
        return Response(OrderAdminSerializer(orders, many=True).data)


class AdminCustomerDeleteView(APIView):
    permission_classes = [IsPlatformAdmin]

    def delete(self, request, user_id):
        # Prevent deleting the currently logged-in admin account
        if request.user.id == user_id:
            return Response(
                {'detail': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminMeView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        profile = request.user.admin_profile
        avatar_url = ''
        if profile.avatar:
            request_obj = request
            avatar_url = request_obj.build_absolute_uri(profile.avatar.url)
        return Response({
            'role':       profile.role,
            'username':   request.user.username,
            'email':      request.user.email,
            'avatar_url': avatar_url,
        })


class AdminAvatarView(APIView):
    permission_classes = [IsPlatformAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        profile = request.user.admin_profile
        avatar = request.FILES.get('avatar')
        if not avatar:
            return Response({'avatar': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.avatar = avatar
        profile.save(update_fields=['avatar'])
        return Response({'avatar_url': request.build_absolute_uri(profile.avatar.url)})

    def delete(self, request):
        profile = request.user.admin_profile
        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=['avatar'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Vendor Management ──────────────────────────────────────────────────────────

class AdminVendorManagementListView(APIView):
    """Full vendor list with product count, revenue, and payout history."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        vendors = Vendor.objects.select_related('user').order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            vendors = vendors.filter(status=status_filter)
        return Response(PendingVendorSerializer(vendors, many=True).data)


class AdminVendorManagementDetailView(APIView):
    """Single vendor detail: profile + products + payouts."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request, vendor_id):
        vendor = get_object_or_404(Vendor.objects.select_related('user'), id=vendor_id)
        products = list(
            vendor.products.values('id', 'name', 'price', 'stock', 'is_active')[:20]
        )
        payouts = list(
            VendorPayout.objects.filter(vendor=vendor)
            .values('id', 'amount', 'method', 'status', 'requested_at', 'processed_at')[:20]
        )
        top_products = (
            OrderItem.objects.filter(product__vendor=vendor)
            .values('product__name')
            .annotate(qty=Sum('quantity'), rev=Sum(F('price') * F('quantity')))
            .order_by('-rev')[:5]
        )
        return Response({
            'vendor': PendingVendorSerializer(vendor).data,
            'products': products,
            'payouts': payouts,
            'top_products': [
                {'name': r['product__name'], 'quantity': r['qty'], 'revenue': float(r['rev'] or 0)}
                for r in top_products
            ],
        })


class AdminVendorActionView(APIView):
    """Approve, reject, suspend, or delete a vendor."""
    permission_classes = [IsSuperAdmin]

    def patch(self, request, vendor_id):
        action = (request.data.get('action') or '').lower()
        if action not in {'approve', 'reject', 'suspend'}:
            return Response({'action': 'Use approve, reject, or suspend.'}, status=status.HTTP_400_BAD_REQUEST)

        vendor = get_object_or_404(Vendor.objects.select_related('user'), id=vendor_id)

        with transaction.atomic():
            if action == 'approve':
                vendor.status = Vendor.STATUS_APPROVED
                vendor.user.is_active = True
            elif action == 'reject':
                vendor.status = Vendor.STATUS_REJECTED
                vendor.user.is_active = False
            elif action == 'suspend':
                vendor.status = 'rejected'  # reuse rejected to block access
                vendor.user.is_active = False
            vendor.save(update_fields=['status', 'updated_at'])
            vendor.user.save(update_fields=['is_active'])
            LogEntry.objects.create(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(Vendor).id,
                object_id=str(vendor.id),
                object_repr=str(vendor),
                action_flag=CHANGE,
                change_message=f'Admin vendor action={action}.',
            )

        return Response({'message': f'Vendor {action}d.', 'vendor': PendingVendorSerializer(vendor).data})

    def delete(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, id=vendor_id)
        LogEntry.objects.create(
            user_id=request.user.id,
            content_type_id=ContentType.objects.get_for_model(Vendor).id,
            object_id=str(vendor.id),
            object_repr=str(vendor),
            action_flag=CHANGE,
            change_message='Admin deleted vendor.',
        )
        vendor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVendorAnalyticsView(APIView):
    """Vendor analytics: totals by status, top 5 by revenue."""
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        total     = Vendor.objects.count()
        approved  = Vendor.objects.filter(status='approved').count()
        pending   = Vendor.objects.filter(status='pending').count()
        rejected  = Vendor.objects.filter(status='rejected').count()
        top5 = (
            VendorOrder.objects.values('vendor__id', 'vendor__store_name')
            .annotate(revenue=Sum('subtotal'), orders=Count('id'))
            .order_by('-revenue')[:5]
        )
        return Response({
            'totals': {'total': total, 'approved': approved, 'pending': pending, 'rejected': rejected},
            'top_vendors': [
                {'id': r['vendor__id'], 'store_name': r['vendor__store_name'],
                 'revenue': float(r['revenue'] or 0), 'orders': r['orders']}
                for r in top5
            ],
        })


# ── Admin Refund Management ────────────────────────────────────────────────────

class AdminRefundListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from .models import Refund
        qs = Refund.objects.select_related('order', 'customer', 'vendor').order_by('-created_at')
        status_f = request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        data = [{
            'id': r.id,
            'order_id': r.order_id,
            'customer': r.customer.username if r.customer else '',
            'vendor': r.vendor.store_name if r.vendor else '',
            'status': r.status,
            'reason': r.reason,
            'notes': r.notes,
            'admin_note': r.admin_note,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        } for r in qs]
        return Response(data)


class AdminRefundActionView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, refund_id):
        from .models import Refund
        refund = get_object_or_404(Refund, id=refund_id)
        new_status = request.data.get('status')
        valid = {s[0] for s in Refund.STATUS_CHOICES}
        if new_status not in valid:
            return Response({'detail': f'status must be one of {valid}.'}, status=status.HTTP_400_BAD_REQUEST)
        refund.status     = new_status
        refund.admin_note = request.data.get('admin_note', refund.admin_note)
        refund.save(update_fields=['status', 'admin_note', 'updated_at'])
        return Response({'id': refund.id, 'status': refund.status, 'admin_note': refund.admin_note})


class AdminRefundReportsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        from .models import Refund
        qs = Refund.objects.all()
        total = qs.count()
        by_status = {s: qs.filter(status=s).count() for s, _ in Refund.STATUS_CHOICES}
        per_vendor = list(
            qs.filter(vendor__isnull=False)
            .values('vendor__store_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        total_orders = Order.objects.count()
        return Response({
            'total_refunds': total,
            'refund_rate': round(total / total_orders * 100, 2) if total_orders else 0,
            'by_status': by_status,
            'per_vendor': per_vendor,
        })
