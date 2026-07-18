from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from .models import (
    Category, Product, Order, OrderItem, Cart, CartItem,
    CustomerProfile, Address, WishlistItem, VendorOrder,
    Shipment,
    ProductReviewReport, SupportTicket, SupportMessage, LoyaltyTransaction,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ['name', 'slug']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display  = ['name', 'vendor', 'category', 'price', 'stock', 'is_active', 'created_at']
    list_filter   = ['category', 'is_active', 'is_featured', 'vendor']
    search_fields = ['name', 'vendor__store_name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Vendors only see their own products
        return qs.filter(vendor__user=request.user)

    def save_model(self, request, obj, form, change):
        # Auto-assign vendor when a vendor creates a product
        if not request.user.is_superuser and not obj.vendor_id:
            vendor = getattr(request.user, 'vendor_profile', None)
            if vendor:
                obj.vendor = vendor
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        # Vendors cannot change product ownership
        if not request.user.is_superuser:
            return ['vendor']
        return []


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class ShipmentInline(admin.StackedInline):
    model = Shipment
    extra = 0
    max_num = 1
    readonly_fields = ['tracking_number', 'updated_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ['id', 'customer_name', 'status', 'payment_method', 'total_price', 'order_date']
    list_filter   = ['status', 'payment_method']
    search_fields = ['customer_name', 'customer_email']
    inlines       = [OrderItemInline, ShipmentInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Vendors only see orders that contain their products
        return qs.filter(vendor_orders__vendor__user=request.user).distinct()


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['tracking_number', 'order', 'status', 'estimated_arrival', 'current_location', 'updated_at']
    list_filter = ['status']
    search_fields = ['tracking_number', 'order__id', 'order__customer_name', 'order__customer_email']
    readonly_fields = ['tracking_number', 'updated_at']
    list_select_related = ['order']


@admin.register(VendorOrder)
class VendorOrderAdmin(admin.ModelAdmin):
    list_display  = ['id', 'vendor', 'order', 'status', 'subtotal', 'created_at']
    list_filter   = ['status', 'vendor']
    search_fields = ['order__id', 'vendor__store_name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Vendors only see their own sub-orders
        return qs.filter(vendor__user=request.user)

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ['vendor', 'order', 'subtotal']
        return []


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'phone', 'loyalty_points', 'preferred_currency']
    search_fields = ['user__username', 'user__email']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display  = ['user', 'full_name', 'city', 'country', 'type', 'is_default']
    list_filter   = ['type', 'country']
    search_fields = ['user__username', 'full_name', 'city']


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display  = ['user', 'product', 'added_at']
    search_fields = ['user__username', 'product__name']


@admin.register(ProductReviewReport)
class ProductReviewReportAdmin(admin.ModelAdmin):
    list_display = ['review', 'reporter', 'reason', 'resolved', 'created_at']
    list_filter  = ['reason', 'resolved']
    actions      = ['mark_resolved']

    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True)
    mark_resolved.short_description = 'Mark selected reports as resolved'


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ['created_at']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'type', 'subject', 'status', 'created_at']
    list_filter   = ['type', 'status']
    search_fields = ['subject', 'user__username']
    inlines       = [SupportMessageInline]


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'type', 'points', 'balance_after', 'order', 'created_at']
    list_filter   = ['type']
    search_fields = ['user__username']


def _require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Only superusers can perform this action.')

@admin.action(description='Deactivate selected users')
def deactivate_users(modeladmin, request, queryset):
    _require_superuser(request)
    queryset.update(is_active=False)

@admin.action(description='Activate selected users')
def activate_users(modeladmin, request, queryset):
    _require_superuser(request)
    queryset.update(is_active=True)

@admin.action(description='Delete selected users')
def delete_users(modeladmin, request, queryset):
    _require_superuser(request)
    # Use Django's built-in deletion confirmation flow.
    return modeladmin.delete_selected(request, queryset)

# Replace the built-in User admin registration with a custom admin class.
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    actions = [deactivate_users, activate_users, delete_users]

admin.site.register(Cart)
admin.site.register(CartItem)

# Vendor-specific admin (approval/rejection actions, payouts, notifications)
from . import admin_vendor  # noqa: F401
