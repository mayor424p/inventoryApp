from django.contrib import admin
from . import models
from django.utils.html import format_html



admin.site.register(models.Category)
admin.site.register(models.Location)

admin.site.register(models.Inventory)
admin.site.register(models.Supplier)
admin.site.register(models.Staff)
admin.site.register(models.Transaction)
admin.site.register(models.TransactionItem)
admin.site.register(models.Refund)
admin.site.register(models.PurchaseOrder)
admin.site.register(models.PurchaseOrderItem)
# Register your models here.


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    
    readonly_fields = ('sku','barcode_image') # Add other fields here if needed
    
    list_display = ('name', 'category', 'price', 'quantity', 'location', 'expiry_date', 'sku', 'barcode_image_tag')

    def barcode_image_tag(self, obj):
        if obj.barcode_image:
            
            return format_html('<img src="{}" alt="Barcode for {}" style="max-width: 150px; max-height: 150px;"/>', obj.barcode_image.url, obj.name)
        return""
    barcode_image_tag.short_description = "Barcode Image"

  
