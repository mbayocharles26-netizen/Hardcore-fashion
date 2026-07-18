from django.db import models
import uuid

from django.contrib.auth.models import User


# ── Customer profile & address ─────────────────────────────────────────────────

class CustomerProfile(models.Model):
    """Extended profile for customer accounts."""
    user               = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone              = models.CharField(max_length=30, blank=True, default='')
    avatar             = models.ImageField(upload_to='customers/avatars/', blank=True, null=True)
    loyalty_points     = models.PositiveIntegerField(default=0)
    preferred_currency = models.CharField(max_length=8, default='RWF')
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'CustomerProfile — {self.user.username}'


class Address(models.Model):
    """Multiple saved shipping/billing addresses per customer."""
    TYPE_SHIPPING = 'shipping'
    TYPE_BILLING  = 'billing'
    TYPE_CHOICES  = [(TYPE_SHIPPING, 'Shipping'), (TYPE_BILLING, 'Billing')]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label      = models.CharField(max_length=60, blank=True, default='', help_text='e.g. Home, Work')
    type       = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_SHIPPING)
    full_name  = models.CharField(max_length=200)
    line1      = models.CharField(max_length=255)
    line2      = models.CharField(max_length=255, blank=True, default='')
    city       = models.CharField(max_length=100)
    state      = models.CharField(max_length=100, blank=True, default='')
    postcode   = models.CharField(max_length=20)
    country    = models.CharField(max_length=100, default='United Kingdom')
    phone      = models.CharField(max_length=30, blank=True, default='')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f'{self.full_name}, {self.line1}, {self.city}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(
                user=self.user, type=self.type, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# ── Catalogue ──────────────────────────────────────────────────────────────────

class Category(models.Model):
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(unique=True)
    description = models.TextField(blank=True, default='')
    image       = models.ImageField(upload_to='categories/', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Vendor(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    store_name      = models.CharField(max_length=200)
    description     = models.TextField(blank=True, default='')
    email           = models.EmailField(max_length=254, blank=True, default='')
    phone           = models.CharField(max_length=30, blank=True, default='')
    address         = models.TextField(blank=True, default='')
    logo            = models.ImageField(upload_to='vendors/logos/', blank=True, null=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    payout_method   = models.CharField(max_length=50, blank=True, default='',
                                       help_text='flutterwave | paypal | mobile_money | bank_transfer')
    payout_details  = models.JSONField(default=dict, blank=True,
                                       help_text='Gateway-specific account details')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.store_name

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED


class VendorVerification(Vendor):
    """Proxy used to expose the pending-vendor review queue in Django admin."""

    class Meta:
        proxy = True
        verbose_name = 'Verify vendor'
        verbose_name_plural = 'Verify vendors'


class Product(models.Model):
    category         = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    vendor           = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products',
                                         null=True, blank=True)
    name             = models.CharField(max_length=200)
    slug             = models.SlugField(unique=True)
    description      = models.TextField()
    price            = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock            = models.PositiveIntegerField(default=0)
    image            = models.ImageField(upload_to='products/', blank=True, null=True)
    # e.g. {"sizes": ["S","M","L"], "colors": ["black","white"], "brand": "Nike"}
    attributes       = models.JSONField(default=dict, blank=True)
    shipping_days    = models.PositiveSmallIntegerField(default=3, help_text='Estimated days to ship')
    is_featured      = models.BooleanField(default=False)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def avg_rating(self):
        agg = self.reviews.filter(is_visible=True).aggregate(avg=models.Avg('rating'))
        return round(agg['avg'] or 0, 1)


# ── Orders ─────────────────────────────────────────────────────────────────────

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('shipped',    'Shipped'),
        ('delivered',  'Delivered'),
        ('cancelled',  'Cancelled'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('flutterwave',  'Flutterwave'),
        ('paypal',       'PayPal'),
        ('mobile_money', 'Mobile Money'),
        ('stripe',       'Stripe'),
        ('cod',          'Cash on Delivery'),
    ]

    user                       = models.ForeignKey(User, on_delete=models.SET_NULL,
                                                   null=True, blank=True, related_name='orders')
    customer_name              = models.CharField(max_length=200)
    customer_email             = models.EmailField(max_length=254, blank=True, default='')
    customer_phone             = models.CharField(max_length=30, blank=True, default='')
    customer_address           = models.TextField(blank=True, null=True)
    # Frozen snapshot of the shipping address at checkout time
    shipping_address           = models.JSONField(default=dict, blank=True)
    order_date                 = models.DateTimeField(auto_now_add=True)
    status                     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method             = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES,
                                                  blank=True, default='')
    flutterwave_transaction_id = models.CharField(max_length=128, blank=True, default='')
    subtotal                   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost              = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    tax_amount                 = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    total_price                = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loyalty_points_earned      = models.PositiveIntegerField(default=0)
    loyalty_points_used        = models.PositiveIntegerField(default=0)
    notes                      = models.TextField(blank=True, default='')

    def __str__(self):
        who = self.customer_name or (self.user.username if self.user else 'Guest')
        return f'Order #{self.id} — {who}'


class Shipment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SHIPPED = 'shipped'
    STATUS_IN_TRANSIT = 'in_transit'
    STATUS_DELIVERED = 'delivered'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_IN_TRANSIT, 'In transit'),
        (STATUS_DELIVERED, 'Delivered'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    tracking_number = models.CharField(max_length=32, unique=True, db_index=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    estimated_arrival = models.DateField(blank=True, null=True)
    current_location = models.CharField(max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.tracking_number} for order #{self.order_id}'

    @classmethod
    def generate_tracking_number(cls):
        # UUID-derived values make guessing a customer's shipment impractical.
        return f'HFS-{uuid.uuid4().hex[:16].upper()}'

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_tracking_number()
        super().save(*args, **kwargs)


class VendorOrder(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('shipped',    'Shipped'),
        ('delivered',  'Delivered'),
        ('cancelled',  'Cancelled'),
    ]

    order           = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='vendor_orders')
    vendor          = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='vendor_orders')
    subtotal        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vendor_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tracking_number = models.CharField(max_length=128, blank=True, default='')
    shipped_at      = models.DateTimeField(blank=True, null=True)
    delivered_at    = models.DateTimeField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('order', 'vendor')

    def __str__(self):
        return f'VendorOrder order={self.order_id} vendor={self.vendor_id}'

    def save(self, *args, **kwargs):
        if self.subtotal and self.vendor_id:
            rate = self.vendor.commission_rate / 100
            self.vendor_earnings = self.subtotal * (1 - rate)
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price    = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def vendor(self):
        return self.product.vendor

    def __str__(self):
        return f'{self.quantity}x {self.product.name}'


