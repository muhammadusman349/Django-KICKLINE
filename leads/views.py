
import os
from django.db import models
from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status, generics, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from .scrapers import CompanySearcher
from .utils import check_duplicate_website, normalize_url, prioritize_emails

from .models import Lead, ScrapingTask
from .tasks import (
    search_and_scrape_companies,
    bulk_scrape_from_queries,
    re_scrape_lead,
    validate_all_emails,
    export_leads_to_csv,
    cleanup_old_tasks,
    scrape_single_website,
)
from .utils import check_duplicate_website, normalize_url
from .serializers import (
    LeadListSerializer,
    LeadDetailSerializer,
    LeadCreateUpdateSerializer,
    ScrapingTaskSerializer,
    ScrapingTaskDetailSerializer,
    ScrapingRequestSerializer,
    BulkScrapingRequestSerializer,
    RescrapeRequestSerializer,
    LeadFilterSerializer,
    LeadExportSerializer,
    LeadSerializer,  # Backward compatibility
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list views"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LeadViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Leads with filtering and pagination.
    """
    queryset = Lead.objects.all()
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LeadCreateUpdateSerializer
        if self.action == 'retrieve':
            return LeadDetailSerializer
        return LeadListSerializer
    
    def get_queryset(self):
        """Apply filters from query parameters"""
        queryset = Lead.objects.all()
        
        # Parse filter serializer
        filter_serializer = LeadFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data
            
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('source'):
                queryset = queryset.filter(source=filters['source'])
            
            if filters.get('email_validated') is not None:
                queryset = queryset.filter(email_validated=filters['email_validated'])
            
            if filters.get('has_email') is not None:
                if filters['has_email']:
                    queryset = queryset.exclude(email__isnull=True).exclude(email='')
                else:
                    queryset = queryset.filter(Q(email__isnull=True) | Q(email=''))
            
            if filters.get('country'):
                queryset = queryset.filter(country__icontains=filters['country'])
            
            if filters.get('search'):
                search = filters['search']
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(email__icontains=search) |
                    Q(website__icontains=search) |
                    Q(country__icontains=search) |
                    Q(notes__icontains=search)
                )
            
            # Apply ordering
            order_by = filters.get('order_by', '-created_at')
            queryset = queryset.order_by(order_by)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new lead with duplicate checking"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        website = serializer.validated_data.get('website', '')
        
        # Check for duplicate
        if website and check_duplicate_website(website):
            return Response(
                {'error': 'Lead with this website already exists'},
                status=status.HTTP_409_CONFLICT
            )
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    @action(detail=True, methods=['post'])
    def rescrape(self, request, pk=None):
        """Re-scrape a specific lead for updated emails"""
        lead = self.get_object()
        max_pages = request.data.get('max_pages', 5)
        
        # Queue async task
        task = re_scrape_lead.delay(lead.id, max_pages=max_pages)
        
        return Response({
            'message': 'Re-scrape task queued',
            'task_id': task.id,
            'lead_id': lead.id,
        })
    
    @action(detail=False, methods=['post'])
    def bulk_rescrape(self, request):
        """Re-scrape multiple leads"""
        serializer = RescrapeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lead_ids = serializer.validated_data['lead_ids']
        max_pages = serializer.validated_data.get('max_pages', 5)
        
        # Queue tasks for each lead
        tasks = []
        for lead_id in lead_ids:
            task = re_scrape_lead.delay(lead_id, max_pages=max_pages)
            tasks.append(task.id)
        
        return Response({
            'message': f'Queued re-scrape for {len(lead_ids)} leads',
            'task_count': len(tasks),
            'tasks': tasks,
        })
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """Export leads to CSV"""
        serializer = LeadExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Queue export task
        task = export_leads_to_csv.delay(
            lead_ids=serializer.validated_data.get('lead_ids'),
            status=serializer.validated_data.get('status'),
            email_validated=serializer.validated_data.get('email_validated'),
        )
        
        return Response({
            'message': 'Export task queued',
            'task_id': task.id,
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get lead statistics"""
        total = Lead.objects.count()
        with_email = Lead.objects.exclude(email__isnull=True).exclude(email='').count()
        validated = Lead.objects.filter(email_validated=True).count()
        by_status = Lead.objects.values('status').annotate(count=models.Count('id'))
        by_source = Lead.objects.values('source').annotate(count=models.Count('id'))
        
        return Response({
            'total': total,
            'with_email': with_email,
            'without_email': total - with_email,
            'email_validated': validated,
            'by_status': list(by_status),
            'by_source': list(by_source),
        })


class ScrapingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View scraping tasks (read-only).
    """
    queryset = ScrapingTask.objects.all()
    serializer_class = ScrapingTaskSerializer
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ScrapingTaskDetailSerializer
        return ScrapingTaskSerializer
    
    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Clean up old completed tasks"""
        days = request.data.get('days', 30)
        task = cleanup_old_tasks.delay(days=days)
        
        return Response({
            'message': f'Cleanup task queued for tasks older than {days} days',
            'task_id': task.id,
        })


class SearchScrapeAPIView(generics.GenericAPIView):
    """
    Search for companies and scrape their websites for emails.
    Supports both synchronous and asynchronous execution.
    """
    serializer_class = ScrapingRequestSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        query = serializer.validated_data['query']
        max_results = serializer.validated_data.get('max_results', 10)
        max_pages_per_site = serializer.validated_data.get('max_pages_per_site', 5)
        async_task = serializer.validated_data.get('async_task', True)
        
        # Create tracking task
        scraping_task = ScrapingTask.objects.create(
            query=query,
            status='pending',
        )
        
        if async_task:
            # Queue async Celery task
            task = search_and_scrape_companies.delay(
                query=query,
                max_results=max_results,
                max_pages_per_site=max_pages_per_site,
                task_id=str(scraping_task.id),
            )
            
            return Response({
                'message': 'Scraping task queued',
                'task_id': str(scraping_task.id),
                'celery_task_id': task.id,
                'query': query,
                'status': 'pending',
            }, status=status.HTTP_202_ACCEPTED)
        
        else:
            # Execute synchronously (not recommended for large batches)
            try:
                result = search_and_scrape_companies(
                    query=query,
                    max_results=max_results,
                    max_pages_per_site=max_pages_per_site,
                    task_id=str(scraping_task.id),
                )
                
                return Response({
                    'message': 'Scraping completed',
                    'task_id': str(scraping_task.id),
                    'query': query,
                    'results': result,
                })
            
            except Exception as e:
                scraping_task.status = 'failed'
                scraping_task.errors = str(e)
                scraping_task.save()
                
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


class BulkScrapeAPIView(generics.GenericAPIView):
    """
    Bulk scrape multiple search queries.
    """
    serializer_class = BulkScrapingRequestSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        queries = serializer.validated_data['queries']
        max_results = serializer.validated_data.get('max_results_per_query', 10)
        max_pages = serializer.validated_data.get('max_pages_per_site', 5)
        
        # Queue bulk task
        task = bulk_scrape_from_queries.delay(
            queries=queries,
            max_results_per_query=max_results,
            max_pages_per_site=max_pages,
        )
        
        return Response({
            'message': f'Bulk scraping task queued for {len(queries)} queries',
            'task_id': task.id,
            'queries': queries,
        }, status=status.HTTP_202_ACCEPTED)


class ValidateEmailsAPIView(generics.GenericAPIView):
    """
    Re-validate all emails in the database.
    """
    
    def post(self, request):
        task = validate_all_emails.delay()
        
        return Response({
            'message': 'Email validation task queued',
            'task_id': task.id,
        }, status=status.HTTP_202_ACCEPTED)


class CeleryTaskStatusAPIView(generics.GenericAPIView):
    """
    Check status of a Celery task.
    """
    
    def get(self, request, task_id):
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        
        response = {
            'task_id': task_id,
            'status': result.status,
            'ready': result.ready(),
        }
        
        if result.ready():
            if result.successful():
                response['result'] = result.result
            else:
                response['error'] = str(result.result)
        
        return Response(response)


# Legacy API Views for backward compatibility

class LeadSearchAPIView(generics.GenericAPIView):
    """
    Legacy search endpoint - redirects to new async search.
    """
    
    @method_decorator(ratelimit(key='ip', rate='10/m', method='GET'))
    def get(self, request):
        query = request.GET.get("q", "football sports manufacturer")
        max_results = int(request.GET.get("max_results", 10))
        
        # Create tracking task
        scraping_task = ScrapingTask.objects.create(
            query=query,
            status='pending',
        )
        
        # Queue async task
        task = search_and_scrape_companies.delay(
            query=query,
            max_results=max_results,
            task_id=str(scraping_task.id),
        )
        
        return Response({
            'message': 'Lead search queued',
            'task_id': str(scraping_task.id),
            'celery_task_id': task.id,
            'query': query,
            'check_status_url': f'/api/leads/tasks/{task.id}/status/',
        })


class LeadQuickSearchAPIView(generics.GenericAPIView):
    """
    Quick synchronous search for simple use cases.
    Limited to 5 results to avoid timeouts.
    """
    serializer_class = LeadListSerializer

    @method_decorator(ratelimit(key='ip', rate='5/m', method='GET'))
    def get(self, request):
        from .scrapers import CompanySearcher, EmailExtractor, ScrapingError
        from .scrapers import extract_emails_from_website
        from .utils import check_duplicate_website, normalize_url, prioritize_emails

        query = request.GET.get("q", "football sports manufacturer")

        # Search for companies
        searcher = CompanySearcher(delay=1.5)
        search_results = searcher.search_duckduckgo(query, max_results=5)

        created_leads = []
        skipped = []

        for item in search_results:
            website = normalize_url(item["website"])

            # Skip duplicates
            if check_duplicate_website(website):
                skipped.append({'website': website, 'reason': 'duplicate'})
                continue

            # Extract emails, phones, and social media
            extractor = EmailExtractor(max_pages=3, delay=1.0)
            result = extractor.extract_from_website(website)

            emails = result.get('emails', [])
            phones = result.get('phones', [])
            social_media = result.get('social_media', {})
            country = result.get('country', '')
            city = result.get('city', '')

            has_social = any(v for v in social_media.values() if v)

            if emails or phones or has_social:
                best_email = None
                if emails:
                    prioritized = prioritize_emails(emails, item['name'])
                    best_email = prioritized[0] if prioritized else None
                primary_phone = phones[0] if phones else ''

                lead = Lead.objects.create(
                    name=item["name"][:255],
                    website=website,
                    email=best_email,
                    email_validated=bool(best_email),
                    phone=primary_phone,
                    country=country,
                    city=city,
                    linkedin=social_media.get('linkedin', ''),
                    facebook=social_media.get('facebook', ''),
                    instagram=social_media.get('instagram', ''),
                    twitter=social_media.get('twitter', ''),
                    youtube=social_media.get('youtube', ''),
                    scraped_pages=result.get('scraped_pages', []),
                    source='search',
                )
                created_leads.append(lead)
            else:
                skipped.append({
                    'website': website,
                    'reason': 'no_contact_info',
                    'name': item['name'],
                    'phones_found': len(phones),
                })

        serializer = self.get_serializer(created_leads, many=True)

        return Response({
            "message": "Lead search completed",
            "query": query,
            "found": len(search_results),
            "created": len(created_leads),
            "skipped": len(skipped),
            "data": serializer.data,
            "skipped_details": skipped,
        })


# ============================================================================
# NEW: Manual Selection API Views (Search + Individual Scraping)
# ============================================================================

class SearchCompaniesAPIView(generics.GenericAPIView):
    """
    Search for companies ONLY - does NOT scrape websites.
    Returns list of companies (name + website) for manual selection.
    """
    
    @method_decorator(ratelimit(key='ip', rate='10/m', method='GET'))
    def get(self, request):
        query = request.GET.get("q", "football sports manufacturer")
        max_results = int(request.GET.get("max_results", 20))
        
        # Search for companies only
        searcher = CompanySearcher(delay=1.5)
        search_results = searcher.search_duckduckgo(query, max_results)
        
        # Check which websites already exist in database
        companies = []
        for item in search_results:
            website = normalize_url(item["website"])
            exists = check_duplicate_website(website)
            
            companies.append({
                'name': item['name'],
                'website': website,
                'snippet': item.get('snippet', ''),
                'already_exists': exists,
            })
        
        return Response({
            "message": "Search completed",
            "query": query,
            "total_found": len(companies),
            "new_companies": len([c for c in companies if not c['already_exists']]),
            "existing_companies": len([c for c in companies if c['already_exists']]),
            "companies": companies,
        })


class ScrapeSingleCompanyAPIView(generics.GenericAPIView):
    """
    Scrape a single selected company website for emails.
    Accepts company name and website, returns scraped lead.
    """
    
    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
    def post(self, request):
        company_name = request.data.get('name', '').strip()
        website = request.data.get('website', '').strip()
        max_pages = request.data.get('max_pages', 5)
        
        # Validation
        if not website:
            return Response(
                {'error': 'Website URL is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not company_name:
            return Response(
                {'error': 'Company name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Normalize URL
        normalized_url = normalize_url(website)
        
        # Check for duplicate before scraping
        if check_duplicate_website(normalized_url):
            return Response({
                'error': 'This website already exists in the database',
                'website': normalized_url,
                'duplicate': True,
            }, status=status.HTTP_409_CONFLICT)
        
        # Queue async scraping task
        task = scrape_single_website.delay(
            website_url=normalized_url,
            company_name=company_name,
            max_pages=max_pages,
        )
        
        return Response({
            'message': 'Scraping task queued for selected company',
            'celery_task_id': task.id,
            'name': company_name,
            'website': normalized_url,
            'check_status_url': f'/api/leads/tasks/{task.id}/status/',
        }, status=status.HTTP_202_ACCEPTED)


class QuickScrapeSingleAPIView(generics.GenericAPIView):
    """
    Synchronous scraping for a single company (for immediate feedback).
    Use for small scraping jobs only.
    """
    serializer_class = LeadDetailSerializer

    @method_decorator(ratelimit(key='ip', rate='3/m', method='POST'))
    def post(self, request):
        company_name = request.data.get('name', '').strip()
        website = request.data.get('website', '').strip()
        max_pages = request.data.get('max_pages', 3)

        if not website or not company_name:
            return Response(
                {'error': 'Both name and website are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Normalize URL
        normalized_url = normalize_url(website)

        # Check for duplicate
        if check_duplicate_website(normalized_url):
            return Response({
                'error': 'This website already exists in the database',
                'website': normalized_url,
                'duplicate': True,
            }, status=status.HTTP_409_CONFLICT)

        # Scrape synchronously (for quick results)
        try:
            from .scrapers import EmailExtractor
            extractor = EmailExtractor(max_pages=max_pages, delay=1.0)
            result = extractor.extract_from_website(normalized_url)

            emails = result.get('emails', [])
            phones = result.get('phones', [])
            social_media = result.get('social_media', {})
            country = result.get('country', '')
            city = result.get('city', '')

            has_social = any(v for v in social_media.values() if v)

            if emails or phones or has_social:
                best_email = None
                if emails:
                    prioritized = prioritize_emails(emails, company_name)
                    best_email = prioritized[0] if prioritized else None
                primary_phone = phones[0] if phones else ''

                # Create lead with all extracted data
                lead = Lead.objects.create(
                    name=company_name[:255],
                    website=normalized_url,
                    email=best_email,
                    email_validated=bool(best_email),
                    phone=primary_phone,
                    country=country,
                    city=city,
                    linkedin=social_media.get('linkedin', ''),
                    facebook=social_media.get('facebook', ''),
                    instagram=social_media.get('instagram', ''),
                    twitter=social_media.get('twitter', ''),
                    youtube=social_media.get('youtube', ''),
                    scraped_pages=result.get('scraped_pages', []),
                    source='search',
                    status='new',
                )

                serializer = self.get_serializer(lead)

                return Response({
                    'message': 'Company scraped and saved successfully',
                    'status': 'success',
                    'lead': serializer.data,
                    'emails_found': len(emails),
                    'phones_found': len(phones),
                    'social_media': social_media,
                    'country': country,
                    'city': city,
                })
            else:
                return Response({
                    'message': 'No contact info found on this website',
                    'status': 'no_contact',
                    'website': normalized_url,
                    'phones': phones,
                    'social_media': social_media,
                    'country': country,
                    'city': city,
                    'pages_scraped': result.get('scraped_pages', []),
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': f'Scraping failed: {str(e)}',
                'website': normalized_url,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
