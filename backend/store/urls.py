from django.urls import path

from . import views
from . import admin_api
from . import vendor_api
from . import customer_api
from .views import AuthMeView
from .recommendations import ProductRecommendationsView
from .auth_views import RequestForgotPasswordOtpView, RequestSignupOtpView, VerifyForgotPasswordOtpView
from .flutterwave_views import flutterwave_initialize, flutterwave_webhook
from .analytics_dashboard_view import analytics_dashboard
from .analytics_views import product_view_track, analytics_dashboard_kpis
from .analytics_api_views import (
    MonthlySalesView, ProductPerformanceView, SalesTrendView, TopProductsView,
    TotalRevenueView, RevenuePerUserView, RevenuePerVendorView,
)
from .refund_api import (
    RefundRequestView, RefundVendorActionView, RefundAdminActionView,
    RefundListView, RefundReportsView,
)
from .admin_api import (
    AdminVendorManagementListView, AdminVendorManagementDetailView,
    AdminVendorActionView, AdminVendorAnalyticsView,
    AdminRefundListView, AdminRefundActionView, AdminRefundReportsView,
)


urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('auth/me/', AuthMeView.as_view(), name='api-auth-me'),
    path('register/', views.RegisterView.as_view(), name='api-register'),
    path('register/request-otp/', RequestSignupOtpView.as_view(), name='api-register-request-otp'),
    path('password/request-otp/', RequestForgotPasswordOtpView.as_view(), name='api-password-request-otp'),
    path('password/verify-otp/', VerifyForgotPasswordOtpView.as_view(), name='api-password-verify-otp'),

    # ── Public storefront ─────────────────────────────────────────────────────
    path('categories/', views.CategoryListView.as_view(), name='api-categories'),
    path('products/', views.ProductListView.as_view(), name='api-products'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='api-product-detail'),
    path('products/<int:product_id>/recommendations/', ProductRecommendationsView.as_view(), name='api-product-recommendations'),
    path('orders/', views.OrderListCreateView.as_view(), name='api-orders'),
    path('orders/<int:order_id>/', views.OrderDetailView.as_view(), name='api-order-detail'),
    path('shipment/<str:tracking_number>/track/', views.ShipmentTrackingView.as_view(), name='api-shipment-track'),
    path('cart/', views.CartView.as_view(), name='api-cart'),
    path('cart/<int:item_id>/', views.CartView.as_view(), name='api-cart-item'),
    path('checkout/', views.CheckoutView.as_view(), name='api-checkout'),

    # ── Analytics ─────────────────────────────────────────────────────────────
    path('analytics/product-view/', product_view_track, name='api-analytics-product-view'),
    path('analytics/dashboard-kpis/', analytics_dashboard_kpis, name='api-analytics-dashboard-kpis'),
    path('analytics/sales-trend/', SalesTrendView.as_view(), name='api-analytics-sales-trend'),
    path('analytics/top-products/', TopProductsView.as_view(), name='api-analytics-top-products'),
    path('analytics/monthly-sales/', MonthlySalesView.as_view(), name='api-analytics-monthly-sales'),
    path('analytics/product-performance/', ProductPerformanceView.as_view(), name='api-analytics-product-performance'),
    path('analytics/total-revenue/', TotalRevenueView.as_view(), name='api-analytics-total-revenue'),
    path('analytics/revenue-per-user/', RevenuePerUserView.as_view(), name='api-analytics-revenue-per-user'),
    path('analytics/revenue-per-vendor/', RevenuePerVendorView.as_view(), name='api-analytics-revenue-per-vendor'),
    path('admin/analytics-dashboard/', analytics_dashboard, name='admin-analytics-dashboard'),


    # ── Flutterwave ───────────────────────────────────────────────────────────
    path('flutterwave/initialize/', flutterwave_initialize, name='api-flutterwave-initialize'),
    path('flutterwave/webhook/', flutterwave_webhook, name='api-flutterwave-webhook'),

    # ── Platform admin API ────────────────────────────────────────────────────
    path('admin/me/', admin_api.AdminMeView.as_view(), name='api-admin-me'),
    path('admin/me/avatar/', admin_api.AdminAvatarView.as_view(), name='api-admin-avatar'),
    path('admin/dashboard/', admin_api.AdminDashboardView.as_view(), name='api-admin-dashboard'),
    path('admin/products/', admin_api.AdminProductListCreateView.as_view(), name='api-admin-products'),
    path('admin/products/<int:product_id>/', admin_api.AdminProductDetailView.as_view(), name='api-admin-product-detail'),
    path('admin/categories/', admin_api.AdminCategoryListCreateView.as_view(), name='api-admin-categories'),
    path('admin/orders/', admin_api.AdminOrderListView.as_view(), name='api-admin-orders'),
    path('admin/orders/<int:order_id>/status/', admin_api.AdminOrderStatusView.as_view(), name='api-admin-order-status'),
    path('admin/orders/<int:order_id>/invoice/', admin_api.AdminInvoiceView.as_view(), name='api-admin-order-invoice'),
    path('admin/customers/', admin_api.AdminCustomerListView.as_view(), name='api-admin-customers'),
    path('admin/customers/<int:user_id>/status/', admin_api.AdminCustomerStatusView.as_view(), name='api-admin-customer-status'),
    path('admin/customers/<int:user_id>/orders/', admin_api.AdminCustomerOrdersView.as_view(), name='api-admin-customer-orders'),
    path('admin/customers/<int:user_id>/', admin_api.AdminCustomerDeleteView.as_view(), name='api-admin-customer-delete'),
    path('admin/vendors/', admin_api.AdminVendorHistoryListView.as_view(), name='api-admin-vendors'),
    path('admin/vendors/pending/', admin_api.AdminPendingVendorListView.as_view(), name='api-admin-pending-vendors'),
    path('admin/vendors/<int:vendor_id>/verification/', admin_api.AdminVendorVerificationActionView.as_view(), name='api-admin-vendor-verification'),
    path('admin/inventory/', admin_api.AdminInventoryView.as_view(), name='api-admin-inventory'),
    path('admin/inventory/export/', admin_api.AdminInventoryExportView.as_view(), name='api-admin-inventory-export'),
    path('admin/inventory/import/', admin_api.AdminInventoryImportView.as_view(), name='api-admin-inventory-import'),
    path('admin/reports/', admin_api.AdminReportsView.as_view(), name='api-admin-reports'),
    path('admin/settings/', admin_api.AdminSettingsView.as_view(), name='api-admin-settings'),
    path('admin/transactions/', admin_api.AdminTransactionsView.as_view(), name='api-admin-transactions'),
    path('admin/transactions/<int:order_id>/action/', admin_api.AdminTransactionActionView.as_view(), name='api-admin-transaction-action'),

    # ── Customer dashboard API ────────────────────────────────────────────────
    path('customer/dashboard/',           customer_api.CustomerDashboardView.as_view(),         name='api-customer-dashboard'),
    path('customer/orders/',              customer_api.CustomerOrderListView.as_view(),          name='api-customer-orders'),
    path('customer/orders/<int:order_id>/', customer_api.CustomerOrderDetailView.as_view(),     name='api-customer-order-detail'),
    path('customer/orders/<int:order_id>/invoice/', customer_api.CustomerOrderInvoiceView.as_view(), name='api-customer-order-invoice'),
    path('customer/wishlist/',            customer_api.CustomerWishlistView.as_view(),           name='api-customer-wishlist'),
    path('customer/wishlist/<int:item_id>/', customer_api.CustomerWishlistItemView.as_view(),   name='api-customer-wishlist-item'),
    path('customer/wallet/',              customer_api.CustomerWalletView.as_view(),             name='api-customer-wallet'),
    path('customer/notifications/',       customer_api.CustomerNotificationsView.as_view(),     name='api-customer-notifications'),
    path('customer/profile/',             customer_api.CustomerProfileView.as_view(),           name='api-customer-profile'),
    path('customer/profile/avatar/',      customer_api.CustomerAvatarView.as_view(),            name='api-customer-avatar'),
    path('customer/profile/password/',    customer_api.CustomerChangePasswordView.as_view(),    name='api-customer-change-password'),
    path('customer/profile/delete/',      customer_api.CustomerDeleteAccountView.as_view(),     name='api-customer-delete-account'),
    path('customer/addresses/',           customer_api.CustomerAddressListCreateView.as_view(), name='api-customer-addresses'),
    path('customer/addresses/<int:address_id>/', customer_api.CustomerAddressDetailView.as_view(), name='api-customer-address-detail'),
    path('customer/reviews/',             customer_api.CustomerReviewListCreateView.as_view(),  name='api-customer-reviews'),
    path('customer/reviews/<int:review_id>/', customer_api.CustomerReviewDetailView.as_view(), name='api-customer-review-detail'),

    # ── Vendor dashboard API ──────────────────────────────────────────────────
    path('vendor/status/', vendor_api.VendorAccountStatusView.as_view(), name='api-vendor-status'),
    path('vendor/dashboard/', vendor_api.VendorDashboardView.as_view(), name='api-vendor-dashboard'),
    path('vendor/profile/',             vendor_api.VendorProfileView.as_view(),           name='api-vendor-profile'),
    path('vendor/profile/avatar/',      vendor_api.VendorAvatarView.as_view(),            name='api-vendor-avatar'),
    path('vendor/products/', vendor_api.VendorProductListCreateView.as_view(), name='api-vendor-products'),
    path('vendor/products/import/', vendor_api.VendorProductBulkImportView.as_view(), name='api-vendor-products-import'),
    path('vendor/products/<int:product_id>/', vendor_api.VendorProductDetailView.as_view(), name='api-vendor-product-detail'),
    path('vendor/orders/', vendor_api.VendorOrderListView.as_view(), name='api-vendor-orders'),
    path('vendor/orders/<int:vendor_order_id>/status/', vendor_api.VendorOrderStatusView.as_view(), name='api-vendor-order-status'),
    path('vendor/orders/<int:vendor_order_id>/payment-action/', vendor_api.VendorPaymentConfirmView.as_view(), name='api-vendor-order-payment-action'),
    path('vendor/orders/<int:vendor_order_id>/invoice/', vendor_api.VendorInvoiceView.as_view(), name='api-vendor-order-invoice'),
    path('vendor/payouts/', vendor_api.VendorPayoutListCreateView.as_view(), name='api-vendor-payouts'),
    path('vendor/notifications/', vendor_api.VendorNotificationListView.as_view(), name='api-vendor-notifications'),
    path('vendor/notifications/mark-all-read/', vendor_api.VendorNotificationMarkAllReadView.as_view(), name='api-vendor-notifications-mark-all-read'),
    path('vendor/notifications/clear/', vendor_api.VendorNotificationClearView.as_view(), name='api-vendor-notifications-clear'),
    path('vendor/notifications/<int:notification_id>/read/', vendor_api.VendorNotificationMarkReadView.as_view(), name='api-vendor-notification-read'),
    path('vendor/earnings/', vendor_api.VendorEarningsSummaryView.as_view(), name='api-vendor-earnings'),

    # ── Refunds ───────────────────────────────────────────────────────────────────
    path('refunds/request/',                  RefundRequestView.as_view(),           name='api-refund-request'),
    path('refunds/list/',                     RefundListView.as_view(),              name='api-refund-list'),
    path('refunds/vendor-action/<int:refund_id>/', RefundVendorActionView.as_view(), name='api-refund-vendor-action'),
    path('refunds/admin-action/<int:refund_id>/',  RefundAdminActionView.as_view(),  name='api-refund-admin-action'),
    path('refunds/reports/',                  RefundReportsView.as_view(),           name='api-refund-reports'),

    # ── Vendor Management (admin) ────────────────────────────────────────────────────────────────
    path('admin/vendor-management/',                    AdminVendorManagementListView.as_view(),   name='api-admin-vendor-management'),
    path('admin/vendor-management/<int:vendor_id>/',    AdminVendorManagementDetailView.as_view(), name='api-admin-vendor-management-detail'),
    path('admin/vendor-management/<int:vendor_id>/action/', AdminVendorActionView.as_view(),       name='api-admin-vendor-action'),
    path('admin/vendor-analytics/',                     AdminVendorAnalyticsView.as_view(),        name='api-admin-vendor-analytics'),

    # ── Refund Management (admin) ────────────────────────────────────────────────────────────────
    path('admin/refunds/',                    AdminRefundListView.as_view(),   name='api-admin-refunds'),
    path('admin/refunds/<int:refund_id>/action/', AdminRefundActionView.as_view(), name='api-admin-refund-action'),
    path('admin/refunds/reports/',            AdminRefundReportsView.as_view(), name='api-admin-refund-reports'),
]