# ── Cart ───────────────────────────────────────────────────────────────────────

class Cart(models.Model):
    # A signed-in customer has one durable cart. Guest carts use session_key
    # until they are merged into the customer's cart at login.
    user       = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cart',
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def cart_total(self):
        return sum(item.subtotal for item in self.items.select_related('product').all())

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        if not self.user_id:
            return f'Guest cart {self.session_key or self.pk}'
        return f'Cart — {self.user.username}'


class CartItem(models.Model):
    cart     = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f'{self.quantity}× {self.product.name}'


# ── Wishlist ───────────────────────────────────────────────────────────────────

class WishlistItem(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.user.username} ♥ {self.product.name}'


# ── Reviews ────────────────────────────────────────────────────────────────────

class ProductReview(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='product_reviews')
    rating     = models.PositiveSmallIntegerField(default=5, help_text='1–5 stars')
    title      = models.CharField(max_length=120, blank=True, default='')
    body       = models.TextField(blank=True, default='')
    reply      = models.TextField(blank=True, default='')
    replied_at = models.DateTimeField(blank=True, null=True)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'user')

    def __str__(self):
        return f'Review product={self.product_id} user={self.user_id} rating={self.rating}'


class ProductReviewReport(models.Model):
    REASON_SPAM      = 'spam'
    REASON_OFFENSIVE = 'offensive'
    REASON_FAKE      = 'fake'
    REASON_OTHER     = 'other'
    REASON_CHOICES   = [
        (REASON_SPAM,      'Spam'),
        (REASON_OFFENSIVE, 'Offensive'),
        (REASON_FAKE,      'Fake Review'),
        (REASON_OTHER,     'Other'),
    ]

    review     = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='reports')
    reporter   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='review_reports')
    reason     = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_OTHER)
    details    = models.TextField(blank=True, default='')
    resolved   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('review', 'reporter')
        ordering = ['-created_at']

    def __str__(self):
        return f'Report review={self.review_id} by={self.reporter_id}'


