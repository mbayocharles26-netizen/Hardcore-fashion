from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Product, Order, OrderItem, Vendor, VendorOrder, Cart, CartItem, Shipment


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'store_name', 'description', 'email', 'status', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    vendor = VendorSerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'stock', 'image',
            'category', 'category_name', 'vendor', 'created_at'
        ]
        extra_kwargs = {
            'name':        {'max_length': 200},
            'slug':        {'max_length': 200},
            'description': {'max_length': 5000},
            'price':       {'max_digits': 10, 'decimal_places': 2, 'min_value': 0},
            'stock':       {'min_value': 0},
        }


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'vendor', 'quantity', 'price']

    def get_vendor(self, obj):
        if not getattr(obj, 'product', None) or not obj.product.vendor_id:
            return None
        return VendorSerializer(obj.product.vendor).data


class VendorOrderSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    items = serializers.SerializerMethodField()

    def get_items(self, obj):
        qs = obj.order.items.select_related('product__category', 'product__vendor')
        qs = [i for i in qs.all() if i.product_id and i.product.vendor_id == obj.vendor_id]
        return OrderItemSerializer(qs, many=True).data


    class Meta:
        model = VendorOrder
        fields = ['id', 'order', 'vendor', 'subtotal', 'status', 'created_at', 'items']


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ['tracking_number', 'status', 'estimated_arrival', 'current_location', 'updated_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    vendor_orders = VendorOrderSerializer(many=True, read_only=True)
    shipment = ShipmentTrackingSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'status', 'total_price', 'items', 'vendor_orders', 'shipment', 'order_date']



class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_name', 'product_price', 'quantity', 'subtotal']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'items', 'created_at']
