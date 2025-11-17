from rest_framework import serializers
from .models import Inventory, Location, Category, Product, Supplier, Staff, Transaction, TransactionItem, Refund, PurchaseOrder, PurchaseOrderItem

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.CharField()

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['barcode', 'sku', 'barcode_image']  

    def create(self, validated_data):
        category_name = validated_data.pop('category')
        category, _ = Category.objects.get_or_create(name=category_name.strip())
        product = Product.objects.create(category=category, **validated_data)
        return product
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['category']= instance.category.name
        return rep
    
   

class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku = serializers.CharField(source='product.sku', read_only=True)
    category = serializers.CharField(source='product.category.name', read_only=True)
    price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    #supplier = serializers.CharField(source='product.supplier.name', read_only=True)
    last_updated = serializers.DateTimeField(source='product.date_added', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    barcode_image = serializers.ImageField(source='product.barcode_image', read_only=True) # Add this line
    product_expiry_date = serializers.DateTimeField(source='product.expiry_date', read_only=True)




    class Meta:
        model = Inventory 
        fields = [
            'id',
            'product',
            'location',
            'quantity',
            'sku',
            'category',
            'price',
            
            'last_updated',
            'location_name',
            'product_name',
            'barcode_image',
            'product_expiry_date',
        ]

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

class StaffSerializer(serializers.ModelSerializer):
    

    class Meta:
        model = Staff
        fields = '__all__'

class TransactionItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = TransactionItem
        fields = ['product_name', 'quantity_sold', 'price_at_time_of_sale', 'subtotal']

class TransactionSerializer(serializers.ModelSerializer):
    items = TransactionItemSerializer(many=True, read_only=True)
    staff_name = serializers.CharField(source='staff.name', read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'transaction_id', 'date_time', 'staff_name', 'total_amount', 'payment_method', 'status', 'items']

class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = '__all__'

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'

class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'