# ── Support ────────────────────────────────────────────────────────────────────

class SupportTicket(models.Model):
    TYPE_GENERAL = 'general'
    TYPE_ORDER   = 'order'
    TYPE_RETURN  = 'return'
    TYPE_REFUND  = 'refund'
    TYPE_CHOICES = [
        (TYPE_GENERAL, 'General Enquiry'),
        (TYPE_ORDER,   'Order Issue'),
        (TYPE_RETURN,  'Return Request'),
        (TYPE_REFUND,  'Refund Request'),
    ]
    STATUS_OPEN        = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED    = 'resolved'
    STATUS_CLOSED      = 'closed'
    STATUS_CHOICES     = [
        (STATUS_OPEN,        'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED,    'Resolved'),
        (STATUS_CLOSED,      'Closed'),
    ]

    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='support_tickets')
    order      = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='support_tickets')
    type       = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    subject    = models.CharField(max_length=200)
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Ticket #{self.id} — {self.subject}'


class SupportMessage(models.Model):
    ticket     = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='support_messages')
    body       = models.TextField()
    attachment = models.FileField(upload_to='support/attachments/', blank=True, null=True)
    is_staff   = models.BooleanField(default=False,
                                     help_text='True when the message is sent by admin/staff')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'SupportMessage ticket={self.ticket_id} sender={self.sender_id}'


# ── Loyalty ────────────────────────────────────────────────────────────────────

class LoyaltyTransaction(models.Model):
    TYPE_EARN   = 'earn'
    TYPE_SPEND  = 'spend'
    TYPE_ADJUST = 'adjust'
    TYPE_CHOICES = [
        (TYPE_EARN,   'Earned'),
        (TYPE_SPEND,  'Spent'),
        (TYPE_ADJUST, 'Manual Adjustment'),
    ]

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loyalty_transactions')
    order         = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='loyalty_transactions')
    type          = models.CharField(max_length=10, choices=TYPE_CHOICES)
    points        = models.IntegerField(help_text='Positive = earned, negative = spent/adjusted')
    balance_after = models.PositiveIntegerField(help_text='Running balance after this transaction')
    note          = models.CharField(max_length=200, blank=True, default='')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Loyalty user={self.user_id} {self.type} {self.points:+d}'


# ── Analytics ──────────────────────────────────────────────────────────────────

class ProductView(models.Model):
    """Tracks product page views for analytics."""
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='views')
    viewed_at  = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=64, blank=True, default='')

    def __str__(self):
        return f'ProductView product={self.product_id} at={self.viewed_at}'


# ── Auth / OTP ─────────────────────────────────────────────────────────────────

class OTPVerification(models.Model):
    PURPOSE_SIGNUP          = 'signup'
    PURPOSE_FORGOT_PASSWORD = 'forgot_password'
    PURPOSE_CHOICES         = [
        (PURPOSE_SIGNUP,          PURPOSE_SIGNUP),
        (PURPOSE_FORGOT_PASSWORD, PURPOSE_FORGOT_PASSWORD),
    ]

    email      = models.EmailField(max_length=254, db_index=True)
    purpose    = models.CharField(max_length=32, choices=PURPOSE_CHOICES, db_index=True)
    otp_hash   = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts   = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'OTP Verification'
        verbose_name_plural = 'OTP Verifications'
        indexes = [
            models.Index(fields=['email', 'purpose'], name='store_otpve_email_90141a_idx'),
        ]

    def __str__(self):
        return f'OTPVerification email={self.email} purpose={self.purpose}'


# ── Vendor extended models ─────────────────────────────────────────────────────

class VendorStaffMember(models.Model):
    ROLE_OWNER   = 'owner'
    ROLE_MANAGER = 'manager'
    ROLE_STAFF   = 'staff'
    ROLE_CHOICES = [
        (ROLE_OWNER,   'Owner'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_STAFF,   'Staff'),
    ]

    vendor     = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='staff_members')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendor_staff_roles')
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STAFF)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'user')
        ordering = ['vendor', 'role']

    def __str__(self):
        return f'{self.user.username} @ {self.vendor.store_name} ({self.role})'


