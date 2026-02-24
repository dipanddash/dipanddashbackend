from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .admin_api import (
    admin_csrf,
    admin_login,
    admin_logout,
    admin_me,
    admin_stats,
    AdminAddressViewSet,
    AdminAppVersionViewSet,
    AdminCategoryViewSet,
    AdminCouponViewSet,
    AdminItemViewSet,
    AdminOrderItemReviewViewSet,
    AdminOrderItemViewSet,
    AdminOrderViewSet,
    AdminOrderReviewViewSet,
    AdminPushTokenViewSet,
    AdminUserCouponUsageViewSet,
    AdminUserViewSet,
    AdminSupportTicketViewSet,
    AdminSupportMessageViewSet,
)
from .views import (
    send_otp,
    verify_otp,
    get_user_profile,
    send_rider_otp,
    verify_rider_otp,
    get_rider_orders,
    get_ready_for_pickup_orders,
    accept_order_for_pickup,
    home_data,
    get_combos,
    get_cart,
    add_to_cart,
    update_cart_item,
    remove_from_cart,
    get_addresses,
    create_address,
    delete_address,
    checkout,
    update_order_status,
    update_rider_location,
    update_rider_location_simple,
    mark_order_delivered,
    get_orders,
    get_order_detail,
    get_active_order,
    order_review,
    register_push_token,
    unregister_push_token,
    check_app_version,
    create_razorpay_order,
    verify_razorpay_payment,
    available_coupons,
    validate_coupon,
    apply_coupon,
    create_support_ticket,
    get_support_tickets,
    support_chat,
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

urlpatterns = [
    # Admin API (session-based)
    path("admin/csrf/", admin_csrf, name="admin_csrf"),
    path("admin/login/", admin_login, name="admin_login"),
    path("admin/logout/", admin_logout, name="admin_logout"),
    path("admin/me/", admin_me, name="admin_me"),
    path("admin/stats/", admin_stats, name="admin_stats"),
    path("admin/", include(admin_router.urls)),

    # Authentication
    path("send-otp/", send_otp, name="send_otp"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("me/", get_user_profile, name="get_user_profile"),  # Get current user profile

    # Rider Authentication
    path("rider/send-otp/", send_rider_otp, name="send_rider_otp"),
    path("rider/verify-otp/", verify_rider_otp, name="verify_rider_otp"),

    # Rider Orders
    path("rider/orders/", get_rider_orders, name="get_rider_orders"),
    path("rider/orders/ready/", get_ready_for_pickup_orders, name="get_ready_for_pickup_orders"),
    path("rider/orders/accept/", accept_order_for_pickup, name="accept_order_for_pickup"),
    
    # Home & Items
    path("home/", home_data, name="home_data"),
    path("combos/", get_combos, name="get_combos"),
    
    # Cart Operations
    path("cart/", get_cart, name="get_cart"),
    path("cart/add/", add_to_cart, name="add_to_cart"),
    path("cart/item/<int:cart_item_id>/update/", update_cart_item, name="update_cart_item"),
    path("cart/item/<int:cart_item_id>/remove/", remove_from_cart, name="remove_from_cart"),
    
    # Address Operations
    path("addresses/", get_addresses, name="get_addresses"),
    path("addresses/create/", create_address, name="create_address"),
    path("addresses/<int:address_id>/delete/", delete_address, name="delete_address"),
    
    # Order Operations
    path("checkout/", checkout, name="checkout"),
    path("orders/update-status/", update_order_status, name="update_order_status"),
    path("orders/update-rider-location/", update_rider_location, name="update_rider_location"),
    path("orders/rider-location/", update_rider_location_simple, name="update_rider_location_simple"),
    path("orders/mark-delivered/", mark_order_delivered, name="mark_order_delivered"),
    path("orders/", get_orders, name="get_orders"),
    path("orders/<int:order_id>/", get_order_detail, name="get_order_detail"),
    path("orders/<int:order_id>/review/", order_review, name="order_review"),
    path("orders/active/", get_active_order, name="get_active_order"),
    path("register-push-token/", register_push_token, name="register_push_token"),
    path("unregister-push-token/", unregister_push_token, name="unregister_push_token"),
    path("check-app-version/", check_app_version, name="check_app_version"),
    
    # Razorpay Payment
    path("payment/create-order/", create_razorpay_order, name="create_razorpay_order"),
    path("payment/verify/", verify_razorpay_payment, name="verify_razorpay_payment"),
    
    # Coupons
    path("coupons/", available_coupons, name="available_coupons"),
    path("coupons/validate/", validate_coupon, name="validate_coupon"),
    path("coupons/apply/", apply_coupon, name="apply_coupon"),
    
    # Support Chat
    path("support/tickets/create/", create_support_ticket, name="create_support_ticket"),
    path("support/tickets/", get_support_tickets, name="get_support_tickets"),
    path("support/tickets/<int:ticket_id>/chat/", support_chat, name="support_chat"),
]
