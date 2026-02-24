from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .admin_api import (
    admin_csrf,
    admin_login,
    admin_logout,
    admin_me,
    admin_change_password,
    admin_stats,
    AdminAddressViewSet,
    AdminAppVersionViewSet,
    AdminCategoryViewSet,
    AdminCouponViewSet,
    AdminItemViewSet,
    AdminOrderItemReviewViewSet,
    AdminOrderItemViewSet,
    AdminOrderReviewViewSet,
    AdminOrderViewSet,
    AdminPushTokenViewSet,
    AdminSupportMessageViewSet,
    AdminSupportTicketViewSet,
    AdminStaffViewSet,
    AdminUserCouponUsageViewSet,
    AdminUserViewSet,
)

admin_router = DefaultRouter()
admin_router.register(r"categories", AdminCategoryViewSet, basename="admin-categories")
admin_router.register(r"items", AdminItemViewSet, basename="admin-items")
admin_router.register(r"orders", AdminOrderViewSet, basename="admin-orders")
admin_router.register(r"order-items", AdminOrderItemViewSet, basename="admin-order-items")
admin_router.register(r"reviews", AdminOrderReviewViewSet, basename="admin-reviews")
admin_router.register(r"item-reviews", AdminOrderItemReviewViewSet, basename="admin-item-reviews")
admin_router.register(r"coupons", AdminCouponViewSet, basename="admin-coupons")
admin_router.register(r"coupon-usage", AdminUserCouponUsageViewSet, basename="admin-coupon-usage")
admin_router.register(r"push-tokens", AdminPushTokenViewSet, basename="admin-push-tokens")
admin_router.register(r"app-versions", AdminAppVersionViewSet, basename="admin-app-versions")
admin_router.register(r"users", AdminUserViewSet, basename="admin-users")
admin_router.register(r"addresses", AdminAddressViewSet, basename="admin-addresses")
admin_router.register(r"support-tickets", AdminSupportTicketViewSet, basename="admin-support-tickets")
admin_router.register(r"support-messages", AdminSupportMessageViewSet, basename="admin-support-messages")
admin_router.register(r"staff", AdminStaffViewSet, basename="admin-staff")

urlpatterns = [
    path("csrf/", admin_csrf, name="admin_csrf"),
    path("login/", admin_login, name="admin_login"),
    path("logout/", admin_logout, name="admin_logout"),
    path("me/", admin_me, name="admin_me"),
    path("change-password/", admin_change_password, name="admin_change_password"),
    path("stats/", admin_stats, name="admin_stats"),
    path("", include(admin_router.urls)),
]
