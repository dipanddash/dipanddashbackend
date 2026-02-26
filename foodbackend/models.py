from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User


class OTP(models.Model):
    mobile = models.CharField(max_length=10)
    otp = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["mobile", "created_at"], name="otp_mobile_created_idx"),
        ]

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return self.mobile


class RiderOTP(models.Model):
    mobile = models.CharField(max_length=10)
    otp = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["mobile", "created_at"], name="riderotp_mobile_created_idx"),
        ]

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return self.mobile


class Rider(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rider_profile')
    mobile = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rider {self.mobile}"


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    mobile = models.CharField(max_length=15, unique=True)
    force_password_change = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email or self.user.username} ({self.mobile})"


class Category(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class HomeBanner(models.Model):
    title = models.CharField(max_length=120, blank=True)
    media = models.ImageField(upload_to="home_banners/")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title or f"Banner #{self.id}"


class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField()
    image = models.ImageField(upload_to="items/", blank=True, null=True)
    is_available = models.BooleanField(default=True)
    is_combo = models.BooleanField(default=False)
    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GST rate (%) for this item. Leave empty to use category GST.",
    )
    combo_items = models.ManyToManyField(
        "self",
        through="ComboItem",
        symmetrical=False,
        related_name="included_in_combos",
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["is_available", "is_combo"]),
        ]

    def __str__(self):
        return f"{self.name} - ₹{self.get_effective_price()}"

    def get_gst_rate(self):
        return self.gst_rate if self.gst_rate is not None else self.category.gst_rate

    def get_effective_price(self):
        if not self.is_combo:
            return self.price
        combo_items = self.combo_links.select_related("item")
        return sum(ci.item.price * ci.quantity for ci in combo_items)


class ComboItem(models.Model):
    combo = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="combo_links")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="combo_components")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("combo", "item")

    def __str__(self):
        return f"{self.quantity} x {self.item.name} in {self.combo.name}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user.username}"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    def get_subtotal(self):
        return sum(item.get_subtotal() for item in self.items.all())

    def get_total_tax(self):
        return sum(item.get_tax() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'item')

    def __str__(self):
        return f"{self.quantity} x {self.item.name}"

    def get_subtotal(self):
        return self.item.get_effective_price() * self.quantity

    def get_tax(self):
        gst_rate = self.item.get_gst_rate() / 100
        return self.get_subtotal() * gst_rate

    def get_total_price(self):
        return self.get_subtotal() + self.get_tax()


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(
        max_length=20,
        choices=[('home', 'Home'), ('work', 'Work'), ('other', 'Other')],
        default='home'
    )
    full_address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.user.username} - {self.address_type}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready_for_pickup', 'Ready For Pickup'),
        ('pickup_pending', 'Pickup Pending'),
        ('on_the_way', 'On The Way'),
        ('delivery_pending', 'Delivery Pending'),
        ('pickup_failed', 'Pickup Failed'),
        ('pickup_rescheduled', 'Pickup Rescheduled'),
        ('delivery_failed', 'Delivery Failed'),
        ('delivery_rescheduled', 'Delivery Rescheduled'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    rider = models.ForeignKey(
        Rider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=5.0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    delivery_otp = models.CharField(max_length=4, null=True, blank=True)
    rider_name = models.CharField(max_length=100, null=True, blank=True)
    rider_mobile = models.CharField(max_length=15, null=True, blank=True)
    rider_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rider_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rider_location_updated_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"], name="order_user_created_idx"),
            models.Index(fields=["user", "status", "created_at"], name="order_user_status_created_idx"),
            models.Index(fields=["rider", "created_at"], name="order_rider_created_idx"),
            models.Index(fields=["status", "rider", "created_at"], name="order_status_rider_created_idx"),
            models.Index(fields=["rider_mobile"], name="order_rider_mobile_idx"),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)
    tax_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.item.name if self.item else 'Deleted Item'}"


