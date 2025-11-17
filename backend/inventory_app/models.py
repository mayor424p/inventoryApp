from django.db import models
import time
from django.core.files.base import ContentFile
import qrcode
from io import BytesIO
from django.contrib.auth.models import User
import uuid


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    

class Location(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    

class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='products')
    date_added = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True, null=True)
    barcode = models.CharField(max_length=100, unique=True, blank=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if not self.sku:
            self.sku = f"PROD-{int(time.time())}-{str(uuid.uuid4()).split('-')[-1][:8].upper()}"

            if not self.barcode:
                self.barcode = self.sku
        
       
        super().save(*args, **kwargs)

        if is_new and self.barcode and not self.barcode_image:
            try:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=4,
                    border=4
                )
                qr.add_data(self.barcode)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                filename = f"barcode_{self.barcode}.png"
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                buffer.seek(0)

                if self.barcode_image:
                    self.barcode_image.delete(save=False)

                    
                self.barcode_image.save(filename, ContentFile(buffer.read()), save=False)
                buffer.close()

                super().save(update_fields=['barcode_image'])

            except Exception as e:
                print(f"Error generating barcode image for product {self.id}: {e}")
                raise e
        

       
class Inventory(models.Model):
    STATUS_CHOICES = [
        ('IN STOCK', 'In Stock'),
        ('LOW STOCK', 'Low Stock'),
        ('OUT OF STOCK', 'Out of Stock'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    quantity_resevered=models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN STOCK')

    class Meta:
        unique_together = ('product', 'location')

    def available_quantity(self):
        return self.quantity - self.quantity_resevered
    
    def update_status(self):
        if self.quantity == 0:
            self.status = 'OUT OF STOCK'
        elif self.quantity < 10:
            self.status = "LOW STOCK"
        else:
            self.status = 'IN STOCK'
        self.save(update_fields=['status'])

    
    def __str__(self):
        return f"{self.product.name} at {self.location.name}: {self.quantity} ({self.status})"

    
class Supplier(models.Model):
    name = models.CharField(max_length=50)
    products_supplied = models.JSONField(default=list)
    brand_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    address = models.CharField(max_length=255, blank=True, null=True)


    def __str__(self):

        return f"{self.company_name or self.name} ({self.brand_name or 'No Brand'})"
    

class Staff(models.Model):
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    ]


    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    department = models.CharField(max_length=100, default="General")
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hire_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default="active")

    def __str__(self):
        return f"{self.name} ({self.role})"
    

class Transaction(models.Model):
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('MOBILE', 'Mobile Payment'),
    ]
    transaction_id = models.CharField(max_length=100, unique=True)
    date_time = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"sale {self.transaction_id} - {self.total_amount}"
    

class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_sold = models.PositiveIntegerField()
    price_at_time_of_sale = models.DecimalField(max_digits=10, decimal_places=2) # Price snapshot
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity_sold} x {self.product.name} in {self.transaction.transaction_id}"
    

class Refund(models.Model): # Represents a return/refund
    original_transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_returned = models.PositiveIntegerField()
    reason = models.TextField() # e.g., "Defective", "Wrong Item"
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_time = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Refund for {self.original_transaction.transaction_id} - {self.product.name}"
    

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    po_number = models.CharField(max_length=100, unique=True) # Generate unique PO number
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True) # Who created the PO

    def __str__(self):
        return f"PO {self.po_number} - {self.supplier.name}"
    
class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_ordered = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity_ordered} x {self.product.name} in {self.purchase_order.po_number}"

# Create your models here.
