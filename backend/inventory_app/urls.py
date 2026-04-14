from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import auth_views
from .views import AnalyticsViewSet

router = DefaultRouter()

router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'locations', views.LocationViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'inventory', views.InventoryViewSet)
router.register(r'suppliers', views.SupplierViewSet)
router.register(r'staff', views.StaffViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'transaction-items', views.TransactionItemViewSet)
router.register(r'refunds', views.RefundViewSet)
router.register(r'purchase-orders', views.PurchaseOrderViewSet)
router.register(r'purchase-order-items', views.PurchaseOrderItemViewSet)
router.register(r'analytics', AnalyticsViewSet, basename='analytics')


urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', auth_views.register_user, name='register'),
    path('auth/login/', auth_views.login_user, name='login'),
   
]