class OrderReview(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_reviews')
    delivery_rating = models.PositiveSmallIntegerField()
    overall_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for Order #{self.order.id} by {self.user.username}"


class OrderItemReview(models.Model):
    review = models.ForeignKey(OrderReview, on_delete=models.CASCADE, related_name='item_reviews')
    order_item = models.ForeignKey(OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    item_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_name} ({self.rating}★)"
class PushToken(models.Model):
    """Store user's Expo push notification tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_tokens')
    push_token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10, choices=[('ios', 'iOS'), ('android', 'Android')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'push_token']

    def __str__(self):
        return f"{self.user.username} - {self.device_type}"


class AppVersion(models.Model):
    """Track app versions for update notifications"""
    version = models.CharField(max_length=20, unique=True)
    release_notes = models.TextField()
    features = models.JSONField(default=list)  # List of new features
    is_mandatory = models.BooleanField(default=False)
    released_at = models.DateTimeField(auto_now_add=True)
    platform = models.CharField(
        max_length=10, 
        choices=[('all', 'All'), ('ios', 'iOS'), ('android', 'Android')],
        default='all'
    )

    def __str__(self):
        return f"v{self.version} - {self.platform}"


class Coupon(models.Model):
    """Coupon/Offer model for promotions"""
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage Discount'),
        ('fixed', 'Fixed Amount Discount'),
        ('free_item', 'Free Item'),
    ]
    
    code = models.CharField(max_length=50, unique=True, help_text="Coupon code (e.g., NEWDIP)")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Percentage (e.g., 10 for 10%) or Fixed amount (e.g., 50 for ₹50)",
        null=True,
        blank=True
    )
    free_item = models.ForeignKey(
        Item, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='coupon_free_items',
        help_text="Item to be given free (for free_item discount type)"
    )
    free_item_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coupon_free_categories',
        help_text="Category to choose free item from (e.g., Burgers)"
    )
    min_order_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Minimum order amount to apply coupon"
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum discount amount (for percentage discounts)"
    )
    for_first_time_users_only = models.BooleanField(
        default=False,
        help_text="Only available for users who haven't placed an order before"
    )
    max_uses = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Maximum number of times this coupon can be used (leave empty for unlimited)"
    )
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True, help_text="Leave empty for no expiry")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, help_text="Description shown to users")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["is_active", "valid_from", "valid_until"], name="coupon_active_window_idx"),
            models.Index(fields=["for_first_time_users_only"], name="coupon_first_time_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"

    def is_valid(self):
        """Check if coupon is valid based on dates and usage"""
        if not self.is_active:
            return False, "Coupon is not active"
        
        now = timezone.now()
        if now < self.valid_from:
            return False, "Coupon is not yet valid"
        
        if self.valid_until and now > self.valid_until:
            return False, "Coupon has expired"
        
        if self.max_uses and self.used_count >= self.max_uses:
            return False, "Coupon usage limit reached"
        
        return True, "Valid"

    def can_be_used_by_user(self, user):
        """Check if user is eligible to use this coupon"""
        if self.for_first_time_users_only:
            order_count = Order.objects.filter(user=user).count()
            if order_count > 0:
                return False, "Coupon is only for first-time users"
        
        return True, "Eligible"


class UserCouponUsage(models.Model):
    """Track which users have used which coupons"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_usage')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='user_usage')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='coupon_usage')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-used_at']

    def __str__(self):
        return f"{self.user.username} used {self.coupon.code}"


class SupportTicket(models.Model):
    """Support ticket for customer help requests"""
    CATEGORY_CHOICES = [
        ('general', 'General Issue'),
        ('order', 'Order Related Issue'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["user", "created_at"], name="supportticket_user_created_idx"),
            models.Index(fields=["status", "created_at"], name="supticket_status_created_ix"),
        ]

    def __str__(self):
        return f"Ticket #{self.id} - {self.get_category_display()} - {self.user.username}"

    def get_customer_name(self):
        """Get customer name from user profile"""
        profile = getattr(self.user, 'profile', None)
        if profile:
            return profile.name or self.user.username
        return self.user.username

    def get_customer_mobile(self):
        """Get customer mobile from user profile"""
        profile = getattr(self.user, 'profile', None)
        if profile:
            return profile.mobile or ''
        return ''


class SupportMessage(models.Model):
    """Individual messages within a support ticket"""
    SENDER_CHOICES = [
        ('customer', 'Customer'),
        ('admin', 'Admin'),
    ]
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="supportmsg_ticket_created_idx"),
        ]

    def __str__(self):
        return f"{self.sender_type} - {self.message[:50]}"
