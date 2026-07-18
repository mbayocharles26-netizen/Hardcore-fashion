"""
Refund Management API
- Customer: request refund, list own refunds
- Vendor:   approve/reject refunds for their products
- Admin:    override status, mark processed, reports
"""
from django.db.models import Count, Q, Sum
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, Refund, Vendor, VendorOrder, VendorNotification
from .admin_api import IsPlatformAdmin
from .vendor_api import IsApprovedVendor, _vendor



# ── Serializer ─────────────────────────────────────────────────────────────────

class RefundSerializer(serializers.ModelSerializer):
    order_id       = serializers.IntegerField(source='order.id', read_only=True)
    customer_name  = serializers.SerializerMethodField()
    vendor_name    = serializers.SerializerMethodField()

    class Meta:
        model  = Refund
        fields = [
            'id', 'order_id', 'customer_name', 'vendor_name',
            'status', 'reason', 'notes', 'admin_note',
            'created_at', 'updated_at',
        ]

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username if obj.customer else ''

    def get_vendor_name(self, obj):
        return obj.vendor.store_name if obj.vendor else ''


# ── Customer: create request ───────────────────────────────────────────────────

class RefundRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        reason   = (request.data.get('reason') or '').strip()
        notes    = (request.data.get('notes') or '').strip()

        if not order_id or not reason:
            return Response({'detail': 'order_id and reason are required.'}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(id=order_id, user=request.user, status__in=['delivered', 'cancelled']).first()
        if not order:
            return Response({'detail': 'Order not eligible for refund.'}, status=status.HTTP_404_NOT_FOUND)

        if Refund.objects.filter(order=order, customer=request.user).exists():
            return Response({'detail': 'Refund already requested for this order.'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine primary vendor from first vendor_order
        vendor_order = VendorOrder.objects.filter(order=order).select_related('vendor').first()
        vendor = vendor_order.vendor if vendor_order else None

        refund = Refund.objects.create(
            order=order, customer=request.user, vendor=vendor,
            reason=reason, notes=notes,
        )

        # Notify the vendor in real-time about a new refund request.
        # (If the refund has no vendor assigned, skip notification.)
        if refund.vendor_id:
            notif = VendorNotification.objects.create(
                vendor_id=refund.vendor_id,
                type=VendorNotification.TYPE_REVIEW,
                title=f'New refund request for Order #{refund.order_id}',
                body=f'Refund #{refund.id} requested by {request.user.email or request.user.username}.',
                link=f'/vendor-refunds/',
            )
            try:
                from .vendor_api import push_vendor_notification
                push_vendor_notification(notif)
            except Exception:
                # Fail open: refund should still be created even if WS push fails.
                pass

        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)



# ── Vendor: approve / reject ───────────────────────────────────────────────────

class RefundVendorActionView(APIView):
    permission_classes = [IsApprovedVendor]

    def patch(self, request, refund_id):
        vendor = _vendor(request)
        refund = Refund.objects.filter(id=refund_id, vendor=vendor, status=Refund.STATUS_PENDING).first()
        if not refund:
            return Response({'detail': 'Not found or already actioned.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action not in ('approve', 'reject'):
            return Response({'detail': 'action must be approve or reject.'}, status=status.HTTP_400_BAD_REQUEST)

        refund.status = Refund.STATUS_APPROVED if action == 'approve' else Refund.STATUS_REJECTED
        refund.notes  = request.data.get('notes', refund.notes)
        refund.save(update_fields=['status', 'notes', 'updated_at'])
        return Response(RefundSerializer(refund).data)


# ── Admin: override + mark processed ──────────────────────────────────────────

class RefundAdminActionView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, refund_id):
        refund = Refund.objects.filter(id=refund_id).first()
        if not refund:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        valid = {s[0] for s in Refund.STATUS_CHOICES}
        if new_status not in valid:
            return Response({'detail': f'status must be one of {valid}.'}, status=status.HTTP_400_BAD_REQUEST)

        refund.status     = new_status
        refund.admin_note = request.data.get('admin_note', refund.admin_note)
        refund.save(update_fields=['status', 'admin_note', 'updated_at'])
        return Response(RefundSerializer(refund).data)


# ── List (role-aware) ──────────────────────────────────────────────────────────

class RefundListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if getattr(user, 'admin_profile', None) and user.admin_profile.is_active:
            qs = Refund.objects.select_related('order', 'customer', 'vendor').all()
        elif getattr(user, 'vendor_profile', None) and user.vendor_profile.status == 'approved':
            qs = Refund.objects.filter(vendor=user.vendor_profile).select_related('order', 'customer', 'vendor')
        else:
            qs = Refund.objects.filter(customer=user).select_related('order', 'customer', 'vendor')

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = RefundSerializer(qs, many=True)
        return Response(serializer.data)


# ── Admin reports ──────────────────────────────────────────────────────────────

class RefundReportsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Refund.objects.all()
        total = qs.count()
        by_status = {s: qs.filter(status=s).count() for s, _ in Refund.STATUS_CHOICES}
        per_vendor = (
            qs.filter(vendor__isnull=False)
            .values('vendor__store_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        total_orders = Order.objects.count()
        refund_rate  = round((total / total_orders * 100), 2) if total_orders else 0

        return Response({
            'total_refunds': total,
            'refund_rate':   refund_rate,
            'by_status':     by_status,
            'per_vendor':    list(per_vendor),
        })
