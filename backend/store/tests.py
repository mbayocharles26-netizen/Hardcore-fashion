from datetime import date, timedelta
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    AdminProfile, Cart, CartItem, Category, Order, OrderItem, Product, Shipment, Vendor,
    VendorVerification,
)


class VendorAccountStatusViewTests(APITestCase):
    def test_customer_has_no_vendor_account(self):
        user = User.objects.create_user(username='customer', password='StrongPass!1')
        self.client.force_authenticate(user=user)

        response = self.client.get('/api/vendor/status/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'is_vendor': False, 'status': None})

    def test_pending_vendor_status_is_visible_without_dashboard_access(self):
        user = User.objects.create_user(username='vendor', password='StrongPass!1')
        Vendor.objects.create(user=user, store_name='Vendor Store', status=Vendor.STATUS_PENDING)
        self.client.force_authenticate(user=user)

        response = self.client.get('/api/vendor/status/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'is_vendor': True, 'status': Vendor.STATUS_PENDING})

    def test_verify_vendor_proxy_is_registered_for_the_admin_sidebar(self):
        self.assertIn(VendorVerification, admin.site._registry)


class VendorVerificationAdminTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='StrongPass!1',
        )
        self.vendor_user = User.objects.create_user(
            username='pending-vendor', email='vendor@example.com', password='StrongPass!1',
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            store_name='Pending Store',
            status=Vendor.STATUS_PENDING,
        )
        self.client.force_login(self.admin_user)

    def test_sidebar_review_queue_approves_vendor_and_writes_audit_log(self):
        response = self.client.post(
            reverse('admin:store_vendorverification_changelist'),
            {'vendor_action': f'approve-{self.vendor.id}'},
            follow=True,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.vendor.refresh_from_db()
        self.vendor_user.refresh_from_db()
        self.assertEqual(self.vendor.status, Vendor.STATUS_APPROVED)
        self.assertTrue(self.vendor_user.is_active)
        self.assertTrue(LogEntry.objects.filter(
            user_id=self.admin_user.id,
            object_id=str(self.vendor.id),
        ).exists())


class VendorVerificationDashboardApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='platform-admin', password='StrongPass!1')
        AdminProfile.objects.create(user=self.admin_user, role=AdminProfile.ROLE_SUPER_ADMIN)
        self.vendor_user = User.objects.create_user(username='dashboard-vendor', password='StrongPass!1')
        self.vendor = Vendor.objects.create(user=self.vendor_user, store_name='Dashboard Store')
        self.client.force_authenticate(user=self.admin_user)

    def test_dashboard_lists_and_approves_pending_vendor(self):
        list_response = self.client.get('/api/admin/vendors/')
        action_response = self.client.patch(
            f'/api/admin/vendors/{self.vendor.id}/verification/',
            {'action': 'approve'},
            format='json',
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]['store_name'], 'Dashboard Store')
        self.assertEqual(action_response.status_code, status.HTTP_200_OK)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.status, Vendor.STATUS_APPROVED)
        history_response = self.client.get('/api/admin/vendors/')
        self.assertEqual(history_response.data[0]['status'], Vendor.STATUS_APPROVED)

    def test_dashboard_can_reject_vendor_and_non_super_admin_is_denied(self):
        action_response = self.client.patch(
            f'/api/admin/vendors/{self.vendor.id}/verification/',
            {'action': 'reject'},
            format='json',
        )

        self.assertEqual(action_response.status_code, status.HTTP_200_OK)
        self.vendor.refresh_from_db()
        self.vendor_user.refresh_from_db()
        self.assertEqual(self.vendor.status, Vendor.STATUS_REJECTED)
        self.assertFalse(self.vendor_user.is_active)

        manager = User.objects.create_user(username='product-manager', password='StrongPass!1')
        AdminProfile.objects.create(user=manager, role=AdminProfile.ROLE_PRODUCT_MANAGER)
        self.client.force_authenticate(user=manager)
        denied_response = self.client.get('/api/admin/vendors/pending/')
        self.assertEqual(denied_response.status_code, status.HTTP_403_FORBIDDEN)


class ShipmentTrackingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='shopper', password='StrongPass!1')
        self.order = Order.objects.create(
            user=self.user,
            customer_name='Shopper',
            customer_email='shopper@example.com',
            total_price='2500.00',
            status='processing',
        )

    def test_shipment_generates_a_unique_tracking_number(self):
        shipment = Shipment.objects.create(order=self.order)

        self.assertTrue(shipment.tracking_number.startswith('HFS-'))
        self.assertEqual(len(shipment.tracking_number), 20)

    def test_tracking_endpoint_returns_customer_safe_shipment_data(self):
        shipment = Shipment.objects.create(
            order=self.order,
            status=Shipment.STATUS_IN_TRANSIT,
            estimated_arrival=date(2026, 8, 1),
            current_location='Kigali distribution centre',
        )

        response = self.client.get(f'/api/shipment/{shipment.tracking_number}/track/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tracking_number'], shipment.tracking_number)
        self.assertEqual(response.data['status'], Shipment.STATUS_IN_TRANSIT)
        self.assertEqual(response.data['estimated_arrival'], '2026-08-01')
        self.assertEqual(response.data['current_location'], 'Kigali distribution centre')
        self.assertIn('updated_at', response.data)

    def test_successful_payment_webhook_creates_shipment(self):
        payload = {
            'data': {
                'tx_ref': f'order_{self.order.id}_payment',
                'status': 'successful',
                'transaction_id': 'flw-transaction-123',
            },
        }

        with patch('store.flutterwave_views.verify_webhook_signature', return_value=True):
            response = self.client.post(
                '/api/flutterwave/webhook/',
                data=json.dumps(payload),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')
        self.assertEqual(self.order.flutterwave_transaction_id, 'flw-transaction-123')
        self.assertTrue(Shipment.objects.filter(order=self.order, tracking_number__startswith='HFS-').exists())

    def test_order_detail_includes_shipment_for_its_owner(self):
        shipment = Shipment.objects.create(order=self.order)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f'/api/orders/{self.order.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['shipment']['tracking_number'], shipment.tracking_number)


class PersistentCartTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cart-customer', email='cart@example.com', password='StrongPass!1',
        )
        self.category = Category.objects.create(name='Cart Test Category', slug='cart-test-category')
        self.product_a = Product.objects.create(
            category=self.category,
            name='Guest Cart Product', slug='guest-cart-product', description='Guest cart test product',
            price='100.00', stock=10,
        )
        self.product_b = Product.objects.create(
            category=self.category,
            name='Account Cart Product', slug='account-cart-product', description='Account cart test product',
            price='200.00', stock=10,
        )

    def test_guest_can_add_and_retrieve_a_session_cart(self):
        add_response = self.client.post(
            '/api/cart/', {'product_id': self.product_a.id, 'quantity': 2}, format='json',
        )
        cart_response = self.client.get('/api/cart/')

        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(cart_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cart_response.data['items'][0]['product'], self.product_a.id)
        self.assertEqual(cart_response.data['items'][0]['quantity'], 2)
        self.assertTrue(Cart.objects.filter(session_key=self.client.session.session_key).exists())

    def test_login_merges_the_guest_cart_into_the_account_cart(self):
        self.client.post(
            '/api/cart/', {'product_id': self.product_a.id, 'quantity': 2}, format='json',
        )
        guest_session_key = self.client.session.session_key

        account_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=account_cart, product=self.product_a, quantity=1)
        CartItem.objects.create(cart=account_cart, product=self.product_b, quantity=1)

        login_response = self.client.post(
            '/api/token/', {'username': 'cart-customer', 'password': 'StrongPass!1'}, format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

        cart_response = self.client.get('/api/cart/')
        merged_items = {item['product']: item['quantity'] for item in cart_response.data['items']}

        self.assertEqual(merged_items, {self.product_a.id: 3, self.product_b.id: 1})
        self.assertFalse(Cart.objects.filter(session_key=guest_session_key).exists())

    def test_account_cart_survives_an_authenticated_session_ending(self):
        account_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=account_cart, product=self.product_a, quantity=2)

        self.client.force_authenticate(user=self.user)
        signed_in_response = self.client.get('/api/cart/')
        self.client.force_authenticate(user=None)
        signed_out_response = self.client.get('/api/cart/')
        self.client.force_authenticate(user=self.user)
        signed_back_in_response = self.client.get('/api/cart/')

        self.assertEqual(signed_in_response.data['items'][0]['quantity'], 2)
        self.assertEqual(signed_out_response.data['items'], [])
        self.assertEqual(signed_back_in_response.data['items'][0]['quantity'], 2)


class AnalyticsApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='analytics-admin', password='StrongPass!1')
        AdminProfile.objects.create(user=self.admin_user, role=AdminProfile.ROLE_SUPER_ADMIN)
        self.customer = User.objects.create_user(username='analytics-customer', password='StrongPass!1')
        category = Category.objects.create(name='Analytics', slug='analytics')
        self.product = Product.objects.create(
            category=category,
            name='Analytics T-Shirt',
            slug='analytics-t-shirt',
            description='Test product',
            price='1000.00',
            stock=20,
        )
        paid_order = Order.objects.create(
            user=self.customer,
            customer_name='Customer',
            total_price='3000.00',
            status='processing',
        )
        Order.objects.filter(pk=paid_order.pk).update(order_date=timezone.now() - timedelta(days=7))
        OrderItem.objects.create(order=paid_order, product=self.product, quantity=3, price='1000.00')

        cancelled_order = Order.objects.create(
            user=self.customer,
            customer_name='Customer',
            total_price='9000.00',
            status='cancelled',
        )
        OrderItem.objects.create(order=cancelled_order, product=self.product, quantity=9, price='1000.00')
        self.client.force_authenticate(user=self.admin_user)

    def test_sales_endpoints_return_completed_sales_only(self):
        response = self.client.get('/api/analytics/sales-trend/?range=monthly&months=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['range'], 'monthly')
        self.assertEqual(len(response.data['labels']), 2)
        self.assertEqual(sum(response.data['revenue']), 3000.0)
        self.assertEqual(sum(response.data['orders']), 1)

        monthly_response = self.client.get('/api/analytics/monthly-sales/?months=2')
        self.assertEqual(monthly_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sum(monthly_response.data['revenue']), 3000.0)

    def test_product_performance_excludes_cancelled_orders(self):
        response = self.client.get('/api/analytics/product-performance/?days=30&limit=5')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metric'], 'revenue')
        self.assertEqual(response.data['items'][0]['name'], 'Analytics T-Shirt')
        self.assertEqual(response.data['items'][0]['quantity'], 3)
        self.assertEqual(response.data['items'][0]['revenue'], 3000.0)

    def test_existing_admin_reports_and_dashboard_endpoints_are_aggregate_safe(self):
        reports_response = self.client.get('/api/admin/reports/')
        dashboard_response = self.client.get('/api/admin/dashboard/')

        self.assertEqual(reports_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sum(row['revenue'] for row in reports_response.data['monthly_sales']), 3000.0)
        self.assertEqual(reports_response.data['product_performance'][0]['quantity'], 3)
        self.assertEqual(reports_response.data['product_performance'][0]['revenue'], 3000.0)
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.data['top_products'][0]['quantity'], 3)

    def test_analytics_endpoints_require_a_platform_admin(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get('/api/analytics/top-products/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AnalyticsTemplateTests(APITestCase):
    def test_dashboard_and_reports_pages_render_the_chart_shell(self):
        dashboard = self.client.get('/dashboard/')
        reports = self.client.get('/reports/')

        self.assertEqual(dashboard.status_code, status.HTTP_200_OK)
        self.assertEqual(reports.status_code, status.HTTP_200_OK)
        self.assertContains(dashboard, 'data-analytics-dashboard')
        self.assertContains(reports, 'Monthly Sales')
