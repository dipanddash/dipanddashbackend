from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import foodbackend.admin_urls

urlpatterns = [
    path("admin/", include(foodbackend.admin_urls)),
    path("dj-admin/", admin.site.urls),

    # 🔐 Auth / OTP APIs
    path("api/", include("foodbackend.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)