class VendorDocument(models.Model):
    DOC_REGISTRATION = 'registration'
    DOC_TAX          = 'tax'
    DOC_ID           = 'identity'
    DOC_OTHER        = 'other'
    DOC_CHOICES      = [
        (DOC_REGISTRATION, 'Business Registration'),
        (DOC_TAX,          'Tax Certificate'),
        (DOC_ID,           'Identity Document'),
        (DOC_OTHER,        'Other'),
    ]
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    vendor      = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='documents')
    doc_type    = models.CharField(max_length=20, choices=DOC_CHOICES, default=DOC_OTHER)
    file        = models.FileField(upload_to='vendors/documents/')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_vendor_docs')
    reviewed_at = models.DateTimeField(blank=True, null=True)
    notes       = models.TextField(blank=True, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.vendor.store_name} — {self.doc_type}'


class VendorPayout(models.Model):
    STATUS_REQUESTED  = 'requested'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED  = 'completed'
    STATUS_FAILED     = 'failed'
    STATUS_CHOICES    = [
        (STATUS_REQUESTED,  'Requested'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED,  'Completed'),
        (STATUS_FAILED,     'Failed'),
    ]
    METHOD_CHOICES = [
        ('flutterwave',   'Flutterwave'),
        ('paypal',        'PayPal'),
        ('mobile_money',  'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    vendor         = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payouts')
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    method         = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    reference      = models.CharField(max_length=128, blank=True, default='')
    payout_details = models.JSONField(default=dict, blank=True)
    requested_at   = models.DateTimeField(auto_now_add=True)
    processed_at   = models.DateTimeField(blank=True, null=True)
    notes          = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f'Payout #{self.id} — {self.vendor.store_name} — {self.amount}'


class VendorNotification(models.Model):
    TYPE_NEW_ORDER = 'new_order'
    TYPE_LOW_STOCK = 'low_stock'
    TYPE_PAYMENT   = 'payment'
    TYPE_PAYOUT    = 'payout'
    TYPE_REVIEW    = 'review'
    TYPE_SYSTEM    = 'system'
    TYPE_CHOICES   = [
        (TYPE_NEW_ORDER, 'New Order'),
        (TYPE_LOW_STOCK, 'Low Stock'),
        (TYPE_PAYMENT,   'Payment Confirmed'),
        (TYPE_PAYOUT,    'Payout Update'),
        (TYPE_REVIEW,    'New Review'),
        (TYPE_SYSTEM,    'System'),
    ]

    vendor     = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='notifications')
    type       = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    title      = models.CharField(max_length=200)
    body       = models.TextField(blank=True, default='')
    is_read    = models.BooleanField(default=False)
    link       = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'VendorNotification vendor={self.vendor_id} type={self.type}'


# ── Refunds ───────────────────────────────────────────────────────────────────

class Refund(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_APPROVED  = 'approved'
    STATUS_REJECTED  = 'rejected'
    STATUS_PROCESSED = 'processed'
    STATUS_CHOICES   = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_APPROVED,  'Approved'),
        (STATUS_REJECTED,  'Rejected'),
        (STATUS_PROCESSED, 'Processed'),
    ]

    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    customer   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='refunds')
    vendor     = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='refunds')
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reason     = models.TextField()
    notes      = models.TextField(blank=True, default='')
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Refund #{self.id} order={self.order_id} status={self.status}'


# ── Admin roles ────────────────────────────────────────────────────────────────

class AdminProfile(models.Model):
    ROLE_SUPER_ADMIN     = 'super_admin'
    ROLE_PRODUCT_MANAGER = 'product_manager'
    ROLE_ORDER_MANAGER   = 'order_manager'
    ROLE_CHOICES         = [
        (ROLE_SUPER_ADMIN,     'Super Admin'),
        (ROLE_PRODUCT_MANAGER, 'Product Manager'),
        (ROLE_ORDER_MANAGER,   'Order Manager'),
    ]

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    role       = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_ORDER_MANAGER)
    avatar     = models.ImageField(upload_to='admins/avatars/', blank=True, null=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'
