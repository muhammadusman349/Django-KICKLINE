"""
URL configuration for leads app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'tasks', views.ScrapingTaskViewSet, basename='scrapingtask')

urlpatterns = [
    # Router URLs (ViewSets)
    path('', include(router.urls)),
    
    # Async scraping endpoints
    path('scrape/', views.SearchScrapeAPIView.as_view(), name='scrape'),
    path('scrape/bulk/', views.BulkScrapeAPIView.as_view(), name='scrape-bulk'),
    
    # Email validation
    path('validate-emails/', views.ValidateEmailsAPIView.as_view(), name='validate-emails'),
    
    # Celery task status
    path('tasks/<str:task_id>/status/', views.CeleryTaskStatusAPIView.as_view(), name='task-status'),
    
    # Legacy endpoints (for backward compatibility)
    path('search-leads/', views.LeadSearchAPIView.as_view(), name='search-leads'),
    path('quick-search/', views.LeadQuickSearchAPIView.as_view(), name='quick-search'),
    
    # NEW: Manual selection endpoints (search only, then scrape individually)
    path('search/', views.SearchCompaniesAPIView.as_view(), name='search-companies'),
    path('scrape/single/', views.ScrapeSingleCompanyAPIView.as_view(), name='scrape-single'),
    path('scrape/single/sync/', views.QuickScrapeSingleAPIView.as_view(), name='scrape-single-sync'),
]
