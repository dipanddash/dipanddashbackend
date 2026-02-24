from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db import models
from django.utils.crypto import get_random_string
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
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
    StaffProfileSerializer,
    StaffCreateSerializer,
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
    StaffProfile,
)


class AdminBaseViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


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
    permission_classes = [IsSuperUser]


class AdminUserCouponUsageViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsSuperUser]
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


class AdminStaffViewSet(viewsets.ViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser, IsSuperUser]

    def list(self, request):
        queryset = (
            StaffProfile.objects.select_related("user")
            .filter(user__is_staff=True, user__is_superuser=False)
            .order_by("-created_at")
        )
        serializer = StaffProfileSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data["email"].strip().lower()
        mobile = data["mobile"].strip()
        name = data["name"].strip()

        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "A user with this email already exists."}, status=400)

        if StaffProfile.objects.filter(mobile=mobile).exists():
            return Response({"error": "A staff member with this mobile already exists."}, status=400)

        base_username = email.split("@")[0]
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{suffix}"
            suffix += 1

        generated_password = get_random_string(length=10)
        first_name, _, last_name = name.partition(" ")

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=generated_password,
                    first_name=first_name,
                    last_name=last_name.strip(),
                    is_staff=True,
                    is_superuser=False,
                    is_active=True,
                )
                staff = StaffProfile.objects.create(user=user, mobile=mobile)
        except IntegrityError:
            return Response({"error": "Could not create staff account. Please try again."}, status=400)

        output = StaffProfileSerializer(staff).data
        output["generated_password"] = generated_password
        return Response(output, status=201)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        try:
            staff = StaffProfile.objects.select_related("user").get(pk=pk, user__is_superuser=False)
        except StaffProfile.DoesNotExist:
            return Response({"error": "Staff not found."}, status=404)

        generated_password = get_random_string(length=10)
        staff.user.set_password(generated_password)
        staff.user.save(update_fields=["password"])
        staff.force_password_change = True
        staff.save(update_fields=["force_password_change"])

        return Response({
            "message": "Staff password reset successfully.",
            "generated_password": generated_password,
            "staff_id": staff.user.id,
        })

    def partial_update(self, request, pk=None):
        try:
            staff = StaffProfile.objects.select_related("user").get(pk=pk, user__is_superuser=False)
        except StaffProfile.DoesNotExist:
            return Response({"error": "Staff not found."}, status=404)

        name = request.data.get("name")
        mobile = request.data.get("mobile")
        is_active = request.data.get("is_active")

        if mobile is not None:
            mobile = str(mobile).strip()
            if StaffProfile.objects.exclude(pk=staff.pk).filter(mobile=mobile).exists():
                return Response({"error": "A staff member with this mobile already exists."}, status=400)
            staff.mobile = mobile
            staff.save(update_fields=["mobile"])

        if name is not None:
            name = str(name).strip()
            first_name, _, last_name = name.partition(" ")
            staff.user.first_name = first_name
            staff.user.last_name = last_name.strip()
            staff.user.save(update_fields=["first_name", "last_name"])

        if is_active is not None:
            if isinstance(is_active, str):
                is_active = is_active.strip().lower() in {"1", "true", "yes", "on"}
            else:
                is_active = bool(is_active)
            staff.user.is_active = is_active
            staff.user.save(update_fields=["is_active"])

        return Response(StaffProfileSerializer(staff).data)


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def admin_csrf(request):
    return Response({"csrfToken": get_token(request)})


@ensure_csrf_cookie
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def admin_login(request):
    identifier = request.data.get("username") or request.data.get("email")
    password = request.data.get("password")

    if not identifier or not password:
        return Response({"error": "Email/username and password are required."}, status=400)

    identifier = str(identifier).strip()
    username_for_auth = identifier
    if "@" in identifier:
        user_by_email = User.objects.filter(email__iexact=identifier).first()
        if user_by_email:
            username_for_auth = user_by_email.username

    user = authenticate(request, username=username_for_auth, password=password)
    if not user or not user.is_staff:
        return Response({"error": "Invalid credentials or not an admin user."}, status=401)

    login(request, user)
    force_password_change = False
    if user.is_staff and not user.is_superuser:
        staff_profile = StaffProfile.objects.filter(user=user).first()
        force_password_change = bool(staff_profile and staff_profile.force_password_change)

    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "must_change_password": force_password_change,
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
    force_password_change = False
    if user.is_staff and not user.is_superuser:
        staff_profile = StaffProfile.objects.filter(user=user).first()
        force_password_change = bool(staff_profile and staff_profile.force_password_change)

    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "must_change_password": force_password_change,
    })


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([permissions.IsAdminUser])
def admin_change_password(request):
    current_password = request.data.get("current_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not current_password or not new_password:
        return Response({"error": "Current and new password are required."}, status=400)
    if len(str(new_password)) < 8:
        return Response({"error": "New password must be at least 8 characters."}, status=400)
    if confirm_password is not None and new_password != confirm_password:
        return Response({"error": "New password and confirm password do not match."}, status=400)
    if not request.user.check_password(current_password):
        return Response({"error": "Current password is incorrect."}, status=400)

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])

    if request.user.is_staff and not request.user.is_superuser:
        staff_profile = StaffProfile.objects.filter(user=request.user).first()
        if staff_profile and staff_profile.force_password_change:
            staff_profile.force_password_change = False
            staff_profile.save(update_fields=["force_password_change"])

    login(request, request.user)
    return Response({"message": "Password changed successfully."})


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

