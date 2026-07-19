import json

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Cart, Order, OrderItem, Shipment
from .serializers import OrderSerializer
from .flutterwave import create_payment, verify_webhook_signature
from .throttles import PaymentRateThrottle
from .email_service import send_tracking_email


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentRateThrottle])
def flutterwave_initialize(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()
    if not items.exists():
        return Response({'error': 'Cart is empty'}, status=400)

    body = request.data or {}
    customer = {
        'name': body.get('customer_name', request.user.get_username()),
        'email': body.get('customer_email', request.user.email or ''),
        'phone_number': body.get('customer_phone', ''),
    }

    total = sum(i.product.price * i.quantity for i in items)
    order = Order.objects.create(
        user=request.user,
        customer_name=customer['name'],
        customer_email=customer['email'],
        customer_phone=customer.get('phone_number', '') or '',
        customer_address=body.get('customer_address', ''),
        total_price=total,
        payment_method='flutterwave',
        status='pending',
    )

    for it in items:
        OrderItem.objects.create(
            order=order,
            product=it.product,
            quantity=it.quantity,
            price=it.product.price,
        )

    cart.items.all().delete()

    reference = f'order_{order.id}_{get_random_string(6).lower()}'
    tx_ref = reference

    redirect_url = request.build_absolute_uri(
        reverse('order_confirmation', kwargs={'order_id': order.id})
    )

    payment_payload = create_payment(
        reference=reference,
        tx_ref=tx_ref,
        amount=str(total),
        customer=customer,
        redirect_url=redirect_url,
    )

    link = payment_payload.get('data', {}).get('link')
    return Response({'order': OrderSerializer(order).data, 'payment_link': link, 'tx_ref': tx_ref})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def flutterwave_webhook(request):
    raw = request.body

    received_signature = (
        request.META.get('HTTP_X_SIGNATURE') or
        request.META.get('HTTP_X_FLW_SIGNATURE') or ''
    )

    if not verify_webhook_signature(raw, received_signature):
        return HttpResponse('invalid signature', status=400)

    try:
        payload = json.loads(raw.decode('utf-8'))
    except Exception:
        payload = {}

    data = payload.get('data') or {}
    tx_ref = data.get('tx_ref') or ''
    status = data.get('status') or ''

    order_id = None
    if tx_ref.startswith('order_'):
        try:
            order_id = int(tx_ref.split('_')[1])
        except Exception:
            order_id = None

    if not order_id:
        return HttpResponse('tx_ref missing order', status=200)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return HttpResponse('order not found', status=200)

    if status in ['successful', 'paid']:
        order.status = 'processing'
        order.flutterwave_transaction_id = data.get('transaction_id') or ''
        order.save(update_fields=['status', 'flutterwave_transaction_id'])
        shipment, created = Shipment.objects.get_or_create(order=order)
        if created and order.customer_email:
            track_url = request.build_absolute_uri(
                f'/track-shipment/?code={shipment.tracking_number}'
            )
            send_tracking_email(
                to_email=order.customer_email,
                customer_name=order.customer_name or 'Customer',
                order_id=order.id,
                tracking_number=shipment.tracking_number,
                track_url=track_url,
            )

    return HttpResponse('ok', status=200)
