from django.urls import path
from . import views

app_name = 'Kickline'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('categories/', views.category_list, name='category_list'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('shipment/', views.shipment, name='shipment'),
    path('contact/', views.contact, name='contact'),
]
