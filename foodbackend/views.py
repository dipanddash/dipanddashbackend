from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.conf import settings
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal
from django.utils import timezone
from django.db import models
from django.db.models import Count, Prefetch
import random
import requests
import math
import razorpay
import hmac
import hashlib

from .models import (
    OTP,
    RiderOTP,
    Rider,
    Category,
    Item,
    ComboItem,
    Cart,
    CartItem,
    Address,
    Order,
    OrderItem,
    OrderReview,
    OrderItemReview,
    Coupon,
    UserCouponUsage,
    PushToken,
    AppVersion,
    SupportTicket,
    SupportMessage,
)

PLATFORM_FEE = Decimal("5.00")

RESTAURANT_LAT_DEFAULT = Decimal("12.9697368")
RESTAURANT_LNG_DEFAULT = Decimal("80.2479267")

RAZORPAY_KEY_ID = "rzp_test_SFZXtVKJeXVM11"
RAZORPAY_KEY_SECRET = "QDT11YuAlT45R8OyPrHfCyKY"


def _is_valid_mobile(mobile):
    return bool(mobile) and str(mobile).isdigit() and len(str(mobile)) == 10


def _generate_login_otp():
    return str(random.randint(1000, 9999))


def _send_fast2sms_otp(mobile, otp):
    # Development Mode: Skip SMS and print OTP to console
    dev_mode = getattr(settings, "OTP_DEV_MODE", False)
    if dev_mode:
        print(f"\n{'='*50}")
        print(f"📱 OTP for {mobile}: {otp}")
        print(f"{'='*50}\n")
        return True, None
    
    api_key = getattr(settings, "FAST2SMS_API_KEY", "")
    sender_id = getattr(settings, "FAST2SMS_SENDER_ID", "")
    route = getattr(settings, "FAST2SMS_ROUTE", "dlt")
    template_id = getattr(settings, "FAST2SMS_TEMPLATE_ID", "")
    message_template = getattr(
        settings,
        "FAST2SMS_MESSAGE_TEMPLATE",
        "Your OTP for Dip & Dash is {otp}. Do not share it with anyone.",
    )

    if not api_key or not sender_id:
        return False, "Fast2SMS is not configured"

    params = {
        "route": route,
        "sender_id": sender_id,
        "numbers": str(mobile),
        "flash": "0",
    }

    if str(route).lower() == "dlt":
        if not template_id:
            return False, "Fast2SMS DLT template id is missing"
        # For DLT route, send template_id as the 'message' parameter
        params["message"] = template_id
        params["variables_values"] = str(otp)
    else:
        params["message"] = message_template.format(otp=otp)

    # Add authorization as query parameter (not header)
    params["authorization"] = api_key

    # Debug logging
    print(f"\n🔍 Fast2SMS Request Debug:")
    print(f"   API Key: {api_key[:10]}...{api_key[-10:]} (length: {len(api_key)})")
    print(f"   Sender ID: {sender_id}")
    print(f"   Template ID: {template_id}")
    print(f"   Route: {route}")
    print(f"   Params: {params}\n")

    try:
        response = requests.get(
            "https://www.fast2sms.com/dev/bulkV2",
            params=params,
            timeout=10,
        )
        raw_text = response.text or ""
        data = response.json() if response.content else {}

        if response.status_code != 200:
            print(f"Fast2SMS HTTP {response.status_code}: {raw_text}")
            return False, data.get("message") or f"Fast2SMS error: {response.status_code}"

        if data.get("return") is True or str(data.get("status")).lower() in {"success", "ok"}:
            return True, None

        if raw_text:
            print(f"Fast2SMS response: {raw_text}")
        return False, data.get("message") or "Fast2SMS request failed"
    except Exception as e:
        return False, f"Fast2SMS error: {str(e)}"


def _get_restaurant_coords():
    lat = getattr(settings, "RESTAURANT_LAT", RESTAURANT_LAT_DEFAULT)
    lng = getattr(settings, "RESTAURANT_LNG", RESTAURANT_LNG_DEFAULT)
    return float(lat), float(lng)


def _geocode_address(full_address):
    """Geocode address using Google Geocoding API if coordinates are missing."""
    if not full_address:
        return None, None

    google_api_key = getattr(settings, "GOOGLE_GEOCODING_API_KEY", None)
    if not google_api_key:
        return None, None

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&key={google_api_key}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            location = data["results"][0]["geometry"]["location"]
            return Decimal(str(location["lat"])), Decimal(str(location["lng"]))
    except Exception as e:
        print(f"Geocoding error: {e}")

    return None, None


def _calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula.
    Returns distance in kilometers.
    """
    if not all([lat1, lon1, lat2, lon2]):
        return None
    
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    
    R = 6371  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _calculate_delivery_charge(distance_km):
    """
    Calculate delivery charge based on distance.
    - Within 2 km: Free
    - Above 2 km: ₹10 per km
    """
    if distance_km is None:
        return Decimal("0.00")
    
    distance_km = float(distance_km)
    
    if distance_km <= 2:
        return Decimal("0.00")
    
    # ₹10 per km for distance above 2 km
    charge = (distance_km - 2) * 10
    return Decimal(str(round(charge, 2)))


def _generate_delivery_otp():
    return str(random.randint(1000, 9999))


def _serialize_order_for_rider(order):
    customer_name = order.user.first_name or "Customer"
    customer_mobile = order.user.username
    address = order.address
    items_count = getattr(order, "items_count", None)
    if items_count is None:
        items_count = order.items.count()

    return {
        "id": order.id,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "items_count": items_count,
        "total_price": float(order.total_price),
        "delivery_otp": order.delivery_otp,
        "customer_name": customer_name,
        "customer_mobile": customer_mobile,
        "delivery_address": address.full_address if address else "N/A",
        "delivery_city": address.city if address else None,
        "delivery_postal_code": address.postal_code if address else None,
        "delivery_latitude": float(address.latitude) if address and address.latitude else None,
        "delivery_longitude": float(address.longitude) if address and address.longitude else None,
    }


@api_view(["POST"])
def send_otp(request):
    mobile = request.data.get("mobile")
    if not _is_valid_mobile(mobile):
        return Response({"error": "Valid 10-digit mobile is required"}, status=400)

    otp = _generate_login_otp()

    OTP.objects.filter(mobile=mobile).delete()
    OTP.objects.create(mobile=mobile, otp=otp)

    sent, error = _send_fast2sms_otp(mobile, otp)
    if not sent:
        OTP.objects.filter(mobile=mobile, otp=otp).delete()
        return Response({"error": error}, status=500)

    return Response({"message": "OTP sent"})


@api_view(["POST"])
def verify_otp(request):
    mobile = request.data.get("mobile")
    otp = request.data.get("otp")
    name = request.data.get("name", "Dev User")

    print(f"\n🔍 Verify OTP Request:")
    print(f"   Mobile: {mobile}")
    print(f"   OTP: {otp}")
    print(f"   Name: {name}\n")

    if not _is_valid_mobile(mobile) or not otp:
        print(f"❌ Validation failed: mobile={mobile}, otp={otp}")
        return Response({"error": "Mobile and OTP are required"}, status=400)

    latest = OTP.objects.filter(mobile=mobile).order_by("-created_at").first()
    
    if not latest:
        print(f"❌ No OTP found for mobile: {mobile}")
        return Response({"error": "Invalid OTP"}, status=400)
    
    print(f"   DB OTP: {latest.otp}, Expired: {latest.is_expired()}")
    
    if latest.is_expired():
        print(f"❌ OTP expired for {mobile}")
        return Response({"error": "OTP expired"}, status=400)
    
    if latest.otp != str(otp):
        print(f"❌ OTP mismatch. DB: {latest.otp}, Received: {otp}")
        return Response({"error": "Invalid OTP"}, status=400)

    print(f"✅ OTP verified successfully for {mobile}")

    user, created = User.objects.get_or_create(
        username=mobile,
        defaults={"first_name": name},
    )
    
    # If user already exists, update their name
    if not created and name and name != "Dev User":
        user.first_name = name
        user.save()

    Cart.objects.get_or_create(user=user)

    refresh = RefreshToken.for_user(user)

    return Response({
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "user_id": user.id,
        "name": user.first_name,
        "mobile": user.username,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """Get current user's profile"""
    user = request.user
    return Response({
        "user_id": user.id,
        "name": user.first_name or "User",
        "mobile": user.username,
        "email": user.email or "",
    })


