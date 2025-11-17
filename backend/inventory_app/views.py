# backend/inventory_app/views.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction # For atomic operations during sales/refunds
from . import models, serializers
from django.db.models import Sum, Count
from datetime import timedelta
from django.utils import timezone

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = models.Category.objects.all()
    serializer_class = serializers.CategorySerializer
    permission_classes = [permissions.IsAuthenticated] # Consider adding permissions later

class LocationViewSet(viewsets.ModelViewSet):
    queryset = models.Location.objects.all()
    serializer_class = serializers.LocationSerializer
    permission_classes = [permissions.IsAuthenticated]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = models.Product.objects.all()
    serializer_class = serializers.ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()  # Serializer handles category creation now

        # Optional: create Inventory entry for this product
        location_id = request.data.get('location')
        quantity = request.data.get('quantity', 0)

        if location_id:
            location = models.Location.objects.get(pk=location_id)
            models.Inventory.objects.create(
                product=product,
                location=location,
                quantity=quantity
            )
        supplier_id = request.data.get('supplier')
        if supplier_id:
            try:
                supplier = models.Supplier.objects.get(pk=supplier_id)
                # Avoid duplicates

                if not isinstance(supplier.products_supplied, list):
                    supplier.products_supplied = []
                    
                if product.name not in supplier.products_supplied:
                    supplier.products_supplied.append(product.name)
                    supplier.save(update_fields=['products_supplied'])
            except models.Supplier.DoesNotExist:
                pass  # supplier is optional, skip if not 

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
     
