from django.conf import settings
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.http import FileResponse, HttpResponse
import os

from django.db.models import Q
from .models import Product, Category
from .views import checkout_view, process_order, order_confirmation, login_redirect


def index(request):
    featured = (
        Product.objects.filter(is_active=True, is_featured=True)
        .select_related('category')[:8]
    )
    categories = Category.objects.all()
    return render(request, 'index.html', {
        'featured': featured,
        'categories': categories,
    })


def products(request):
    qs = Product.objects.select_related('category').filter(is_active=True)
    categories = Category.objects.all()

    search = request.GET.get('search', '').strip()
    category_slug = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', '')

    if search:
        # Split into individual words so "blue shirt" matches both terms
        terms = [t for t in search.split() if t]
        for term in terms:
            qs = qs.filter(
                Q(name__icontains=term) |
                Q(description__icontains=term) |
                Q(category__name__icontains=term) |
                Q(attributes__icontains=term)
            )
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if sort == 'price_asc':
        qs = qs.order_by('price')
    elif sort == 'price_desc':
        qs = qs.order_by('-price')
    elif sort == 'name':
        qs = qs.order_by('name')

    return render(request, 'products.html', {
        'products': qs,
        'categories': categories,
        'search': search,
        'active_category': category_slug,
        'sort': sort,
        'total_count': qs.count(),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category').filter(is_active=True),
        slug=slug,
    )
    related = (
        Product.objects.filter(
            category=product.category,
            is_active=True,
        )
        .exclude(id=product.id)
        .order_by('?')[:3]
    )
    return render(request, 'product_detail.html', {
        'product': product,
        'related': related,
    })


def cart(request):
    return render(request, 'cart.html')


def checkout(request):
    return checkout_view(request)


def login_view(request):
    return render(request, 'login.html')


def register_view(request):
    return render(request, 'register.html')


def forgot_password_view(request):
    return render(request, 'forgot_password.html')


from .dashboard_access import get_role
from .jwt_auth import get_user_from_jwt_cookie_or_header


def _jwt_user(request):
    """Resolve user from JWT Bearer token (Authorization header or cookie)."""
    return get_user_from_jwt_cookie_or_header(request)


def admin_dashboard_view(request):
    user = _jwt_user(request)
    if not user or get_role(user) != 'admin':
        return render(request, '403.html', status=403)
    return render(request, 'admin_panel.html')


def admin_panel_view(request):
    # Backwards-compatible alias — same JWT-aware guard
    user = _jwt_user(request)
    if not user or get_role(user) != 'admin':
        return render(request, '403.html', status=403)
    return render(request, 'admin_panel.html')


def vendor_dashboard_view(request):
    return render(request, 'vendor_dashboard.html')


def customer_dashboard_view(request):
    return render(request, 'customer_dashboard.html')


def reports_view(request):
    return render(request, 'reports.html')


def vendor_refunds_view(request):
    # Redirect to the refunds tab inside the vendor dashboard
    from django.http import HttpResponseRedirect
    return HttpResponseRedirect('/vendor-dashboard/?tab=refunds')


def track_shipment_view(request):
    return render(request, 'track_shipment.html')


def service_worker(request):
    sw_path = os.path.join(
        settings.BASE_DIR,
        'frontend',
        'static',
        'service-worker.js',
    )
    with open(sw_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


def favicon(request):
    icon_path = os.path.join(
        settings.BASE_DIR,
        'frontend',
        'static',
        'images',
        'icon-192.png',
    )
    return FileResponse(open(icon_path, 'rb'), content_type='image/png')


def offline(request):
    return render(request, 'offline.html')


urlpatterns = [
    path('', index, name='index'),
    path('products/', products, name='products'),
    path('products/<slug:slug>/', product_detail, name='product_detail'),
    path('cart/', cart, name='cart'),
    path('checkout/', checkout, name='checkout'),
    path('order/confirmation/<int:order_id>/', order_confirmation, name='order_confirmation'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),

    # Role-based dashboards
    path('admin/dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin-panel/', admin_panel_view, name='admin_panel'),

    path('vendor-dashboard/', vendor_dashboard_view, name='vendor_dashboard'),
    path('customer-dashboard/', customer_dashboard_view, name='customer_dashboard'),

    path('redirect/', login_redirect, name='login_redirect'),

    # Legacy aliases

    path('dashboard/', lambda request: render(request, 'dashboard.html'), name='dashboard'),
    path('vendor/', vendor_dashboard_view, name='vendor_dashboard_legacy'),
    path('customer/', customer_dashboard_view, name='customer_dashboard_legacy'),


    path('reports/', reports_view, name='reports'),
    path('vendor-refunds/', vendor_refunds_view, name='vendor_refunds'),
    path('track-shipment/', track_shipment_view, name='track_shipment'),
    path('sw.js', service_worker, name='service_worker'),
    path('favicon.ico', favicon, name='favicon'),
    path('offline/', offline, name='offline'),
]

