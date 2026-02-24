from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    Address,
    AppVersion,
    Category,
    Coupon,
    Item,
    Order,
    OrderItem,
    OrderItemReview,
    OrderReview,
    PushToken,
    UserCouponUsage,
    SupportTicket,
    SupportMessage,
    StaffProfile,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class ItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id",
            "category",
            "category_name",
            "name",
            "price",
            "gst_rate",
            "description",
            "image",
            "image_url",
            "is_available",
            "is_combo",
        )

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class AddressSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Address
        fields = (
            "id",
            "user",
            "user_name",
            "address_type",
            "full_address",
            "city",
            "postal_code",
            "latitude",
            "longitude",
            "is_default",
            "created_at",
        )


class OrderItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "order",
            "item",
            "item_name",
            "quantity",
            "price_at_order",
            "tax_at_order",
        )
        read_only_fields = (
            "order",
            "item",
            "quantity",
            "price_at_order",
            "tax_at_order",
        )


class OrderSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    items_count = serializers.IntegerField(source="items.count", read_only=True)
    address_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "user",
            "user_name",
            "status",
            "subtotal",
            "tax",
            "platform_fee",
            "delivery_charge",
            "coupon",
            "coupon_discount",
            "total_price",
            "delivery_otp",
            "rider_name",
            "rider_mobile",
            "rider_latitude",
            "rider_longitude",
            "rider_location_updated_at",
            "address",
            "address_display",
            "created_at",
            "updated_at",
            "items_count",
        )
        read_only_fields = (
            "subtotal",
            "tax",
            "platform_fee",
            "delivery_charge",
            "coupon",
            "coupon_discount",
            "total_price",
            "delivery_otp",
            "created_at",
            "updated_at",
            "items_count",
        )

    def get_address_display(self, obj):
        if not obj.address:
            return None
        return f"{obj.address.address_type} | {obj.address.city}"


class OrderDetailSerializer(OrderSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    address_details = AddressSerializer(source="address", read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + (
            "items",
            "address_details",
        )


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = "__all__"
        read_only_fields = ("used_count", "created_at", "updated_at")


class UserCouponUsageSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)

    class Meta:
        model = UserCouponUsage
        fields = (
            "id",
            "user",
            "user_name",
            "coupon",
            "coupon_code",
            "order",
            "discount_amount",
            "used_at",
        )
        read_only_fields = fields


class PushTokenSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PushToken
        fields = (
            "id",
            "user",
            "user_name",
            "push_token",
            "device_type",
            "is_active",
            "created_at",
            "updated_at",
        )


class AppVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersion
        fields = "__all__"


class OrderItemReviewSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="review.order.id", read_only=True)

    class Meta:
        model = OrderItemReview
        fields = (
            "id",
            "order_id",
            "item_name",
            "rating",
            "created_at",
        )
        read_only_fields = fields


class OrderReviewSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    item_reviews = OrderItemReviewSerializer(many=True, read_only=True)

    class Meta:
        model = OrderReview
        fields = (
            "id",
            "order",
            "order_id",
            "user",
            "user_name",
            "user_email",
            "delivery_rating",
            "overall_rating",
            "comment",
            "created_at",
            "item_reviews",
        )
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        )


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = (
            "id",
            "ticket",
            "sender_type",
            "message",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "sender_type")


class SupportTicketSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = (
            "id",
            "user",
            "user_name",
            "user_email",
            "category",
            "subject",
            "description",
            "status",
            "priority",
            "messages",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class StaffProfileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    staff_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    force_password_change = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = StaffProfile
        fields = (
            "id",
            "staff_id",
            "name",
            "email",
            "mobile",
            "is_active",
            "force_password_change",
            "date_joined",
            "last_login",
        )

    def get_name(self, obj):
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full_name or obj.user.username


class StaffCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=15)
