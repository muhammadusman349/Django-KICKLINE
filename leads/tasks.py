"""
Celery tasks for asynchronous sports company scraping and lead generation.
"""

import logging
from typing import List, Dict, Optional
from celery import shared_task, chain, group, chord
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone
from django.db import transaction

from .models import Lead, ScrapingTask
from .scrapers import CompanySearcher, EmailExtractor, ScrapingError
from .utils import (
    check_duplicate_website, 
    normalize_url, 
    prioritize_emails,
    get_domain_from_url,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_single_website(self, website_url: str, company_name: str = '',
                         task_id: Optional[str] = None, max_pages: int = 5) -> Dict:
    """
    Celery task to scrape a single website for emails, phones, and social media.

    Args:
        website_url: URL to scrape
        company_name: Company name for context
        task_id: Optional parent ScrapingTask ID for tracking
        max_pages: Maximum pages to crawl

    Returns:
        Dict with scraping results
    """
    try:
        # Normalize URL
        normalized_url = normalize_url(website_url)

        # Check for duplicate
        if check_duplicate_website(normalized_url):
            logger.info(f"Skipping duplicate website: {normalized_url}")
            return {
                'status': 'duplicate',
                'website': normalized_url,
                'message': 'Website already exists in database',
            }

        # Extract emails, phones, and social media
        extractor = EmailExtractor(max_pages=max_pages, delay=1.0)
        result = extractor.extract_from_website(normalized_url)

        emails = result.get('emails', [])
        phones = result.get('phones', [])
        social_media = result.get('social_media', {})
        country = result.get('country', '')
        city = result.get('city', '')
        scraped_pages = result.get('scraped_pages', [])
        errors = result.get('errors', [])

        if emails:
            # Prioritize emails
            prioritized = prioritize_emails(emails, company_name)
            best_email = prioritized[0] if prioritized else None

            # Get primary phone (first one if available)
            primary_phone = phones[0] if phones else ''

            # Create lead with all extracted data
            with transaction.atomic():
                lead = Lead.objects.create(
                    name=company_name or get_domain_from_url(normalized_url),
                    website=normalized_url,
                    email=best_email,
                    email_validated=True,
                    phone=primary_phone,
                    country=country,
                    city=city,
                    linkedin=social_media.get('linkedin', ''),
                    facebook=social_media.get('facebook', ''),
                    instagram=social_media.get('instagram', ''),
                    scraped_pages=scraped_pages,
                    source='search',
                    status='new',
                    task_id=task_id,
                )

                logger.info(f"Created lead: {lead.name} with email: {best_email}, phone: {primary_phone}")

                return {
                    'status': 'success',
                    'lead_id': str(lead.id),
                    'website': normalized_url,
                    'email': best_email,
                    'phones': phones,
                    'social_media': social_media,
                    'country': country,
                    'city': city,
                    'emails_found': len(emails),
                    'phones_found': len(phones),
                    'pages_scraped': len(scraped_pages),
                    'errors': errors,
                }
        else:
            logger.info(f"No emails found for: {normalized_url}")
            return {
                'status': 'no_emails',
                'website': normalized_url,
                'phones': phones,
                'social_media': social_media,
                'country': country,
                'city': city,
                'pages_scraped': len(scraped_pages),
                'errors': errors,
            }

    except Exception as e:
        logger.error(f"Error scraping {website_url}: {e}")

        # Retry on certain failures
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying scrape for {website_url} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)

        return {
            'status': 'error',
            'website': website_url,
            'error': str(e),
        }


