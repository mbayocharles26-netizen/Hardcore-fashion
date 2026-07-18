"""
Customer Dashboard API
All endpoints require an authenticated user (any regular customer).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Address, Category, CustomerProfile, LoyaltyTransaction,
    Order, OrderItem, Product, ProductReview, Shipment,
    WishlistItem,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _profile(user):
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    return profile


# ── Serializers ────────────────────────────────────────────────────────────────

class CustomerProfileSerializer(serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username', read_only=True)
    email      = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name  = serializers.CharField(source='user.last_name')

    class Meta:
        model  = CustomerProfile
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'loyalty_points', 'preferred_currency', 'created_at',
        ]
        read_only_fields = ['username', 'email', 'loyalty_points', 'created_at']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, val in user_data.items():
            setattr(instance.user, attr, val)
        instance.user.save(update_fields=list(user_data.keys()))
        return super().update(instance, validated_data)


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Address
        fields = [
            'id', 'label', 'type', 'full_name', 'line1', 'line2',
            'city', 'state', 'postcode', 'country', 'phone', 'is_default',
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    product_slug  = serializers.SlugField(source='product.slug', read_only=True)

    class Meta:
        model  = OrderItem
        fields = ['id', 'product', 'product_name', 'product_image', 'product_slug', 'quantity', 'price']


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Shipment
        fields = ['tracking_number', 'status', 'estimated_arrival', 'current_location', 'updated_at']


class CustomerOrderSerializer(serializers.ModelSerializer):
    items    = OrderItemSerializer(many=True, read_only=True)
    shipment = ShipmentSerializer(read_only=True)

    class Meta:
        model  = Order
        fields = [
            'id', 'status', 'order_date', 'total_price', 'subtotal',
            'shipping_cost', 'tax_amount', 'payment_method',
            'shipping_address', 'notes', 'loyalty_points_earned',
            'loyalty_points_used', 'items', 'shipment',
        ]


class WishlistItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)
    product_slug  = serializers.SlugField(source='product.slug', read_only=True)
    in_stock      = serializers.BooleanField(source='product.in_stock', read_only=True)

    class Meta:
        model  = WishlistItem
        fields = ['id', 'product', 'product_name', 'product_price', 'product_image', 'product_slug', 'in_stock', 'added_at']


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LoyaltyTransaction
        fields = ['id', 'type', 'points', 'balance_after', 'note', 'created_at']


class ProductReviewSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.SlugField(source='product.slug', read_only=True)

    class Meta:
        model  = ProductReview
        fields = ['id', 'product', 'product_name', 'product_slug', 'rating', 'title', 'body', 'created_at']
        read_only_fields = ['created_at']


# ── Dashboard ──────────────────────────────────────────────────────────────────

class CustomerDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user    = request.user
        profile = _profile(user)
        orders  = Order.objects.filter(user=user)

        total_spend = orders.aggregate(t=Sum('total_price'))['t'] or Decimal('0')

        active_statuses = ('pending', 'processing', 'shipped')
        active_orders   = orders.filter(status__in=active_statuses).count()

        recent_orders = (
            orders.prefetch_related('items__product')
            .order_by('-order_date')[:5]
        )

        monthly_spend = (
            orders.annotate(month=TruncMonth('order_date'))
            .values('month')
            .annotate(total=Sum('total_price'))
            .order_by('month')
        )

        wishlist_count = WishlistItem.objects.filter(user=user).count()

        return Response({
            'metrics': {
                'total_orders':    orders.count(),
                'active_orders':   active_orders,
                'total_spend':     float(total_spend),
                'loyalty_points':  profile.loyalty_points,
                'wishlist_count':  wishlist_count,
            },
            'recent_orders': CustomerOrderSerializer(recent_orders, many=True).data,
            'monthly_spend': [
                {'label': r['month'].strftime('%b %Y'), 'total': float(r['total'] or 0)}
                for r in monthly_spend
            ],
        })


# ── Orders ─────────────────────────────────────────────────────────────────────

class CustomerOrderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (
            Order.objects
            .filter(user=request.user)
            .prefetch_related('items__product')
            .select_related('shipment')
            .order_by('-order_date')
        )
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(CustomerOrderSerializer(qs, many=True).data)


class CustomerOrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = (
                Order.objects
                .prefetch_related('items__product')
                .select_related('shipment')
                .get(id=order_id, user=request.user)
            )
        except Order.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CustomerOrderSerializer(order).data)


class CustomerOrderInvoiceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related('items__product').get(
                id=order_id, user=request.user
            )
        except Order.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        lines = [
            f'Invoice — Order #{order.id}',
            f'Date: {order.order_date.strftime("%d %b %Y")}',
            f'Customer: {order.customer_name} <{order.customer_email}>',
            f'Status: {order.status}',
            '',
            'Items:',
        ]
        for item in order.items.all():
            lines.append(f'  {item.product.name}: {item.quantity} x £{item.price}')
        lines += [
            '',
            f'Subtotal:      £{order.subtotal}',
            f'Shipping:      £{order.shipping_cost}',
            f'Tax:           £{order.tax_amount}',
            f'Total:         £{order.total_price}',
        ]
        response = HttpResponse('\n'.join(lines), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename=invoice-{order.id}.txt'
        return response


# ── Wishlist ───────────────────────────────────────────────────────────────────

class CustomerWishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = WishlistItem.objects.filter(user=request.user).select_related('product')
        return Response(WishlistItemSerializer(qs, many=True).data)

    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'detail': 'product_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
        return Response(
            WishlistItemSerializer(item).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CustomerWishlistItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, item_id):
        deleted, _ = WishlistItem.objects.filter(id=item_id, user=request.user).delete()
        if not deleted:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Wallet / Loyalty ───────────────────────────────────────────────────────────

class CustomerWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = _profile(request.user)
        transactions = LoyaltyTransaction.objects.filter(user=request.user).order_by('-created_at')[:30]
        earned = transactions.filter(type='earn').aggregate(t=Sum('points'))['t'] or 0
        spent  = transactions.filter(type='spend').aggregate(t=Sum('points'))['t'] or 0
        return Response({
            'balance':      profile.loyalty_points,
            'total_earned': earned,
            'total_spent':  abs(spent),
            'transactions': LoyaltyTransactionSerializer(transactions, many=True).data,
        })


# ── Notifications ──────────────────────────────────────────────────────────────
# Customer notifications are derived from order status changes (no separate model needed).
# We synthesise them from recent orders so no extra migration is required.

class CustomerNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(user=request.user)
            .select_related('shipment')
            .order_by('-order_date')[:20]
        )
        notifications = []
        for order in orders:
            icon = {
                'pending':    '🕐',
                'processing': '⚙️',
                'shipped':    '🚚',
                'delivered':  '✅',
                'cancelled':  '❌',
            }.get(order.status, '📦')
            tracking = getattr(getattr(order, 'shipment', None), 'tracking_number', None)
            body = f'Total: £{order.total_price}  •  {order.order_date.strftime("%d %b %Y")}'
            if order.status == 'processing' and tracking:
                body += f'  •  Tracking: {tracking}'
            elif order.status == 'cancelled':
                body = f'Your payment was rejected. {body}'
            notifications.append({
                'id':         order.id,
                'title':      f'Order #{order.id} — {order.status.capitalize()}',
                'body':       body,
                'icon':       icon,
                'order_id':   order.id,
                'created_at': order.order_date.isoformat(),
            })
        return Response(notifications)


# ── Profile ────────────────────────────────────────────────────────────────────

class CustomerProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        return Response(CustomerProfileSerializer(_profile(request.user)).data)

    def patch(self, request):
        profile    = _profile(request.user)
        serializer = CustomerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CustomerAvatarView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        profile = _profile(request.user)
        avatar = request.FILES.get('avatar')
        if not avatar:
            return Response({'avatar': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.avatar = avatar
        profile.save(update_fields=['avatar'])
        return Response({'avatar_url': request.build_absolute_uri(profile.avatar.url)})

    def delete(self, request):
        profile = _profile(request.user)
        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=['avatar'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user         = request.user
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')

        if not user.check_password(old_password):
            return Response({'old_password': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'status': 'Password updated.'})


class CustomerDeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        password = request.data.get('password', '')
        if not request.user.check_password(password):
            return Response({'password': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Addresses ──────────────────────────────────────────────────────────────────

class CustomerAddressListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Address.objects.filter(user=request.user)
        return Response(AddressSerializer(qs, many=True).data)

    def post(self, request):
        serializer = AddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CustomerAddressDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, address_id):
        try:
            address = Address.objects.get(id=address_id, user=request.user)
        except Address.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AddressSerializer(address, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, address_id):
        deleted, _ = Address.objects.filter(id=address_id, user=request.user).delete()
        if not deleted:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Reviews ────────────────────────────────────────────────────────────────────

class CustomerReviewListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ProductReview.objects.filter(user=request.user).select_related('product')
        return Response(ProductReviewSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ProductReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        # Only allow review if customer has purchased the product
        purchased = OrderItem.objects.filter(
            order__user=request.user, product=product
        ).exists()
        if not purchased:
            return Response(
                {'detail': 'You can only review products you have purchased.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        review, created = ProductReview.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                'rating': serializer.validated_data.get('rating', 5),
                'title':  serializer.validated_data.get('title', ''),
                'body':   serializer.validated_data.get('body', ''),
            },
        )
        return Response(
            ProductReviewSerializer(review).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CustomerReviewDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, review_id):
        deleted, _ = ProductReview.objects.filter(id=review_id, user=request.user).delete()
        if not deleted:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
