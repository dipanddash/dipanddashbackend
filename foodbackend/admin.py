from django.contrib import admin
from django import forms
from django.core.cache import cache
from .models import (
    HomeBanner,
    Category, 
    Item, 
    Cart, 
    CartItem, 
    Address, 
    Order, 
    OrderItem,
    OrderReview,
    OrderItemReview,
    Coupon,
    UserCouponUsage,
    SupportTicket,
    SupportMessage,
)


@admin.register(HomeBanner)
class HomeBannerAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "sort_order", "is_active", "created_at")
    list_filter = ("is_active",)
    list_editable = ("sort_order", "is_active")
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete("api:home_data:v2")

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        cache.delete("api:home_data:v2")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'gst_rate')
    list_editable = ('gst_rate',)
    search_fields = ('name',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'gst_rate', 'is_available')
    list_filter = ('category', 'is_available')
    list_editable = ('price', 'gst_rate', 'is_available')
    search_fields = ('name', 'description')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'updated_at', 'item_count')
    search_fields = ('user__username', 'user__first_name')
    readonly_fields = ('created_at', 'updated_at')
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'item', 'quantity', 'get_subtotal', 'get_tax', 'get_total_price')
    list_filter = ('cart__user',)
    search_fields = ('cart__user__username', 'item__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'address_type', 'city', 'is_default')
    list_filter = ('address_type', 'is_default')
    search_fields = ('user__username', 'full_address', 'city')


class OrderItemInline(admin.TabularInline):
    """Show order items inline when viewing an order"""
    model = OrderItem
    extra = 0
    readonly_fields = ('item', 'quantity', 'price_at_order', 'tax_at_order')
    fields = ('item', 'quantity', 'price_at_order', 'tax_at_order')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'subtotal', 'tax', 'platform_fee', 'total_price', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__first_name')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('status',)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'item', 'quantity', 'price_at_order', 'tax_at_order')
    list_filter = ('order__status',)
    search_fields = ('order__user__username', 'item__name')


class OrderItemReviewInline(admin.TabularInline):
    model = OrderItemReview
    extra = 0
    readonly_fields = ('item_name', 'rating', 'created_at')
    fields = ('item_name', 'rating', 'created_at')


@admin.register(OrderReview)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'delivery_rating', 'overall_rating', 'created_at')
    list_filter = ('delivery_rating', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'order__id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemReviewInline]


@admin.register(OrderItemReview)
class OrderItemReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'item_name', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('item_name', 'review__order__id', 'review__user__username')
    readonly_fields = ('created_at',)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code', 
        'discount_type', 
        'discount_value', 
        'min_order_amount',
        'for_first_time_users_only',
        'used_count',
        'max_uses',
        'is_active',
        'valid_until'
    )
    list_filter = ('discount_type', 'is_active', 'for_first_time_users_only', 'valid_from', 'valid_until')
    search_fields = ('code', 'description')
    list_editable = ('is_active',)
    readonly_fields = ('used_count', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Discount Configuration', {
            'fields': (
                'discount_type', 
                'discount_value', 
                'free_item',
                'free_item_category',
                'max_discount_amount'
            )
        }),
        ('Conditions', {
            'fields': (
                'min_order_amount',
                'for_first_time_users_only',
                'max_uses',
                'used_count'
            )
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserCouponUsage)
class UserCouponUsageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'coupon', 'order', 'discount_amount', 'used_at')
    list_filter = ('coupon', 'used_at')
    search_fields = ('user__username', 'coupon__code', 'order__id')
    readonly_fields = ('used_at',)


class SupportMessageInline(admin.TabularInline):
    """Show support messages inline when viewing a ticket"""
    model = SupportMessage
    extra = 0
    readonly_fields = ('sender_type', 'message', 'created_at')
    fields = ('sender_type', 'message', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_customer_name', 'get_customer_mobile', 'category', 'status', 'order', 'created_at', 'updated_at')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('user__username', 'user__profile__name', 'user__profile__mobile', 'id')
    list_editable = ('status',)
    readonly_fields = ('user', 'category', 'order', 'created_at', 'updated_at', 'get_customer_name', 'get_customer_mobile', 'admin_reply_form')
    inlines = [SupportMessageInline]
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('user', 'get_customer_name', 'get_customer_mobile')
        }),
        ('Ticket Details', {
            'fields': ('category', 'status', 'order')
        }),
        ('Admin Reply', {
            'fields': ('admin_reply_form',),
            'description': 'Type your reply below and save the ticket to send it to the customer.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_customer_name(self, obj):
        return obj.get_customer_name()
    get_customer_name.short_description = 'Customer Name'
    
    def get_customer_mobile(self, obj):
        return obj.get_customer_mobile()
    get_customer_mobile.short_description = 'Mobile'
    
    def admin_reply_form(self, obj):
        """Display a form to send admin replies"""
        from django.utils.html import format_html
        
        if obj.pk:  # Only show for existing tickets
            return format_html(
                '<textarea name="admin_reply" rows="4" cols="80" '
                'placeholder="Type your reply here and save the ticket to send it to the customer..." '
                'style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace;"></textarea>'
                '<p style="color: #666; font-size: 12px; margin-top: 5px;">'
                'Note: Your reply will be sent when you click "Save" at the bottom of this page.</p>'
            )
        return "Save the ticket first to enable replies"
    admin_reply_form.short_description = 'Reply to Customer'
    
    def save_model(self, request, obj, form, change):
        """Override save to handle admin replies"""
        super().save_model(request, obj, form, change)
        
        # Check if admin_reply field exists in POST data
        admin_reply = request.POST.get('admin_reply', '').strip()
        if admin_reply and obj.pk:
            # Create admin message
            SupportMessage.objects.create(
                ticket=obj,
                sender_type='admin',
                message=admin_reply
            )
            
            # Update ticket status if it was closed
            if obj.status == 'closed':
                obj.status = 'in_progress'
                obj.save()


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'sender_type', 'short_message', 'created_at')
    list_filter = ('sender_type', 'created_at')
    search_fields = ('ticket__id', 'message', 'ticket__user__username')
    readonly_fields = ('ticket', 'sender_type', 'message', 'created_at')
    
    def short_message(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    short_message.short_description = 'Message'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