@shared_task
def search_and_scrape_companies(query: str, max_results: int = 10, 
                                max_pages_per_site: int = 5,
                                task_id: Optional[str] = None) -> Dict:
    """
    Search for companies and scrape their websites for emails.
    
    Args:
        query: Search query
        max_results: Maximum companies to search
        max_pages_per_site: Maximum pages to crawl per website
        task_id: Parent ScrapingTask ID for tracking
    
    Returns:
        Dict with search and scrape results
    """
    # Update task status
    if task_id:
        ScrapingTask.objects.filter(id=task_id).update(
            status='in_progress',
            started_at=timezone.now(),
        )
    
    # Search for companies
    searcher = CompanySearcher(delay=2.0)
    search_results = searcher.search_duckduckgo(query, max_results)
    
    logger.info(f"Found {len(search_results)} companies for query: {query}")
    
    # Create subtasks to scrape each website
    scrape_tasks = []
    for company in search_results:
        task = scrape_single_website.s(
            website_url=company['website'],
            company_name=company['name'],
            task_id=task_id,
            max_pages=max_pages_per_site,
        )
        scrape_tasks.append(task)
    
    # Execute all scrape tasks in parallel
    if scrape_tasks:
        job = group(scrape_tasks)
        results = job.apply_async()
        scrape_results = results.get(timeout=300)  # 5 minute timeout
    else:
        scrape_results = []
    
    # Aggregate results
    total_found = len(search_results)
    total_saved = sum(1 for r in scrape_results if r.get('status') == 'success')
    duplicates = sum(1 for r in scrape_results if r.get('status') == 'duplicate')
    no_emails = sum(1 for r in scrape_results if r.get('status') == 'no_emails')
    errors = sum(1 for r in scrape_results if r.get('status') == 'error')
    
    # Update task with final status
    if task_id:
        ScrapingTask.objects.filter(id=task_id).update(
            status='completed',
            completed_at=timezone.now(),
            total_found=total_found,
            total_saved=total_saved,
            duplicates_skipped=duplicates,
            errors=f"No emails: {no_emails}, Errors: {errors}",
        )
    
    return {
        'query': query,
        'total_found': total_found,
        'total_saved': total_saved,
        'duplicates_skipped': duplicates,
        'no_emails': no_emails,
        'errors': errors,
        'details': scrape_results,
    }


@shared_task
def bulk_scrape_from_queries(queries: List[str], max_results_per_query: int = 10,
                             max_pages_per_site: int = 5) -> Dict:
    """
    Bulk scrape multiple search queries.
    
    Args:
        queries: List of search queries
        max_results_per_query: Max results per query
        max_pages_per_site: Max pages to crawl per website
    
    Returns:
        Dict with aggregate results
    """
    total_results = {
        'queries_processed': 0,
        'total_found': 0,
        'total_saved': 0,
        'duplicates': 0,
        'failed': 0,
    }
    
    for query in queries:
        try:
            # Create tracking task
            task = ScrapingTask.objects.create(
                query=query,
                status='pending',
            )
            
            # Execute search and scrape
            result = search_and_scrape_companies(
                query=query,
                max_results=max_results_per_query,
                max_pages_per_site=max_pages_per_site,
                task_id=str(task.id),
            )
            
            total_results['queries_processed'] += 1
            total_results['total_found'] += result['total_found']
            total_results['total_saved'] += result['total_saved']
            total_results['duplicates'] += result['duplicates_skipped']
            total_results['failed'] += result['errors']
            
        except Exception as e:
            logger.error(f"Failed to process query '{query}': {e}")
            total_results['failed'] += 1
    
    return total_results


@shared_task
def re_scrape_lead(lead_id: int, max_pages: int = 5) -> Dict:
    """
    Re-scrape an existing lead to find updated emails, phones, and social media.

    Args:
        lead_id: ID of the Lead to re-scrape
        max_pages: Maximum pages to crawl

    Returns:
        Dict with re-scrape results
    """
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return {'status': 'error', 'message': f'Lead {lead_id} not found'}

    try:
        extractor = EmailExtractor(max_pages=max_pages, delay=1.0)
        result = extractor.extract_from_website(lead.website)

        emails = result.get('emails', [])
        phones = result.get('phones', [])
        social_media = result.get('social_media', {})
        country = result.get('country', '')
        city = result.get('city', '')

        updated = False

        if emails:
            # Prioritize and update if new emails found
            prioritized = prioritize_emails(emails, lead.name)

            # Update lead if we found new emails
            if prioritized:
                old_email = lead.email
                lead.email = prioritized[0]
                lead.email_validated = True
                updated = True

        # Update phone if not already set
        if phones and not lead.phone:
            lead.phone = phones[0]
            updated = True

        # Update social media if not already set
        if social_media.get('linkedin') and not lead.linkedin:
            lead.linkedin = social_media['linkedin']
            updated = True
        if social_media.get('facebook') and not lead.facebook:
            lead.facebook = social_media['facebook']
            updated = True
        if social_media.get('instagram') and not lead.instagram:
            lead.instagram = social_media['instagram']
            updated = True

        # Update location if not already set
        if country and not lead.country:
            lead.country = country
            updated = True
        if city and not lead.city:
            lead.city = city
            updated = True

        # Update scraped pages
        lead.scraped_pages = list(set(lead.scraped_pages + result.get('scraped_pages', [])))

        if updated:
            lead.save()
            return {
                'status': 'updated',
                'lead_id': lead_id,
                'email': lead.email,
                'phone': lead.phone,
                'country': lead.country,
                'city': lead.city,
                'emails_found': len(emails),
                'phones_found': len(phones),
            }

        return {
            'status': 'unchanged',
            'lead_id': lead_id,
            'emails_found': len(emails),
            'phones_found': len(phones),
        }

    except Exception as e:
        logger.error(f"Error re-scraping lead {lead_id}: {e}")
        return {'status': 'error', 'lead_id': lead_id, 'error': str(e)}


