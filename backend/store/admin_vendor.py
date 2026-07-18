from django.contrib import admin
from .models import (
    Vendor, VendorVerification, VendorDocument, VendorStaffMember,
    VendorPayout, ProductReview, VendorNotification,
)


class VendorDocumentInline(admin.TabularInline):
    model = VendorDocument
    extra = 0
    readonly_fields = ['uploaded_at']


class VendorStaffInline(admin.TabularInline):
    model = VendorStaffMember
    extra = 0


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display  = ('store_name', 'email', 'phone', 'status', 'commission_rate', 'created_at')
    list_filter   = ('status',)
    search_fields = ('store_name', 'email')
    inlines       = [VendorDocumentInline, VendorStaffInline]

    # Keep bulk actions, but per-row approvals are handled by the dedicated
    # Verify Vendors page below.
    actions       = ['approve_vendors', 'reject_vendors']

    def approve_vendors(self, request, queryset):
        queryset.update(status='approved')
        for v in queryset:
            if getattr(v, 'user_id', None):
                v.user.is_active = True
                v.user.save(update_fields=['is_active'])
        self.message_user(request, 'Selected vendors have been approved.')
    approve_vendors.short_description = 'Approve selected vendors'

    def reject_vendors(self, request, queryset):
        queryset.update(status='rejected')
        for v in queryset:
            if getattr(v, 'user_id', None):
                v.user.is_active = False
                v.user.save(update_fields=['is_active'])
        self.message_user(request, 'Selected vendors have been rejected.')
    reject_vendors.short_description = 'Reject selected vendors'

    # ──────────────────────────────────────────────────────────────────────────
    # Verify Vendors page
    # ──────────────────────────────────────────────────────────────────────────

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('verify-vendors/', self.admin_site.admin_view(self.verify_vendors_view), name='store_vendor_verify_vendors'),
        ]
        # Prepend so it appears before the default URLs.
        return custom_urls + urls

    def verify_vendors_view(self, request):
        from django.contrib import messages
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        from django.db import transaction
        from django.shortcuts import redirect, render

        if not request.user.is_active or not request.user.is_staff:
            # admin_view already enforces permissions, but keep this safe.
            return redirect('admin:index')

        if request.method == 'POST':
            action_value = request.POST.get('vendor_action', '')
            try:
                action, vendor_id_str = action_value.split('-', 1)
                vendor_id = int(vendor_id_str)
            except Exception:
                messages.error(request, 'Invalid action.')
                return redirect(request.path)

            vendor = Vendor.objects.select_related('user').filter(id=vendor_id, status='pending').first()
            if not vendor:
                messages.warning(request, 'Vendor not found or already processed.')
                return redirect(request.path)

            with transaction.atomic():
                if action == 'approve':
                    vendor.status = Vendor.STATUS_APPROVED
                    vendor.user.is_active = True
                    vendor.user.save(update_fields=['is_active'])
                    vendor.save(update_fields=['status'])
                    messages.success(request, f'Approved vendor: {vendor.store_name}')
                elif action == 'reject':
                    vendor.status = Vendor.STATUS_REJECTED
                    vendor.user.is_active = False
                    vendor.user.save(update_fields=['is_active'])
                    vendor.save(update_fields=['status'])
                    messages.warning(request, f'Rejected vendor: {vendor.store_name}')
                else:
                    messages.error(request, 'Invalid vendor action.')
                    return redirect(request.path)

                # Persist audit entry in admin history
                ct = ContentType.objects.get_for_model(Vendor)
                LogEntry.objects.create(
                    user_id=request.user.id,
                    content_type_id=ct.id,
                    object_id=vendor.id,
                    object_repr=str(vendor),
                    action_flag=CHANGE,
                    change_message=f'Vendor verification action={action} by {request.user.get_username()}',
                )

            return redirect(request.path)

        pending_vendors = Vendor.objects.select_related('user').filter(status=Vendor.STATUS_PENDING).order_by('-created_at')
        context = {
            **self.admin_site.each_context(request),
            'pending_vendors': pending_vendors,
        }
        return render(request, 'admin/verify_vendors.html', context)


@admin.register(VendorVerification)
class VendorVerificationAdmin(admin.ModelAdmin):
    """A sidebar entry that opens the dedicated pending-vendor review queue."""

    def changelist_view(self, request, extra_context=None):
        # Reuse the verification handler so both the sidebar entry and the
        # legacy vendor-admin URL support the same audited approve/reject flow.
        return VendorAdmin.verify_vendors_view(self, request)



@admin.register(VendorPayout)
class VendorPayoutAdmin(admin.ModelAdmin):
    list_display  = ('id', 'vendor', 'amount', 'method', 'status', 'requested_at', 'processed_at')
    list_filter   = ('status', 'method')
    search_fields = ('vendor__store_name', 'reference')
    readonly_fields = ('requested_at',)


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display  = ('product', 'user', 'rating', 'is_visible', 'created_at')
    list_filter   = ('rating', 'is_visible')
    search_fields = ('product__name',)


@admin.register(VendorNotification)
class VendorNotificationAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'type', 'title', 'is_read', 'created_at')
    list_filter  = ('type', 'is_read')

