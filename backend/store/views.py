from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .forms import CheckoutForm
from .models import Category, Product, Order, OrderItem, Cart, CartItem, VendorOrder, Vendor, Shipment, OTPVerification
from .cart_service import get_cart
from .otp import otp_hash
from .serializers_auth import VerifySignupOtpSerializer


from .serializers import (
    UserSerializer, CategorySerializer, ProductSerializer,
    OrderSerializer, CartSerializer, CartItemSerializer
)




class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        otp_serializer = VerifySignupOtpSerializer(data=request.data or {})
        otp_serializer.is_valid(raise_exception=True)
        data = otp_serializer.validated_data

        password = data.get('password')
        confirm_password = data.get('confirm_password')
        if password != confirm_password:
            return Response(
                {'error': 'Passwords do not match.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = data.get('username')
        email = (data.get('email') or '').strip().lower()
        role = data.get('role', 'customer')

        if not username or not email or not password:
            return Response(
                {'error': 'username, email, and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp = data.get('otp')
        verification = (
            OTPVerification.objects.filter(
                email__iexact=email,
                purpose=OTPVerification.PURPOSE_SIGNUP,
                verified_at__isnull=True,
            )
            .order_by('-created_at')
            .first()
        )

        if not verification:
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.expires_at <= timezone.now():
            verification.delete()
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.attempts >= 5:
            verification.delete()
            return Response({'otp': 'Too many failed attempts. Request a new OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.otp_hash != otp_hash(otp):
            verification.attempts += 1
            verification.save(update_fields=['attempts'])
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(
            data={
                'username': username,
                'email': email,
                'password': password,
            }
        )
        serializer.is_valid(raise_exception=True)

        try:
            user = serializer.save()
        except Exception:
            # Keep error response simple for frontend
            return Response(
                {'error': 'User could not be created (possibly already exists).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification.verified_at = timezone.now()
        verification.save(update_fields=['verified_at'])

        # If they sign up as vendor, create Vendor profile (optional)
        if role == 'vendor':
            from .models import Vendor
            Vendor.objects.get_or_create(
                user=user,
                defaults={
                    'store_name': username,
                    'description': '',
                    'email': email,
                    'status': 'pending',
                },
            )

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)



class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True)
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        featured = self.request.query_params.get('featured')
        limit = self.request.query_params.get('limit')
        if category:
            qs = qs.filter(category__slug=category)
        if search:
            terms = [t for t in search.split() if t]
            for term in terms:
                qs = qs.filter(
                    Q(name__icontains=term) |
                    Q(description__icontains=term) |
                    Q(category__name__icontains=term) |
                    Q(attributes__icontains=term)
                )
        if featured and featured.lower() in {'1', 'true', 'yes'}:
            qs = qs.filter(is_featured=True)
        if limit:
            try:
                qs = qs[: max(1, min(int(limit), 50))]
            except ValueError:
                pass
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]


class OrderListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related('shipment').prefetch_related('items__product__vendor'),
            id=order_id,
            user=request.user,
        )
        return Response(OrderSerializer(order).data)


class ShipmentTrackingView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, tracking_number):
        shipment = get_object_or_404(
            Shipment.objects.select_related('order'),
            tracking_number__iexact=tracking_number.strip(),
        )
        return Response({
            'tracking_number': shipment.tracking_number,
            'status': shipment.status,
            'estimated_arrival': shipment.estimated_arrival.isoformat() if shipment.estimated_arrival else None,
            'current_location': shipment.current_location,
            'updated_at': shipment.updated_at.isoformat(),
        })


class CartView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cart = get_cart(request)
        return Response(CartSerializer(cart).data)

    def post(self, request):
        cart = get_cart(request)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        if quantity > product.stock:
            return Response({'error': 'Not enough stock'}, status=status.HTTP_400_BAD_REQUEST)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity = min(item.quantity + quantity, product.stock)
        else:
            item.quantity = quantity
        item.save()
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    def patch(self, request, item_id=None):
        try:
            item = CartItem.objects.select_related('product').get(id=item_id, cart=get_cart(request))
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
        quantity = int(request.data.get('quantity', 1))
        if quantity < 1:
            item.delete()
        else:
            item.quantity = min(quantity, item.product.stock)
            item.save()
        cart = get_cart(request)
        return Response(CartSerializer(cart).data)

    def delete(self, request, item_id=None):
        try:
            item = CartItem.objects.get(id=item_id, cart=get_cart(request))
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.db import transaction
        from django.db.models import F

        cart = get_cart(request)
        items = cart.items.select_related('product', 'product__vendor').all()
        if not items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate stock & compute totals
        order_total = 0
        for ci in items:
            if ci.product.stock < ci.quantity:
                return Response({'error': f'Not enough stock for {ci.product.name}'}, status=status.HTTP_400_BAD_REQUEST)
            order_total += ci.product.price * ci.quantity

        with transaction.atomic():
            # Create unified order
            order = Order.objects.create(
                user=request.user,
                customer_name=request.user.get_username(),
                customer_email=request.user.email,
                total_price=order_total,
            )

            # Group by vendor
            vendor_order_map = {}
            for ci in items:
                vendor = ci.product.vendor
                if vendor is None:
                    raise ValidationError('Product is not assigned to a vendor.')
                if vendor.id not in vendor_order_map:
                    vendor_order_map[vendor.id] = VendorOrder.objects.create(
                        order=order,
                        vendor=vendor,
                        subtotal=0,
                    )

            # Create order items and accumulate vendor subtotals
            vendor_subtotals = {vid: 0 for vid in vendor_order_map.keys()}
            for ci in items:
                vendor = ci.product.vendor
                vo = vendor_order_map[vendor.id]

                OrderItem.objects.create(
                    order=order,
                    product=ci.product,
                    quantity=ci.quantity,
                    price=ci.product.price,
                )
                vendor_subtotals[vendor.id] += ci.product.price * ci.quantity

                # Stock update
                Product.objects.filter(id=ci.product_id, stock__gte=ci.quantity).update(
                    stock=F('stock') - ci.quantity
                )

            # Save vendor subtotals
            for vid, subtotal in vendor_subtotals.items():
                VendorOrder.objects.filter(id=vendor_order_map[vid].id).update(subtotal=subtotal)

            cart.items.all().delete()

        Shipment.objects.get_or_create(order=order)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)



# ─────────────────────────────────────────────────────────────
# Django (server-rendered) Checkout Flow


def checkout_view(request):
    return render(request, 'checkout.html')


def process_order(request):
    if request.method != 'POST':
        return redirect('checkout')

    cart = get_cart(request)
    items = cart.items.select_related('product').all()
    if not items.exists():
        return render(request, 'checkout.html', {'cart_items': [], 'order_total': 0, 'error': 'Your cart is empty.'})

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        order_total = sum(i.subtotal for i in items)
        return render(
            request,
            'checkout.html',
            {'cart_items': items, 'order_total': order_total, 'form': form, 'error': None},
        )

    data = form.cleaned_data
    order_total = sum(i.subtotal for i in items)

    order = Order.objects.create(
        user=request.user,
        customer_name=data['customer_name'],
        customer_email=data['customer_email'],
        customer_phone=data.get('customer_phone', '') or '',
        customer_address=data['customer_address'],
        total_price=order_total,
    )

    from django.db import transaction
    from django.db.models import F

    with transaction.atomic():
        # Group items by vendor
        vendor_order_map = {}
        vendor_subtotals = {}
        for cart_item in items:
            vendor = cart_item.product.vendor
            if vendor is None:
                raise ValidationError('Product is not assigned to a vendor.')
            if vendor.id not in vendor_order_map:
                vendor_order_map[vendor.id] = VendorOrder.objects.create(
                    order=order,
                    vendor=vendor,
                    subtotal=0,
                )
                vendor_subtotals[vendor.id] = 0

        for cart_item in items:
            vendor = cart_item.product.vendor
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price=cart_item.product.price,
            )
            vendor_subtotals[vendor.id] += cart_item.product.price * cart_item.quantity

            Product.objects.filter(id=cart_item.product_id, stock__gte=cart_item.quantity).update(
                stock=F('stock') - cart_item.quantity
            )

        for vid, subtotal in vendor_subtotals.items():
            VendorOrder.objects.filter(id=vendor_order_map[vid].id).update(subtotal=subtotal)

        cart.items.all().delete()

    Shipment.objects.get_or_create(order=order)

    return redirect(reverse('order_confirmation', kwargs={'order_id': order.id}))


def order_confirmation(request, order_id: int):
    from .jwt_auth import get_user_from_jwt_cookie_or_header
    user = get_user_from_jwt_cookie_or_header(request)
    order = None
    if user is not None and user.is_authenticated:
        order = get_object_or_404(
            Order.objects.select_related('shipment'),
            id=order_id,
            user=user,
        )

    items = order.items.select_related('product').all() if order else []
    return render(
        request,
        'order_confirmation.html',
        {
            'order': order,
            'order_items': items,
            'shipment': getattr(order, 'shipment', None) if order else None,
            'order_id': order_id,
        },
    )


class AuthMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        })


@login_required
def login_redirect(request):
    """Role-based redirect after successful Django login."""
    from .dashboard_access import get_role
    role = get_role(request.user)
    if role == 'admin':
        return redirect('admin_dashboard')
    if role == 'vendor':
        return redirect('vendor_dashboard')
    return redirect('customer_dashboard')