class InventoryViewSet(viewsets.ModelViewSet):
    """
    Manage inventory records — supports CRUD and bulk delete.
    """
    queryset = models.Inventory.objects.select_related('product', 'product__category', 'location')
    serializer_class = serializers.InventorySerializer
    permission_classes = [permissions.IsAuthenticated]

    # DELETE /inventory/delete_all/
    @action(detail=False, methods=['delete'], url_path='delete_all')
    def delete_all(self, request):
        count = self.queryset.count()
        self.queryset.delete()
        return Response(
            {"message": f"Deleted all ({count}) inventory items."},
            status=status.HTTP_204_NO_CONTENT
        )

    # DELETE /inventory/<id>/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        product_name = instance.product.name if hasattr(instance, "product") else "Unknown"
        self.perform_destroy(instance)
        return Response(
            {"message": f"Inventory item for '{product_name}' deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = models.Supplier.objects.all()
    serializer_class = serializers.SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]

class StaffViewSet(viewsets.ModelViewSet):
    queryset = models.Staff.objects.all()
    serializer_class = serializers.StaffSerializer
    permission_classes = [permissions.IsAuthenticated]

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = models.Transaction.objects.all()
    serializer_class = serializers.TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def create_sale(self, request):
        """
        Handle POS sale creation.
        Expects JSON:
        {
            "items": [{"product_id": 1, "quantity": 2}, ...],
            "payment_method": "CASH",
            "staff_id": 1,
            "location_id": 2   # optional, defaults to first location
        }
        """
        items_data = request.data.get('items', [])
        payment_method = request.data.get('payment_method')
        staff_id = request.data.get('staff_id')
        location_id = request.data.get('location_id')

        # ✅ Validate inputs
        if not items_data or not payment_method:
            return Response(
                {"error": "Items, payment method, and staff ID are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Determine location (required for inventory lookup)
        if location_id:
            location = get_object_or_404(models.Location, pk=location_id)
        else:
            location = models.Location.objects.first()
            if not location:
                return Response(
                    {"error": "No location found. Please add at least one location."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        total_amount = 0
        transaction_items_to_create = []
        inventory_updates = []

        # ✅ Check inventory and calculate totals
        for item_data in items_data:
            product_id = item_data.get('product_id')
            requested_quantity = item_data.get('quantity')

            if not product_id or requested_quantity <= 0:
                return Response(
                    {"error": f"Invalid item: {item_data}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ✅ Ensure the product exists in inventory for this location
            try:
                inventory_item = models.Inventory.objects.select_for_update().get(
                    product_id=product_id,
                    location=location
                )
            except models.Inventory.DoesNotExist:
                return Response(
                    {"error": f"Product {product_id} not found in inventory for location '{location.name}'."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # ✅ Ensure enough stock
            if inventory_item.available_quantity() < requested_quantity:
                return Response(
                    {"error": f"Insufficient stock for product {product_id}. "
                            f"Available: {inventory_item.available_quantity()}, "
                            f"Requested: {requested_quantity}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ✅ Compute totals
            product = inventory_item.product
            item_subtotal = product.price * requested_quantity
            total_amount += item_subtotal

            transaction_items_to_create.append({
                'product': product,
                'quantity_sold': requested_quantity,
                'price_at_time_of_sale': product.price,
                'subtotal': item_subtotal
            })

            inventory_updates.append({
                'inventory_item': inventory_item,
                'quantity_sold': requested_quantity
            })

        # ✅ Create transaction atomically
        try:
            with transaction.atomic():
                import uuid
                transaction_id = str(uuid.uuid4())

                # Create Transaction
                transaction_obj = models.Transaction.objects.create(
                    transaction_id=transaction_id,
                    total_amount=total_amount,
                    payment_method=payment_method,
                    status='COMPLETED',
                    staff_id=staff_id if staff_id else None
                )

                # Create Transaction Items
                for item_data in transaction_items_to_create:
                    models.TransactionItem.objects.create(
                        transaction=transaction_obj,
                        product=item_data['product'],
                        quantity_sold=item_data['quantity_sold'],
                        price_at_time_of_sale=item_data['price_at_time_of_sale'],
                        subtotal=item_data['subtotal']
                    )

                # Update Inventory
                for update_data in inventory_updates:
                    inventory_item = update_data['inventory_item']
                    inventory_item.quantity -= update_data['quantity_sold']

                    # ✅ Update stock status automatically
                    inventory_item.quantity -= update_data['quantity_sold']
                    inventory_item.update_status()

        except Exception as e:
            print(f"Error creating sale: {e}")
            return Response(
                {"error": "An error occurred while processing the sale."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ✅ Success response
        serializer = self.get_serializer(transaction_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post']) # detail=True means it acts on a specific transaction ID (pk)
    def process_refund(self, request, pk=None):
        """
        Custom action to handle refunds.
        Expects: { "items": [{"product_id": 1, "quantity_returned": 1, "reason": "Defective"}, ...], "processed_by_staff_id": 1 }
        """
        original_transaction = get_object_or_404(models.Transaction, id=pk)

        # Prevent refunding a cancelled transaction
        if original_transaction.status == 'cancelled':
            return Response({"error": "Cannot refund a cancelled transaction."}, status=status.HTTP_400_BAD_REQUEST)

        items_data = request.data.get('items', [])
        processed_by_staff_id = request.data.get('processed_by_staff_id')

        if not items_data: # or not processed_by_staff_id:
            return Response({"error": "Refund items and processed_by_staff_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: Get staff object
        # processed_by_staff = get_object_or_404(models.Staff, id=processed_by_staff_id)

        total_refunded = 0
        inventory_updates = []

        for item_data in items_data:
            product_id = item_data.get('product_id')
            quantity_returned = item_data.get('quantity_returned')
            reason = item_data.get('reason', 'N/A')

            if not product_id or quantity_returned <= 0:
                return Response({"error": f"Invalid refund item  {item_data}"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the product was part of the original transaction
            original_item = models.TransactionItem.objects.filter(
                transaction=original_transaction, product_id=product_id
            ).first()

            if not original_item:
                return Response({"error": f"Product {product_id} was not part of transaction {pk}."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if returned quantity doesn't exceed sold quantity
            if quantity_returned > original_item.quantity_sold:
                 return Response({"error": f"Return quantity ({quantity_returned}) for product {product_id} exceeds quantity sold ({original_item.quantity_sold}) in transaction {pk}."}, status=status.HTTP_400_BAD_REQUEST)

            # Calculate refunded amount for this item
            item_refund_amount = original_item.price_at_time_of_sale * quantity_returned
            total_refunded += item_refund_amount

            # Prepare inventory update
            try:
                inventory_item = models.Inventory.objects.select_for_update().get(
                    product_id=product_id, location_id=1 # Assuming 'Main Store' location ID is 1
                )
                inventory_updates.append({
                    'inventory_item': inventory_item,
                    'quantity_returned': quantity_returned
                })
            except models.Inventory.DoesNotExist:
                return Response({"error": f"Product {product_id} not found in inventory for this location."}, status=status.HTTP_404_NOT_FOUND)

        # 3. Create Refund and update Inventory/Transaction atomically
        try:
            with transaction.atomic():
                for item_data in items_data:
                    product_id = item_data['product_id']
                    quantity_returned = item_data['quantity_returned']
                    reason = item_data['reason']

                    # Create Refund record
                    models.Refund.objects.create(
                        original_transaction=original_transaction,
                        product_id=product_id,
                        quantity_returned=quantity_returned,
                        reason=reason,
                        refunded_amount=original_item.price_at_time_of_sale * quantity_returned, # Use price from original item
                        # processed_by=processed_by_staff # Assign staff if validated
                    )

                # Update Inventory quantities
                for update_data in inventory_updates:
                    inventory_item = update_data['inventory_item']
                    inventory_item.quantity += update_data['quantity_returned'] # Increase quantity
                    inventory_item.save()

                # Optional: Update original Transaction status if fully refunded? (Logic depends on requirements)

        except Exception as e:
            # Log the error if using logging
            print(f"Error processing refund: {e}") # Replace with logging
            return Response({"error": "An error occurred while processing the refund."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. Return success response
        return Response({"message": f"Refund processed successfully for transaction {pk}. Total refunded: {total_refunded}"}, status=status.HTTP_200_OK)

class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Returns summarized sales and stock metrics for the dashboard.
        """
        now = timezone.now()
        week_start = now - timedelta(days=7)
        month_start = now.replace(day=1)
        year_start = now.replace(month=1, day=1)

        weekly_sales = (
            models.Transaction.objects
            .filter(date_time__gte=week_start, status='COMPLETED')
            .aggregate(total=Sum('total_amount'))['total'] or 0
        )

        monthly_sales = (
            models.Transaction.objects
            .filter(date_time__gte=month_start, status='COMPLETED')
            .aggregate(total=Sum('total_amount'))['total'] or 0
        )

        yearly_sales = (
            models.Transaction.objects
            .filter(date_time__gte=year_start, status='COMPLETED')
            .aggregate(total=Sum('total_amount'))['total'] or 0
        )

        low_stock = models.Inventory.objects.filter(quantity__lte=10).count()

        data = {
            "weekly_sales": float(weekly_sales),
            "monthly_sales": float(monthly_sales),
            "yearly_sales": float(yearly_sales),
            "weekly_change": 12,
            "monthly_change": 8,
            "yearly_change": 10,
            "low_stock_count": low_stock,
        }

        return Response(data)

    @action(detail=False, methods=['get'])
    def charts(self, request):
        """
        Returns chart data for:
         - High demand products
         - Low demand products
         - Seasonal sales trends
        """
        # 🔹 High demand
        high_demand = (
            models.TransactionItem.objects
            .values('product__name')
            .annotate(sales=Sum('quantity_sold'))
            .order_by('-sales')[:5]
        )

        # 🔹 Low demand
        low_demand = (
            models.TransactionItem.objects
            .values('product__name')
            .annotate(sales=Sum('quantity_sold'))
            .order_by('sales')[:5]
        )

        # 🔹 Seasonal (monthly)
        now = timezone.now()
        months = []
        for i in range(6):
            month_start = (now - timedelta(days=30 * i)).replace(day=1)
            next_month_start = (month_start + timedelta(days=32)).replace(day=1)
            sales_total = (
                models.Transaction.objects
                .filter(date_time__gte=month_start, date_time__lt=next_month_start)
                .aggregate(total=Sum('total_amount'))['total'] or 0
            )
            months.append({
                "month": month_start.strftime("%b"),
                "sales": float(sales_total)
            })

        data = {
            "high_demand": [{"product": h["product__name"], "sales": h["sales"]} for h in high_demand],
            "low_demand": [{"product": l["product__name"], "sales": l["sales"]} for l in low_demand],
            "seasonal": list(reversed(months))
        }

        return Response(data)

        

class RefundViewSet(viewsets.ReadOnlyModelViewSet): # Usually read-only after creation via Transaction action
    queryset = models.Refund.objects.all()
    serializer_class = serializers.RefundSerializer
    permission_classes = [permissions.IsAuthenticated]

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = models.PurchaseOrder.objects.all()
    serializer_class = serializers.PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post']) # Acts on a specific PO ID (pk)
    def receive_order(self, request, pk=None):
        """
        Custom action to receive a purchase order and update inventory.
        """
        po = get_object_or_404(models.PurchaseOrder, id=pk)

        if po.status != 'pending':
            return Response({"error": f"Cannot receive order {pk}. Status is '{po.status}', expected 'pending'."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Update Inventory quantities based on PO items
        try:
            with transaction.atomic():
                for po_item in po.items.all(): # Use the related manager
                    inventory_item, created = models.Inventory.objects.get_or_create(
                        product=po_item.product,
                        location_id=1, # Assuming items go to 'Main Store' location ID 1
                        defaults={'quantity': 0} # If new inventory record, start with 0
                    )
                    inventory_item.quantity += po_item.quantity_ordered
                    inventory_item.save()

                # 3. Update PO status
                po.status = 'received'
                po.save()

        except Exception as e:
            # Log the error if using logging
            print(f"Error receiving order {pk}: {e}") # Replace with logging
            return Response({"error": "An error occurred while receiving the order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. Return success response
        serializer = self.get_serializer(po)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TransactionItemViewSet(viewsets.ReadOnlyModelViewSet): # Usually read-only, created via Transaction
    queryset = models.TransactionItem.objects.all()
    serializer_class = serializers.TransactionItemSerializer
    permission_classes = [permissions.IsAuthenticated]

class PurchaseOrderItemViewSet(viewsets.ReadOnlyModelViewSet): # Usually read-only, created via PurchaseOrder
    queryset = models.PurchaseOrderItem.objects.all()
    serializer_class = serializers.PurchaseOrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

# Notification ViewSet (if you add the Notification model later)
# class NotificationViewSet(viewsets.ModelViewSet):
#     queryset = models.Notification.objects.all()
#     serializer_class = serializers.NotificationSerializer
#     # permission_classes = [permissions.IsAuthenticated]