@api_view(["POST"])
def send_rider_otp(request):
    mobile = request.data.get("mobile")
    if not _is_valid_mobile(mobile):
        return Response({"error": "Valid 10-digit mobile is required"}, status=400)

    otp = _generate_login_otp()

    RiderOTP.objects.filter(mobile=mobile).delete()
    RiderOTP.objects.create(mobile=mobile, otp=otp)

    sent, error = _send_fast2sms_otp(mobile, otp)
    if not sent:
        RiderOTP.objects.filter(mobile=mobile, otp=otp).delete()
        return Response({"error": error}, status=500)

    return Response({"message": "OTP sent"})


@api_view(["POST"])
def verify_rider_otp(request):
    mobile = request.data.get("mobile")
    otp = request.data.get("otp")
    name = request.data.get("name", "Dev Rider")

    if not _is_valid_mobile(mobile) or not otp:
        return Response({"error": "Mobile and OTP are required"}, status=400)

    latest = RiderOTP.objects.filter(mobile=mobile).order_by("-created_at").first()
    if not latest or latest.is_expired() or latest.otp != str(otp):
        return Response({"error": "Invalid OTP"}, status=400)

    user, _ = User.objects.get_or_create(
        username=f"rider_{mobile}",
        defaults={"first_name": name},
    )

    rider, _ = Rider.objects.get_or_create(
        mobile=mobile,
        defaults={"user": user},
    )

    refresh = RefreshToken.for_user(user)

    return Response({
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "user_id": user.id,
        "rider_id": rider.id,
        "name": user.first_name,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_rider_orders(request):
    try:
        rider = request.user.rider_profile
    except Rider.DoesNotExist:
        return Response({"error": "Rider profile not found"}, status=404)

    orders = (
        Order.objects.filter(rider=rider)
        .select_related("user", "address")
        .annotate(items_count=Count("items"))
        .order_by("-created_at")
    )

    return Response({
        "orders": [_serialize_order_for_rider(order) for order in orders]
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_ready_for_pickup_orders(request):
    orders = (
        Order.objects.filter(status="ready_for_pickup", rider__isnull=True)
        .select_related("user", "address")
        .annotate(items_count=Count("items"))
        .order_by("created_at")
    )

    return Response({
        "orders": [_serialize_order_for_rider(order) for order in orders]
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_order_for_pickup(request):
    order_id = request.data.get("order_id")
    mobile = request.data.get("mobile")
    name = request.data.get("name")

    if not order_id:
        return Response({"error": "order_id is required"}, status=400)

    try:
        order = Order.objects.get(id=order_id, status='ready_for_pickup', rider__isnull=True)
    except Order.DoesNotExist:
        return Response({"error": "Order not available for pickup"}, status=404)

    rider = getattr(request.user, 'rider_profile', None)
    if rider is None:
        if not mobile:
            return Response({"error": "Rider mobile required"}, status=400)
        if not name:
            return Response({"error": "Rider name required"}, status=400)

        user, _ = User.objects.get_or_create(
            username=f"rider_{mobile}",
            defaults={"first_name": name},
        )
        rider, _ = Rider.objects.get_or_create(
            mobile=mobile,
            defaults={"user": user},
        )

    order.rider = rider
    order.status = 'on_the_way'
    order.rider_name = rider.user.first_name if rider.user else order.rider_name
    order.rider_mobile = rider.mobile
    order.save(update_fields=['rider', 'status', 'rider_name', 'rider_mobile', 'updated_at'])

    return Response({
        "message": "Order assigned to rider",
        "order_id": order.id,
        "status": order.status,
        "rider_id": rider.id,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_order_delivered(request):
    order_id = request.data.get("order_id")
    otp = request.data.get("otp")

    if not order_id:
        return Response({"error": "order_id is required"}, status=400)

    if not otp:
        return Response({"error": "otp is required"}, status=400)

    try:
        rider = request.user.rider_profile
    except Rider.DoesNotExist:
        return Response({"error": "Rider profile not found"}, status=404)

    try:
        order = Order.objects.get(id=order_id, rider=rider)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    if str(order.delivery_otp) != str(otp):
        return Response({"error": "Invalid OTP"}, status=400)

    order.status = 'delivered'
    order.save(update_fields=['status', 'updated_at'])

    return Response({
        "message": "Order delivered",
        "order_id": order.id,
        "status": order.status,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_order_status(request):
    order_id = request.data.get("order_id")
    status = request.data.get("status")

    if not order_id or not status:
        return Response({"error": "order_id and status are required"}, status=400)

    allowed_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if status not in allowed_statuses:
        return Response({"error": "Invalid status"}, status=400)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    order.status = status
    order.save(update_fields=["status", "updated_at"])

    return Response({
        "message": "Order status updated",
        "order_id": order.id,
        "status": order.status,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_rider_location(request):
    order_id = request.data.get("order_id")
    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")
    rider_name = request.data.get("rider_name")
    rider_mobile = request.data.get("rider_mobile")

    if not order_id or latitude is None or longitude is None:
        return Response({"error": "order_id, latitude and longitude are required"}, status=400)

    try:
        rider = request.user.rider_profile
    except Rider.DoesNotExist:
        return Response({"error": "Rider profile not found"}, status=404)

    try:
        order = Order.objects.get(id=order_id, rider=rider)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    order.rider_latitude = latitude
    order.rider_longitude = longitude
    order.rider_location_updated_at = timezone.now()
    if rider_name:
        order.rider_name = rider_name
    if rider_mobile:
        order.rider_mobile = rider_mobile

    if order.status not in ["delivered", "cancelled"]:
        order.status = "on_the_way"

    order.save(update_fields=[
        "rider_latitude",
        "rider_longitude",
        "rider_location_updated_at",
        "rider_name",
        "rider_mobile",
        "status",
        "updated_at",
    ])

    return Response({
        "message": "Rider location updated",
        "order_id": order.id,
        "status": order.status,
        "delivery_otp": order.delivery_otp,
        "rider_name": order.rider_name,
        "rider_mobile": order.rider_mobile,
        "rider_latitude": float(order.rider_latitude) if order.rider_latitude else None,
        "rider_longitude": float(order.rider_longitude) if order.rider_longitude else None,
        "rider_location_updated_at": order.rider_location_updated_at.isoformat()
        if order.rider_location_updated_at
        else None,
    })


@api_view(["POST"])
def update_rider_location_simple(request):
    """
    Simplified endpoint for rider apps to update GPS location without JWT authentication.
    Uses order_id and rider_mobile for verification.
    """
    order_id = request.data.get("order_id")
    rider_mobile = request.data.get("rider_mobile")
    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")

    if not order_id or not rider_mobile or latitude is None or longitude is None:
        return Response({
            "error": "order_id, rider_mobile, latitude and longitude are required"
        }, status=400)

    try:
        order = Order.objects.get(id=order_id, rider_mobile=rider_mobile)
    except Order.DoesNotExist:
        return Response({
            "error": "Order not found or rider mobile does not match"
        }, status=404)

    # Update rider location
    order.rider_latitude = latitude
    order.rider_longitude = longitude
    order.rider_location_updated_at = timezone.now()
    
    if order.status not in ["delivered", "cancelled"]:
        order.status = "on_the_way"

    order.save(update_fields=[
        "rider_latitude",
        "rider_longitude",
        "rider_location_updated_at",
        "status",
        "updated_at",
    ])

    return Response({
        "success": True,
        "message": "Rider location updated successfully",
        "order_id": order.id,
        "status": order.status,
        "rider_latitude": float(order.rider_latitude),
        "rider_longitude": float(order.rider_longitude),
        "rider_location_updated_at": order.rider_location_updated_at.isoformat(),
    })


@api_view(["GET"])
def home_data(request):
    cache_key = "api:home_data:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    combo_links_prefetch = Prefetch(
        "combo_links",
        queryset=ComboItem.objects.select_related("item").only(
            "combo_id",
            "quantity",
            "item__id",
            "item__name",
            "item__price",
        ),
        to_attr="prefetched_combo_links",
    )

    categories = Category.objects.only("id", "name", "image", "gst_rate")
    items = (
        Item.objects.filter(is_available=True)
        .select_related("category")
        .prefetch_related(combo_links_prefetch)
        .only(
            "id",
            "name",
            "price",
            "description",
            "is_combo",
            "gst_rate",
            "image",
            "category__id",
            "category__name",
            "category__gst_rate",
        )
    )

    payload = {
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "image": request.build_absolute_uri(c.image.url) if c.image else None,
                "gst_rate": float(c.gst_rate),
            }
            for c in categories
        ],
        "items": [
            {
                "id": i.id,
                "name": i.name,
                "price": float(
                    sum(ci.item.price * ci.quantity for ci in getattr(i, "prefetched_combo_links", []))
                    if i.is_combo
                    else i.price
                ),
                "description": i.description,
                "is_combo": i.is_combo,
                "category_id": i.category.id,
                "category_name": i.category.name,
                "gst_rate": float(i.gst_rate if i.gst_rate is not None else i.category.gst_rate),
                "image": request.build_absolute_uri(i.image.url) if i.image else None,
                "combo_items": [
                    {
                        "item_id": ci.item.id,
                        "name": ci.item.name,
                        "quantity": ci.quantity,
                        "price": float(ci.item.price),
                    }
                    for ci in getattr(i, "prefetched_combo_links", [])
                ] if i.is_combo else [],
            }
            for i in items
        ],
    }
    cache.set(cache_key, payload, timeout=60)
    return Response(payload)


@api_view(["GET"])
def get_combos(request):
    cache_key = "api:combos:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    combo_links_prefetch = Prefetch(
        "combo_links",
        queryset=ComboItem.objects.select_related("item").only(
            "combo_id",
            "quantity",
            "item__id",
            "item__name",
            "item__price",
        ),
        to_attr="prefetched_combo_links",
    )
    combos = (
        Item.objects.filter(is_available=True, is_combo=True)
        .select_related("category")
        .prefetch_related(combo_links_prefetch)
        .only(
            "id",
            "name",
            "description",
            "gst_rate",
            "image",
            "category__id",
            "category__name",
            "category__gst_rate",
        )
    )

    payload = {
        "combos": [
            {
                "id": combo.id,
                "name": combo.name,
                "description": combo.description,
                "price": float(sum(ci.item.price * ci.quantity for ci in getattr(combo, "prefetched_combo_links", []))),
                "category_id": combo.category.id,
                "category_name": combo.category.name,
                "gst_rate": float(combo.gst_rate if combo.gst_rate is not None else combo.category.gst_rate),
                "image": request.build_absolute_uri(combo.image.url) if combo.image else None,
                "combo_items": [
                    {
                        "item_id": ci.item.id,
                        "name": ci.item.name,
                        "quantity": ci.quantity,
                        "price": float(ci.item.price),
                    }
                    for ci in getattr(combo, "prefetched_combo_links", [])
                ],
            }
            for combo in combos
        ]
    }
    cache.set(cache_key, payload, timeout=60)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_cart(request):
    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)

    combo_links_prefetch = Prefetch(
        "item__combo_links",
        queryset=ComboItem.objects.select_related("item").only(
            "combo_id",
            "quantity",
            "item__id",
            "item__name",
            "item__price",
        ),
        to_attr="prefetched_combo_links",
    )
    cart_items = list(
        cart.items.select_related("item__category").prefetch_related(combo_links_prefetch)
    )

    items_payload = []
    subtotal = Decimal("0.00")
    total_tax = Decimal("0.00")
    for ci in cart_items:
        item = ci.item
        combo_links = getattr(item, "prefetched_combo_links", [])
        effective_price = (
            sum(ci_link.item.price * ci_link.quantity for ci_link in combo_links)
            if item.is_combo
            else item.price
        )
        item_subtotal = effective_price * ci.quantity
        gst_rate = item.gst_rate if item.gst_rate is not None else item.category.gst_rate
        item_tax = item_subtotal * (gst_rate / Decimal("100"))
        item_total = item_subtotal + item_tax

        subtotal += item_subtotal
        total_tax += item_tax
        items_payload.append(
            {
                "id": ci.id,
                "item_id": item.id,
                "name": item.name,
                "price": float(effective_price),
                "description": item.description,
                "is_combo": item.is_combo,
                "quantity": ci.quantity,
                "category_name": item.category.name,
                "gst_rate": float(gst_rate),
                "subtotal": float(item_subtotal),
                "tax": float(item_tax),
                "total": float(item_total),
                "image": request.build_absolute_uri(item.image.url) if item.image else None,
                "combo_items": [
                    {
                        "item_id": ci_link.item.id,
                        "name": ci_link.item.name,
                        "quantity": ci_link.quantity,
                        "price": float(ci_link.item.price),
                    }
                    for ci_link in combo_links
                ] if item.is_combo else [],
            }
        )

    total_with_tax_and_fee = subtotal + total_tax + PLATFORM_FEE

    return Response({
        "items": items_payload,
        "summary": {
            "subtotal": float(subtotal),
            "total_tax": float(total_tax),
            "platform_fee": float(PLATFORM_FEE),
            "total": float(total_with_tax_and_fee),
        },
        "item_count": len(cart_items),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    item_id = request.data.get("item_id")
    quantity = request.data.get("quantity", 1)

    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Item not found"}, status=404)

    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        item=item,
        defaults={"quantity": quantity}
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    return Response({
        "message": "Item added to cart",
        "cart_item": {
            "id": cart_item.id,
            "name": item.name,
            "quantity": cart_item.quantity,
            "total": float(cart_item.get_total_price()),
        }
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_cart_item(request, cart_item_id):
    quantity = request.data.get("quantity", 1)

    try:
        cart_item = CartItem.objects.get(id=cart_item_id, cart__user=request.user)
    except CartItem.DoesNotExist:
        return Response({"error": "Cart item not found"}, status=404)

    if quantity <= 0:
        cart_item.delete()
        return Response({"message": "Item removed from cart"})

    cart_item.quantity = quantity
    cart_item.save()

    return Response({
        "message": "Cart item updated",
        "cart_item": {
            "id": cart_item.id,
            "name": cart_item.item.name,
            "quantity": cart_item.quantity,
            "total": float(cart_item.get_total_price()),
        }
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_from_cart(request, cart_item_id):
    try:
        cart_item = CartItem.objects.get(id=cart_item_id, cart__user=request.user)
        cart_item.delete()
        return Response({"message": "Item removed from cart"})
    except CartItem.DoesNotExist:
        return Response({"error": "Cart item not found"}, status=404)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_addresses(request):
    addresses = request.user.addresses.all()
    restaurant_lat, restaurant_lng = _get_restaurant_coords()

    address_list = []
    for addr in addresses:
        # Calculate distance for each address
        distance = None
        delivery_available = False
        delivery_charge = Decimal("0.00")
        
        # Get or geocode coordinates
        addr_lat = addr.latitude
        addr_lng = addr.longitude
        
        if not addr_lat or not addr_lng:
            # Try to geocode the address
            addr_lat, addr_lng = _geocode_address(addr.full_address)
            if addr_lat and addr_lng:
                # Save the geocoded coordinates
                addr.latitude = addr_lat
                addr.longitude = addr_lng
                addr.save(update_fields=["latitude", "longitude"])
        
        if addr_lat and addr_lng:
            try:
                distance = _calculate_distance(
                    restaurant_lat, restaurant_lng,
                    float(addr_lat), float(addr_lng)
                )
                if distance:
                    delivery_available = distance <= 5  # Within 5 km radius
                    delivery_charge = _calculate_delivery_charge(distance)
            except Exception as e:
                print(f"Distance calculation error: {e}")
                distance = None
        
        address_list.append({
            "id": addr.id,
            "type": addr.address_type,
            "full_address": addr.full_address,
            "city": addr.city,
            "postal_code": addr.postal_code,
            "latitude": float(addr_lat) if addr_lat else None,
            "longitude": float(addr_lng) if addr_lng else None,
            "is_default": addr.is_default,
            "display": f"{addr.address_type.capitalize()} | {addr.city}",
            "distance_km": round(distance, 2) if distance else None,
            "delivery_available": delivery_available,
            "delivery_charge": float(delivery_charge),
        })

    return Response({
        "addresses": address_list
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_address(request):
    address_type = request.data.get("address_type", "home")
    full_address = request.data.get("full_address")
    city = request.data.get("city")
    postal_code = request.data.get("postal_code")
    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")
    is_default = request.data.get("is_default", False)

    if not all([full_address, city, postal_code]):
        return Response({"error": "Missing required fields"}, status=400)

    address = Address.objects.create(
        user=request.user,
        address_type=address_type,
        full_address=full_address,
        city=city,
        postal_code=postal_code,
        latitude=latitude,
        longitude=longitude,
        is_default=is_default,
    )

    return Response({
        "id": address.id,
        "type": address.address_type,
        "full_address": address.full_address,
        "city": address.city,
        "postal_code": address.postal_code,
        "latitude": float(address.latitude) if address.latitude else None,
        "longitude": float(address.longitude) if address.longitude else None,
        "is_default": address.is_default,
    }, status=201)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_address(request, address_id):
    try:
        address = Address.objects.get(id=address_id, user=request.user)
    except Address.DoesNotExist:
        return Response({"error": "Address not found"}, status=404)

    address.delete()
    return Response({"message": "Address deleted"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout(request):
    address_id = request.data.get("address_id")
    delivery_method = request.data.get("delivery_method", "delivery")
    coupon_id = request.data.get("coupon_id")
    selected_item_id = request.data.get("selected_item_id")

    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        return Response({"error": "Cart not found"}, status=404)

    if not cart.items.exists():
        return Response({"error": "Cart is empty"}, status=400)

    if delivery_method not in ["delivery", "pickup"]:
        return Response({"error": "Invalid delivery method"}, status=400)

    address = None
    delivery_charge = Decimal("0.00")

    if delivery_method == "delivery":
        try:
            address = Address.objects.get(id=address_id, user=request.user)
        except Address.DoesNotExist:
            return Response({"error": "Address not found"}, status=404)

        # Get restaurant coordinates
        restaurant_lat, restaurant_lng = _get_restaurant_coords()
        
        # Get delivery address coordinates (geocode if needed)
        delivery_lat = address.latitude
        delivery_lng = address.longitude
        
        if not delivery_lat or not delivery_lng:
            delivery_lat, delivery_lng = _geocode_address(address.full_address)
            if delivery_lat and delivery_lng:
                address.latitude = delivery_lat
                address.longitude = delivery_lng
                address.save(update_fields=["latitude", "longitude"])
        
        # Calculate distance and check if within 5 km
        if delivery_lat and delivery_lng:
            distance = _calculate_distance(restaurant_lat, restaurant_lng, delivery_lat, delivery_lng)
            
            if distance and distance > 5:
                return Response(
                    {"error": f"Delivery only available within 5 km radius. Your location is {distance:.1f} km away."},
                    status=400
                )
            
            delivery_charge = _calculate_delivery_charge(distance) if distance else Decimal("0.00")
        else:
            return Response(
                {"error": "Could not determine delivery location. Please try again."},
                status=400
            )

    subtotal = cart.get_subtotal()
    total_tax = cart.get_total_tax()
    
    # Handle coupon discount
    coupon = None
    coupon_discount = Decimal("0.00")
    
    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            
            # Validate coupon
            is_valid, message = coupon.is_valid()
            if not is_valid:
                return Response({"error": f"Coupon error: {message}"}, status=400)
            
            can_use, eligibility_msg = coupon.can_be_used_by_user(request.user)
            if not can_use:
                return Response({"error": eligibility_msg}, status=400)
            
            if subtotal < coupon.min_order_amount:
                return Response({
                    "error": f"Minimum order amount for this coupon is ₹{coupon.min_order_amount}"
                }, status=400)
            
            # Calculate discount
            if coupon.discount_type == 'percentage':
                coupon_discount = (subtotal * coupon.discount_value) / Decimal('100')
                if coupon.max_discount_amount:
                    coupon_discount = min(coupon_discount, coupon.max_discount_amount)
            
            elif coupon.discount_type == 'fixed':
                coupon_discount = min(coupon.discount_value, subtotal)
            
            elif coupon.discount_type == 'free_item':
                if coupon.free_item:
                    coupon_discount = coupon.free_item.get_effective_price()
                elif coupon.free_item_category and selected_item_id:
                    try:
                        selected_item = Item.objects.get(
                            id=selected_item_id,
                            category=coupon.free_item_category,
                            is_available=True
                        )
                        coupon_discount = selected_item.get_effective_price()
                    except Item.DoesNotExist:
                        return Response({"error": "Invalid free item selection"}, status=400)
            
            # Increment coupon usage
            coupon.used_count += 1
            coupon.save(update_fields=['used_count'])
            
        except Coupon.DoesNotExist:
            return Response({"error": "Invalid coupon"}, status=404)
    
    total_price = subtotal + total_tax + PLATFORM_FEE + delivery_charge - coupon_discount
    
    # Ensure total doesn't go below zero
    if total_price < 0:
        total_price = Decimal("0.00")

    # Capture all cart items before creating order
    cart_items_list = list(cart.items.all().select_related('item__category'))

    order = Order.objects.create(
        user=request.user,
        address=address,
        subtotal=subtotal,
        tax=total_tax,
        platform_fee=PLATFORM_FEE,
        delivery_charge=delivery_charge,
        coupon=coupon,
        coupon_discount=coupon_discount,
        total_price=total_price,
        status='pickup_pending' if delivery_method == "pickup" else 'confirmed',
        delivery_otp=_generate_delivery_otp() if delivery_method == "delivery" else None,
    )

    # Add all cart items to the order
    for cart_item in cart_items_list:
        OrderItem.objects.create(
            order=order,
            item=cart_item.item,
            quantity=cart_item.quantity,
            price_at_order=cart_item.item.get_effective_price(),
            tax_at_order=cart_item.get_tax(),
        )
    
    # Add free item from coupon to order (so admin can see and pack it)
    if coupon and coupon.discount_type == 'free_item':
        free_item = None
        if coupon.free_item:
            free_item = coupon.free_item
        elif coupon.free_item_category and selected_item_id:
            try:
                free_item = Item.objects.get(id=selected_item_id)
            except Item.DoesNotExist:
                pass
        
        if free_item:
            # Add the free item to the order with price 0
            OrderItem.objects.create(
                order=order,
                item=free_item,
                quantity=1,
                price_at_order=Decimal('0.00'),  # Free item, no charge
                tax_at_order=Decimal('0.00'),  # No tax on free item
            )
    
    # Record coupon usage
    if coupon:
        UserCouponUsage.objects.create(
            user=request.user,
            coupon=coupon,
            order=order,
            discount_amount=coupon_discount
        )

    cart.items.all().delete()

    return Response({
        "order_id": order.id,
        "status": order.status,
        "subtotal": float(order.subtotal),
        "tax": float(order.tax),
        "platform_fee": float(order.platform_fee),
        "delivery_charge": float(order.delivery_charge),
        "coupon_discount": float(order.coupon_discount),
        "total": float(order.total_price),
        "delivery_address": address.full_address if address else None,
        "message": "Order placed successfully",
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_orders(request):
    orders = (
        request.user.orders.select_related("address")
        .annotate(items_count=Count("items"))
        .order_by("-created_at")
    )

    return Response({
        "orders": [
            {
                "id": order.id,
                "status": order.status,
                "subtotal": float(order.subtotal),
                "tax": float(order.tax),
                "platform_fee": float(order.platform_fee),
                "delivery_charge": float(order.delivery_charge),
                "total": float(order.total_price),
                "delivery_otp": order.delivery_otp,
                "rider_name": order.rider_name,
                "rider_mobile": order.rider_mobile,
                "rider_latitude": float(order.rider_latitude) if order.rider_latitude else None,
                "rider_longitude": float(order.rider_longitude) if order.rider_longitude else None,
                "rider_location_updated_at": order.rider_location_updated_at.isoformat()
                if order.rider_location_updated_at
                else None,
                "created_at": order.created_at.isoformat(),
                "items_count": order.items_count,
                "delivery_address": order.address.full_address if order.address else "N/A",
            }
            for order in orders
        ]
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_order_detail(request, order_id):
    order = (
        Order.objects.filter(id=order_id, user=request.user)
        .select_related("address")
        .prefetch_related("items__item", "review__user", "review__item_reviews")
        .first()
    )
    if not order:
        return Response({"error": "Order not found"}, status=404)

    restaurant_lat, restaurant_lng = _get_restaurant_coords()

    delivery_lat = None
    delivery_lng = None
    if order.address:
        if order.address.latitude and order.address.longitude:
            delivery_lat = float(order.address.latitude)
            delivery_lng = float(order.address.longitude)
        else:
            delivery_lat, delivery_lng = _geocode_address(order.address.full_address)
            if delivery_lat and delivery_lng:
                delivery_lat = float(delivery_lat)
                delivery_lng = float(delivery_lng)
                order.address.latitude = delivery_lat
                order.address.longitude = delivery_lng
                order.address.save(update_fields=["latitude", "longitude"])

    review_payload = None
    if hasattr(order, 'review'):
        review_payload = _serialize_order_review(order.review)

    return Response({
        "id": order.id,
        "status": order.status,
        "delivery_method": "pickup" if order.delivery_otp is None else "delivery",
        "subtotal": float(order.subtotal),
        "tax": float(order.tax),
        "platform_fee": float(order.platform_fee),
        "delivery_charge": float(order.delivery_charge),
        "total": float(order.total_price),
        "delivery_otp": order.delivery_otp,
        "rider_name": order.rider_name,
        "rider_mobile": order.rider_mobile,
        "rider_latitude": float(order.rider_latitude) if order.rider_latitude else None,
        "rider_longitude": float(order.rider_longitude) if order.rider_longitude else None,
        "rider_location_updated_at": order.rider_location_updated_at.isoformat()
        if order.rider_location_updated_at
        else None,
        "restaurant_latitude": restaurant_lat,
        "restaurant_longitude": restaurant_lng,
        "delivery_latitude": delivery_lat,
        "delivery_longitude": delivery_lng,
        "created_at": order.created_at.isoformat(),
        "delivery_address": {
            "type": order.address.address_type,
            "full_address": order.address.full_address,
            "city": order.address.city,
            "postal_code": order.address.postal_code,
        } if order.address else None,
        "items": [
            {
                "order_item_id": oi.id,
                "item_id": oi.item.id if oi.item else None,
                "name": oi.item.name if oi.item else "Deleted Item",
                "quantity": oi.quantity,
                "price": float(oi.price_at_order),
                "tax": float(oi.tax_at_order),
                "total": float(oi.price_at_order * oi.quantity + oi.tax_at_order),
            }
            for oi in order.items.all()
        ],
        "review": review_payload,
    })


def _serialize_order_review(review):
    return {
        "id": review.id,
        "order_id": review.order.id,
        "delivery_rating": review.delivery_rating,
        "overall_rating": review.overall_rating,
        "comment": review.comment,
        "created_at": review.created_at.isoformat(),
        "user": {
            "id": review.user.id,
            "name": review.user.first_name,
            "mobile": review.user.username,
            "email": review.user.email,
        },
        "item_reviews": [
            {
                "id": item_review.id,
                "order_item_id": item_review.order_item.id if item_review.order_item else None,
                "item_name": item_review.item_name,
                "rating": item_review.rating,
            }
            for item_review in review.item_reviews.all()
        ],
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def order_review(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    if request.method == "GET":
        if hasattr(order, 'review'):
            return Response({"review": _serialize_order_review(order.review)})
        return Response({"review": None})

    if order.status != "delivered":
        return Response({"error": "Reviews allowed only after delivery"}, status=400)

    delivery_rating = request.data.get("delivery_rating")
    overall_rating = request.data.get("overall_rating")
    comment = request.data.get("comment", "")
    item_ratings = request.data.get("item_ratings", [])

    try:
        delivery_rating = int(delivery_rating)
    except (TypeError, ValueError):
        delivery_rating = 0

    if delivery_rating < 1 or delivery_rating > 5:
        return Response({"error": "delivery_rating must be between 1 and 5"}, status=400)

    if overall_rating is not None:
        try:
            overall_rating = int(overall_rating)
        except (TypeError, ValueError):
            overall_rating = None
        if overall_rating is not None and (overall_rating < 1 or overall_rating > 5):
            return Response({"error": "overall_rating must be between 1 and 5"}, status=400)

    review, _ = OrderReview.objects.update_or_create(
        order=order,
        defaults={
            "user": request.user,
            "delivery_rating": delivery_rating,
            "overall_rating": overall_rating,
            "comment": comment,
        },
    )

    review.item_reviews.all().delete()
    valid_ratings = []

    for item_rating in item_ratings:
        order_item_id = item_rating.get("order_item_id")
        rating_value = item_rating.get("rating")
        try:
            rating_value = int(rating_value)
        except (TypeError, ValueError):
            continue
        if rating_value < 1 or rating_value > 5:
            continue

        try:
            order_item = OrderItem.objects.get(id=order_item_id, order=order)
        except OrderItem.DoesNotExist:
            continue

        item_name = order_item.item.name if order_item.item else "Deleted Item"
        OrderItemReview.objects.create(
            review=review,
            order_item=order_item,
            item_name=item_name,
            rating=rating_value,
        )
        valid_ratings.append(rating_value)

    if overall_rating is None and valid_ratings:
        average_rating = round(sum(valid_ratings) / len(valid_ratings))
        review.overall_rating = average_rating
        review.save(update_fields=["overall_rating", "updated_at"])

    return Response({"review": _serialize_order_review(review)})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_active_order(request):
    active_statuses = [
        'confirmed',
        'preparing',
        'ready_for_pickup',
        'on_the_way',
        'delivery_pending',
    ]

    order = (
        Order.objects
        .filter(user=request.user, status__in=active_statuses)
        .select_related("address")
        .annotate(items_count=Count("items"))
        .order_by('-created_at')
        .first()
    )

    if not order:
        return Response({"active_order": None})

    return Response({
        "active_order": {
            "id": order.id,
            "status": order.status,
            "total": float(order.total_price),
            "created_at": order.created_at.isoformat(),
            "rider_name": order.rider_name,
            "rider_mobile": order.rider_mobile,
            "delivery_otp": order.delivery_otp,
            "delivery_address": order.address.full_address if order.address else None,
            "items_count": order.items_count,
            "rider_latitude": float(order.rider_latitude) if order.rider_latitude else None,
            "rider_longitude": float(order.rider_longitude) if order.rider_longitude else None,
        }
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_razorpay_order(request):
    """Create a Razorpay order for payment"""
    amount = request.data.get("amount")  # Amount in rupees
    
    if not amount:
        return Response({"error": "Amount is required"}, status=400)
    
    try:
        # Initialize Razorpay client
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        
        # Amount should be in paise (smallest currency unit)
        amount_in_paise = int(float(amount) * 100)
        
        # Create Razorpay order
        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1  # Auto capture
        })
        
        return Response({
            "order_id": razorpay_order['id'],
            "amount": razorpay_order['amount'],
            "currency": razorpay_order['currency'],
            "key_id": RAZORPAY_KEY_ID,
        })
    except Exception as e:
        return Response({
            "error": f"Failed to create Razorpay order: {str(e)}"
        }, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_razorpay_payment(request):
    """Verify Razorpay payment signature and complete order"""
    razorpay_order_id = request.data.get("razorpay_order_id")
    razorpay_payment_id = request.data.get("razorpay_payment_id")
    razorpay_signature = request.data.get("razorpay_signature")
    address_id = request.data.get("address_id")
    delivery_method = request.data.get("delivery_method", "delivery")
    
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return Response({"error": "Missing payment verification data"}, status=400)
    
    try:
        # Verify signature
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        # This will raise SignatureVerificationError if signature is invalid
        client.utility.verify_payment_signature(params_dict)
        
        # Signature is valid, process the order
        try:
            cart = request.user.cart
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=404)

        if not cart.items.exists():
            return Response({"error": "Cart is empty"}, status=400)

        address = None
        delivery_charge = Decimal("0.00")

        if delivery_method == "delivery":
            try:
                address = Address.objects.get(id=address_id, user=request.user)
            except Address.DoesNotExist:
                return Response({"error": "Address not found"}, status=404)

            # Calculate delivery charge
            restaurant_lat, restaurant_lng = _get_restaurant_coords()
            delivery_lat = address.latitude
            delivery_lng = address.longitude
            
            if not delivery_lat or not delivery_lng:
                delivery_lat, delivery_lng = _geocode_address(address.full_address)
                if delivery_lat and delivery_lng:
                    address.latitude = delivery_lat
                    address.longitude = delivery_lng
                    address.save(update_fields=["latitude", "longitude"])
            
            if delivery_lat and delivery_lng:
                distance = _calculate_distance(restaurant_lat, restaurant_lng, delivery_lat, delivery_lng)
                if distance and distance > 5:
                    return Response(
                        {"error": f"Delivery only available within 5 km radius. Your location is {distance:.1f} km away."},
                        status=400
                    )
                delivery_charge = _calculate_delivery_charge(distance) if distance else Decimal("0.00")

        subtotal = cart.get_subtotal()
        total_tax = cart.get_total_tax()
        total_price = subtotal + total_tax + PLATFORM_FEE + delivery_charge

        # Create order
        order = Order.objects.create(
            user=request.user,
            address=address,
            subtotal=subtotal,
            tax=total_tax,
            platform_fee=PLATFORM_FEE,
            delivery_charge=delivery_charge,
            total_price=total_price,
            status='pickup_pending' if delivery_method == "pickup" else 'confirmed',
            delivery_otp=_generate_delivery_otp() if delivery_method == "delivery" else None,
        )

        # Create order items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                item=cart_item.item,
                quantity=cart_item.quantity,
                price_at_order=cart_item.item.get_effective_price(),
                tax_at_order=cart_item.get_tax(),
            )

        # Clear cart
        cart.items.all().delete()

        return Response({
            "success": True,
            "order_id": order.id,
            "razorpay_payment_id": razorpay_payment_id,
            "message": "Payment successful and order placed",
        }, status=201)
        
    except razorpay.errors.SignatureVerificationError:
        return Response({
            "error": "Payment verification failed. Invalid signature."
        }, status=400)
    except Exception as e:
        return Response({
            "error": f"Payment verification error: {str(e)}"
        }, status=500)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_push_token(request):
    """Register user's Expo push token"""
    push_token = request.data.get("push_token")
    device_type = request.data.get("device_type", "android")

    if not push_token:
        return Response({"error": "push_token is required"}, status=400)

    # Create or update push token
    token_obj, created = PushToken.objects.update_or_create(
        user=request.user,
        push_token=push_token,
        defaults={
            "device_type": device_type,
            "is_active": True,
            "updated_at": timezone.now()
        }
    )

    return Response({
        "message": "Push token registered successfully",
        "created": created
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unregister_push_token(request):
    """Unregister user's push token"""
    push_token = request.data.get("push_token")

    if not push_token:
        return Response({"error": "push_token is required"}, status=400)

    PushToken.objects.filter(user=request.user, push_token=push_token).update(is_active=False)

    return Response({"message": "Push token unregistered successfully"})


@api_view(["GET"])
def check_app_version(request):
    """Check if app update is available"""
    current_version = request.query_params.get("version", "1.0.0")
    platform = request.query_params.get("platform", "android")

    # Get latest version for platform
    latest = AppVersion.objects.filter(
        models.Q(platform=platform) | models.Q(platform='all')
    ).order_by('-released_at').first()

    if not latest:
        return Response({
            "update_available": False,
            "current_version": current_version
        })

    # Simple version comparison (you can use packaging.version for proper comparison)
    update_available = latest.version != current_version

    return Response({
        "update_available": update_available,
        "latest_version": latest.version,
        "current_version": current_version,
        "is_mandatory": latest.is_mandatory,
        "release_notes": latest.release_notes,
        "features": latest.features,
    })


def send_expo_push_notification(push_tokens, title, body, data=None):
    """
    Send push notification via Expo Push Notification service
    
    Args:
        push_tokens: List of Expo push tokens
        title: Notification title
        body: Notification body
        data: Optional data payload
    """
    if not push_tokens:
        return

    messages = []
    for token in push_tokens:
        messages.append({
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
            "priority": "high",
            "channelId": "order-updates",
        })

    try:
        response = requests.post(
            'https://exp.host/--/api/v2/push/send',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            json=messages,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✓ Sent {len(messages)} notifications")
        else:
            print(f"✗ Failed to send notifications: {response.text}")
            
    except Exception as e:
        print(f"✗ Error sending notifications: {str(e)}")


def notify_order_status_change(order_id, new_status):
    """Send notification when order status changes"""
    try:
        order = Order.objects.get(id=order_id)
        user = order.user
        
        # Get all active push tokens for user
        push_tokens = list(
            PushToken.objects.filter(user=user, is_active=True)
            .values_list('push_token', flat=True)
        )

        if not push_tokens:
            return

        # Status messages
        status_messages = {
            'confirmed': {
                'title': '✅ Order Confirmed',
                'body': f'Order #{order_id} has been confirmed and is being prepared.'
            },
            'preparing': {
                'title': '👨‍🍳 Order is Being Prepared',
                'body': f'Your delicious food is being prepared! Order #{order_id}'
            },
            'ready_for_pickup': {
                'title': '📦 Order Ready for Pickup',
                'body': f'Order #{order_id} is ready! Waiting for delivery partner.'
            },
            'on_the_way': {
                'title': '🚴 Delivery Partner on the Way',
                'body': f'Your order #{order_id} is on the way to you!'
            },
            'delivered': {
                'title': '🎉 Order Delivered',
                'body': f'Order #{order_id} has been delivered. Enjoy your meal!'
            },
            'cancelled': {
                'title': '❌ Order Cancelled',
                'body': f'Order #{order_id} has been cancelled.'
            },
        }

        message = status_messages.get(new_status, {
            'title': 'Order Update',
            'body': f'Order #{order_id} status: {new_status}'
        })

        send_expo_push_notification(
            push_tokens,
            message['title'],
            message['body'],
            {'order_id': order_id, 'status': new_status, 'type': 'order_update'}
        )

    except Order.DoesNotExist:
        print(f"Order {order_id} not found")
    except Exception as e:
        print(f"Error sending order notification: {str(e)}")


def notify_app_update(version, platform='all'):
    """Send notification about new app version"""
    try:
        app_version = AppVersion.objects.get(version=version, platform=platform)
        
        # Get all active push tokens (filter by platform if needed)
        query = PushToken.objects.filter(is_active=True)
        if platform != 'all':
            query = query.filter(device_type=platform)
        
        push_tokens = list(query.values_list('push_token', flat=True))

        if not push_tokens:
            return

        features_text = ', '.join(app_version.features[:3])
        
        send_expo_push_notification(
            push_tokens,
            '🎁 New App Update Available',
            f'Version {version} is now available! {features_text}',
            {
                'type': 'app_update',
                'version': version,
                'is_mandatory': app_version.is_mandatory
            }
        )

    except AppVersion.DoesNotExist:
        print(f"App version {version} not found")
    except Exception as e:
        print(f"Error sending app update notification: {str(e)}")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_coupons(request):
    """Get all available coupons for the current user"""
    try:
        user = request.user
        now = timezone.now()
        
        # Get active coupons that are currently valid
        coupons = Coupon.objects.filter(
            is_active=True,
            valid_from__lte=now
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        )
        
        coupon_list = []
        for coupon in coupons:
            # Check if coupon is still valid and user is eligible
            is_valid, message = coupon.is_valid()
            can_use, eligibility_msg = coupon.can_be_used_by_user(user)
            
            if is_valid and can_use:
                coupon_data = {
                    'id': coupon.id,
                    'code': coupon.code,
                    'description': coupon.description,
                    'discount_type': coupon.discount_type,
                    'discount_value': float(coupon.discount_value) if coupon.discount_value else None,
                    'min_order_amount': float(coupon.min_order_amount),
                    'max_discount_amount': float(coupon.max_discount_amount) if coupon.max_discount_amount else None,
                    'for_first_time_users_only': coupon.for_first_time_users_only,
                    'valid_until': coupon.valid_until.isoformat() if coupon.valid_until else None,
                }
                
                # Add free item/category info if applicable
                if coupon.discount_type == 'free_item':
                    if coupon.free_item:
                        coupon_data['free_item'] = {
                            'id': coupon.free_item.id,
                            'name': coupon.free_item.name,
                            'price': float(coupon.free_item.price)
                        }
                    elif coupon.free_item_category:
                        coupon_data['free_item_category'] = {
                            'id': coupon.free_item_category.id,
                            'name': coupon.free_item_category.name
                        }
                
                coupon_list.append(coupon_data)
        
        return Response({'coupons': coupon_list})
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_coupon(request):
    """Validate and apply a coupon code"""
    try:
        user = request.user
        code = request.data.get('code', '').upper().strip()
        cart_subtotal = Decimal(str(request.data.get('cart_subtotal', 0)))
        
        if not code:
            return Response({'error': 'Coupon code is required'}, status=400)
        
        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response({'error': 'Invalid coupon code'}, status=404)
        
        # Check if coupon is valid
        is_valid, message = coupon.is_valid()
        if not is_valid:
            return Response({'error': message}, status=400)
        
        # Check if user is eligible
        can_use, eligibility_msg = coupon.can_be_used_by_user(user)
        if not can_use:
            return Response({'error': eligibility_msg}, status=400)
        
        # Check minimum order amount
        if cart_subtotal < coupon.min_order_amount:
            return Response({
                'error': f'Minimum order amount is ₹{coupon.min_order_amount}'
            }, status=400)
        
        # Calculate discount
        discount_amount = Decimal('0.00')
        free_item_selection_required = False
        available_items = []
        
        if coupon.discount_type == 'percentage':
            discount_amount = (cart_subtotal * coupon.discount_value) / Decimal('100')
            if coupon.max_discount_amount:
                discount_amount = min(discount_amount, coupon.max_discount_amount)
        
        elif coupon.discount_type == 'fixed':
            discount_amount = min(coupon.discount_value, cart_subtotal)
        
        elif coupon.discount_type == 'free_item':
            if coupon.free_item:
                discount_amount = coupon.free_item.get_effective_price()
                available_items = [{
                    'id': coupon.free_item.id,
                    'name': coupon.free_item.name,
                    'price': float(coupon.free_item.price),
                    'image': coupon.free_item.image.url if coupon.free_item.image else None,
                    'description': coupon.free_item.description if hasattr(coupon.free_item, 'description') else ''
                }]
            elif coupon.free_item_category:
                free_item_selection_required = True
                # Get all available items from the category
                items = Item.objects.filter(
                    category=coupon.free_item_category,
                    is_available=True,
                    is_combo=False
                )
                available_items = [{
                    'id': item.id,
                    'name': item.name,
                    'price': float(item.price),
                    'image': item.image.url if item.image else None
                } for item in items]
        
        response_data = {
            'valid': True,
            'coupon': {
                'id': coupon.id,
                'code': coupon.code,
                'description': coupon.description,
                'discount_type': coupon.discount_type,
                'discount_amount': float(discount_amount),
                'free_item_selection_required': free_item_selection_required,
                'available_items': available_items
            }
        }
        
        return Response(response_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_coupon(request):
    """Apply a validated coupon to calculate final discount"""
    try:
        user = request.user
        coupon_id = request.data.get('coupon_id')
        selected_item_id = request.data.get('selected_item_id')
        cart_subtotal = Decimal(str(request.data.get('cart_subtotal', 0)))
        
        if not coupon_id:
            return Response({'error': 'Coupon ID is required'}, status=400)
        
        try:
            coupon = Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            return Response({'error': 'Invalid coupon'}, status=404)
        
        # Revalidate coupon
        is_valid, message = coupon.is_valid()
        if not is_valid:
            return Response({'error': message}, status=400)
        
        can_use, eligibility_msg = coupon.can_be_used_by_user(user)
        if not can_use:
            return Response({'error': eligibility_msg}, status=400)
        
        if cart_subtotal < coupon.min_order_amount:
            return Response({
                'error': f'Minimum order amount is ₹{coupon.min_order_amount}'
            }, status=400)
        
        # Calculate discount
        discount_amount = Decimal('0.00')
        free_item_info = None
        
        if coupon.discount_type == 'percentage':
            discount_amount = (cart_subtotal * coupon.discount_value) / Decimal('100')
            if coupon.max_discount_amount:
                discount_amount = min(discount_amount, coupon.max_discount_amount)
        
        elif coupon.discount_type == 'fixed':
            discount_amount = min(coupon.discount_value, cart_subtotal)
        
        elif coupon.discount_type == 'free_item':
            if coupon.free_item:
                discount_amount = coupon.free_item.get_effective_price()
                free_item_info = {
                    'id': coupon.free_item.id,
                    'name': coupon.free_item.name,
                    'price': float(coupon.free_item.price)
                }
            elif coupon.free_item_category and selected_item_id:
                try:
                    selected_item = Item.objects.get(
                        id=selected_item_id,
                        category=coupon.free_item_category,
                        is_available=True
                    )
                    discount_amount = selected_item.get_effective_price()
                    free_item_info = {
                        'id': selected_item.id,
                        'name': selected_item.name,
                        'price': float(selected_item.price)
                    }
                except Item.DoesNotExist:
                    return Response({'error': 'Invalid item selection'}, status=400)
            else:
                return Response({'error': 'Please select a free item'}, status=400)
        
        return Response({
            'success': True,
            'discount_amount': float(discount_amount),
            'free_item': free_item_info,
            'message': f'Coupon {coupon.code} applied successfully!'
        })
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ===========================
# SUPPORT CHAT ENDPOINTS
# ===========================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_support_ticket(request):
    """Create a new support ticket"""
    category = request.data.get('category')
    order_id = request.data.get('order_id')
    initial_message = request.data.get('message')
    
    if not category or category not in ['general', 'order']:
        return Response({'error': 'Invalid category'}, status=400)
    
    ticket_data = {
        'user': request.user,
        'category': category,
    }
    
    if order_id:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
            ticket_data['order'] = order
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)
    
    ticket = SupportTicket.objects.create(**ticket_data)
    
    # Create initial message if provided
    if initial_message:
        SupportMessage.objects.create(
            ticket=ticket,
            sender_type='customer',
            message=initial_message
        )
    
    return Response({
        'id': ticket.id,
        'category': ticket.category,
        'status': ticket.status,
        'created_at': ticket.created_at.isoformat(),
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_support_tickets(request):
    """Get all support tickets for current user"""
    tickets = (
        SupportTicket.objects.filter(user=request.user)
        .annotate(
            unread_count=Count(
                "messages",
                filter=models.Q(messages__sender_type="admin"),
            )
        )
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=SupportMessage.objects.only("id", "ticket_id", "message").order_by("-created_at"),
                to_attr="prefetched_messages",
            )
        )
    )
    
    data = []
    for ticket in tickets:
        prefetched_messages = getattr(ticket, "prefetched_messages", [])
        last_message = prefetched_messages[0] if prefetched_messages else None
        data.append({
            'id': ticket.id,
            'category': ticket.category,
            'category_display': ticket.get_category_display(),
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'order_id': ticket.order_id,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
            'last_message': last_message.message if last_message else None,
            'unread_count': ticket.unread_count,
        })
    
    return Response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def support_chat(request, ticket_id):
    """Get messages or send a new message for a ticket"""
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
    except SupportTicket.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=404)
    
    if request.method == 'GET':
        # Return all messages
        messages = ticket.messages.all()
        data = {
            'ticket': {
                'id': ticket.id,
                'category': ticket.category,
                'category_display': ticket.get_category_display(),
                'status': ticket.status,
                'status_display': ticket.get_status_display(),
                'order_id': ticket.order_id,
                'created_at': ticket.created_at.isoformat(),
            },
            'messages': [
                {
                    'id': msg.id,
                    'sender_type': msg.sender_type,
                    'message': msg.message,
                    'created_at': msg.created_at.isoformat(),
                }
                for msg in messages
            ]
        }
        return Response(data)
    
    elif request.method == 'POST':
        # Send a new message
        message_text = request.data.get('message')
        if not message_text or not message_text.strip():
            return Response({'error': 'Message cannot be empty'}, status=400)
        
        message = SupportMessage.objects.create(
            ticket=ticket,
            sender_type='customer',
            message=message_text.strip()
        )
        
        # Update ticket status if closed
        if ticket.status == 'closed':
            ticket.status = 'open'
            ticket.save()
        
        return Response({
            'id': message.id,
            'sender_type': message.sender_type,
            'message': message.message,
            'created_at': message.created_at.isoformat(),
        }, status=201)