@shared_task
def validate_all_emails() -> Dict:
    """
    Re-validate all emails in the database.
    Useful for periodic validation.
    
    Returns:
        Dict with validation results
    """
    from .utils import validate_and_normalize_email
    
    leads = Lead.objects.filter(email__isnull=False).exclude(email='')
    
    results = {
        'total': leads.count(),
        'valid': 0,
        'invalid': 0,
        'normalized': 0,
    }
    
    for lead in leads:
        is_valid, normalized = validate_and_normalize_email(lead.email)
        
        if is_valid:
            lead.email_validated = True
            results['valid'] += 1
            
            if normalized != lead.email:
                lead.email = normalized
                results['normalized'] += 1
        else:
            lead.email_validated = False
            results['invalid'] += 1
        
        lead.save()
    
    return results


@shared_task
def export_leads_to_csv(lead_ids: Optional[List[int]] = None,
                        status: Optional[str] = None,
                        email_validated: Optional[bool] = None) -> str:
    """
    Export leads to CSV file.
    
    Args:
        lead_ids: Optional list of specific lead IDs
        status: Optional status filter
        email_validated: Optional email validation filter
    
    Returns:
        Path to generated CSV file
    """
    import csv
    import os
    from django.conf import settings
    from .utils import format_lead_for_export
    
    # Build queryset
    queryset = Lead.objects.all()
    
    if lead_ids:
        queryset = queryset.filter(id__in=lead_ids)
    if status:
        queryset = queryset.filter(status=status)
    if email_validated is not None:
        queryset = queryset.filter(email_validated=email_validated)
    
    # Generate filename
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"leads_export_{timestamp}.csv"
    filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Write CSV
    fieldnames = [
        'id', 'name', 'website', 'domain', 'email', 'email_validated',
        'country', 'city', 'phone', 'status', 'source', 'linkedin',
        'facebook', 'instagram', 'created_at', 'notes',
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for lead in queryset:
            data = format_lead_for_export(lead)
            row = {
                'id': data['id'],
                'name': data['name'],
                'website': data['website'],
                'domain': data['domain'],
                'email': data['email'],
                'email_validated': data['email_validated'],
                'country': data['country'],
                'city': data['city'],
                'phone': data['phone'],
                'status': data['status'],
                'source': data['source'],
                'linkedin': data['social_media']['linkedin'],
                'facebook': data['social_media']['facebook'],
                'instagram': data['social_media']['instagram'],
                'created_at': data['created_at'],
                'notes': data['notes'],
            }
            writer.writerow(row)
    
    logger.info(f"Exported {queryset.count()} leads to {filepath}")
    
    return filepath


@shared_task
def cleanup_old_tasks(days: int = 30) -> int:
    """
    Delete old completed/failed scraping tasks.
    
    Args:
        days: Delete tasks older than this many days
    
    Returns:
        Number of tasks deleted
    """
    cutoff_date = timezone.now() - timezone.timedelta(days=days)
    
    old_tasks = ScrapingTask.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['completed', 'failed']
    )
    
    count = old_tasks.count()
    old_tasks.delete()
    
    logger.info(f"Deleted {count} old scraping tasks")
    
    return count
