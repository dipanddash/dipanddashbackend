from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import models
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from .admin_serializers import (
    AddressSerializer,
    AppVersionSerializer,
    CategorySerializer,
    CouponSerializer,
    ItemSerializer,
    OrderDetailSerializer,
    OrderItemReviewSerializer,
    OrderItemSerializer,
    OrderReviewSerializer,
    OrderSerializer,
    PushTokenSerializer,
    UserCouponUsageSerializer,
    UserSerializer,
    SupportTicketSerializer,
    SupportMessageSerializer,
)
from .models import (
    Address,
    AppVersion,
    Category,
    Coupon,
    Item,
    Order,
    OrderItemReview,
    OrderItem,
    OrderReview,
    PushToken,
    UserCouponUsage,
    SupportTicket,
    SupportMessage,
)


class AdminBaseViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]


class AdminCategoryViewSet(AdminBaseViewSet):
    queryset = Category.objects.all().order_by("id")
    serializer_class = CategorySerializer


class AdminItemViewSet(AdminBaseViewSet):
    queryset = Item.objects.select_related("category").all().order_by("id")
    serializer_class = ItemSerializer


class AdminOrderViewSet(AdminBaseViewSet):
    queryset = (
        Order.objects.select_related("user", "address", "coupon")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    serializer_class = OrderSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OrderDetailSerializer
        return super().get_serializer_class()


class AdminOrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = OrderItem.objects.select_related("order", "item").all().order_by("-id")
    serializer_class = OrderItemSerializer


class AdminOrderReviewViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = (
        OrderReview.objects.select_related("order", "user")
        .prefetch_related("item_reviews")
        .order_by("-created_at")
    )
    serializer_class = OrderReviewSerializer


class AdminOrderItemReviewViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = OrderItemReview.objects.select_related("review", "order_item").order_by("-created_at")
    serializer_class = OrderItemReviewSerializer


class AdminCouponViewSet(AdminBaseViewSet):
    queryset = Coupon.objects.all().order_by("-created_at")
    serializer_class = CouponSerializer


class AdminUserCouponUsageViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = UserCouponUsage.objects.select_related("user", "coupon", "order").all().order_by("-used_at")
    serializer_class = UserCouponUsageSerializer


class AdminPushTokenViewSet(AdminBaseViewSet):
    queryset = PushToken.objects.select_related("user").all().order_by("-created_at")
    serializer_class = PushTokenSerializer


class AdminAppVersionViewSet(AdminBaseViewSet):
    queryset = AppVersion.objects.all().order_by("-released_at")
    serializer_class = AppVersionSerializer


class AdminUserViewSet(AdminBaseViewSet):
    serializer_class = UserSerializer

    def get_queryset(self):
        role = self.request.query_params.get("role", "all")
        queryset = User.objects.all().order_by("-date_joined")
        if role == "customer":
            return queryset.filter(is_staff=False)
        if role == "staff":
            return queryset.filter(is_staff=True)
        return queryset


class AdminAddressViewSet(AdminBaseViewSet):
    queryset = Address.objects.select_related("user").all().order_by("-created_at")
    serializer_class = AddressSerializer


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def admin_csrf(request):
    return Response({"csrfToken": get_token(request)})


@ensure_csrf_cookie
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def admin_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user or not user.is_staff:
        return Response({"error": "Invalid credentials or not an admin user."}, status=401)

    login(request, user)
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_superuser": user.is_superuser,
    })


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([permissions.IsAdminUser])
def admin_logout(request):
    logout(request)
    return Response({"message": "Logged out"})


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([permissions.IsAdminUser])
def admin_me(request):
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_superuser": user.is_superuser,
    })


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([permissions.IsAdminUser])
def admin_stats(request):
    total_orders = Order.objects.count()
    delivered_orders = Order.objects.filter(status="delivered").count()
    cancelled_orders = Order.objects.filter(status="cancelled").count()
    total_revenue = (
        Order.objects.filter(status="delivered")
        .aggregate(total=models.Sum("total_price"))
        .get("total")
        or 0
    )

    recent_orders = (
        Order.objects.select_related("user")
        .order_by("-created_at")[:5]
    )

    return Response({
        "totals": {
            "orders": total_orders,
            "delivered": delivered_orders,
            "cancelled": cancelled_orders,
            "revenue": float(total_revenue),
        },
        "recent_orders": [
            {
                "id": order.id,
                "user": order.user.username,
                "status": order.status,
                "total": float(order.total_price),
                "created_at": order.created_at.isoformat(),
            }
            for order in recent_orders
        ],
    })


class AdminSupportTicketViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.select_related("user").prefetch_related("messages")
    serializer_class = SupportTicketSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status", "priority", "category"]
    ordering_fields = ["created_at", "priority"]
    ordering = ["-created_at"]


class AdminSupportMessageViewSet(viewsets.ModelViewSet):
    queryset = SupportMessage.objects.select_related("ticket")
    serializer_class = SupportMessageSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["ticket", "sender_type"]
    ordering = ["created_at"]

    def perform_create(self, serializer):
        """Admin sends a message to a support ticket"""
        serializer.save(sender_type="admin")

