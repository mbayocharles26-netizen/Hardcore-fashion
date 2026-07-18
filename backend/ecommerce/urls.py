from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework_simplejwt.views import TokenRefreshView

from store.jwt_views import UsernameOrEmailTokenObtainPairView

# NOTE: Custom token view replaces TokenObtainPairView to support username OR email logins.

urlpatterns = [
    path('superadmin/', admin.site.urls),
    path('api/', include('store.urls')),
    path('api/token/', UsernameOrEmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include('store.template_urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()
