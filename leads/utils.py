"""
Utility functions for leads app - re-export from scrapers and additional helpers.
"""

import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

# Re-export all scraping functionality
from .scrapers import (
    EmailExtractor,
    CompanySearcher,
    extract_emails_from_website,
    validate_and_normalize_email,
    ScrapingError,
)

logger = logging.getLogger(__name__)

# Backward compatible exports
search_sports = CompanySearcher().search_duckduckgo
extract_emails = EmailExtractor().extract_from_website


def check_duplicate_website(website_url: str, exclude_id: Optional[int] = None) -> bool:
    """
    Check if a website already exists in the database.
    
    Args:
        website_url: URL to check
        exclude_id: Optional lead ID to exclude (for updates)
    
    Returns:
        True if duplicate exists, False otherwise
    """
    from .models import Lead
    
    # Normalize URL
    normalized = normalize_url(website_url)
    
    queryset = Lead.objects.filter(website=normalized)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    
    return queryset.exists()


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent storage and comparison.
    
    Args:
        url: Raw URL string
    
    Returns:
        Normalized URL string
    """
    url = url.strip().lower()
    
    # Add scheme if missing
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Remove www. prefix for consistency
    if '://www.' in url:
        url = url.replace('://www.', '://')
    
    return url


def get_domain_from_url(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: Website URL
    
    Returns:
        Domain name (e.g., 'example.com')
    """
    try:
        parsed = urlparse(normalize_url(url))
        return parsed.netloc.replace('www.', '')
    except:
        return ''


def prioritize_emails(emails: List[str], company_name: str = '') -> List[str]:
    """
    Prioritize emails by relevance to the company.
    Priority: sales/business > info > generic
    
    Args:
        emails: List of email addresses
        company_name: Company name for context
    
    Returns:
        Sorted list of emails by priority
    """
    priority_keywords = {
        'high': ['sales', 'business', 'marketing', 'export', 'wholesale', 
                 'manager', 'director', 'ceo', 'contact', 'inquiry'],
        'medium': ['info', 'support', 'hello', 'office'],
        'low': ['admin', 'webmaster', 'noreply', 'no-reply']
    }
    
    scored_emails = []
    
    for email in emails:
        local_part = email.split('@')[0].lower()
        score = 0
        
        # Check priority keywords
        for keyword in priority_keywords['high']:
            if keyword in local_part:
                score += 10
        for keyword in priority_keywords['medium']:
            if keyword in local_part:
                score += 5
        for keyword in priority_keywords['low']:
            if keyword in local_part:
                score -= 5
        
        # Prefer shorter local parts (more likely to be monitored)
        if len(local_part) <= 6:
            score += 2
        
        scored_emails.append((email, score))
    
    # Sort by score (descending)
    scored_emails.sort(key=lambda x: x[1], reverse=True)
    
    return [email for email, score in scored_emails]


def generate_search_queries(sport_types: List[str] = None, 
                          locations: List[str] = None,
                          business_types: List[str] = None) -> List[str]:
    """
    Generate optimized search queries for finding sports companies.
    
    Args:
        sport_types: List of sports (e.g., ['football', 'basketball'])
        locations: List of locations (e.g., ['usa', 'germany'])
        business_types: List of business types (e.g., ['manufacturer', 'wholesale'])
    
    Returns:
        List of search query strings
    """
    if not sport_types:
        sport_types = ['football', 'basketball', 'tennis', 'cricket', 'rugby', 
                      'hockey', 'volleyball', 'baseball', 'swimming', 'fitness']
    
    if not locations:
        locations = ['usa', 'uk', 'germany', 'italy', 'spain', 'france', 
                    'china', 'pakistan', 'india', 'turkey']
    
    if not business_types:
        business_types = ['manufacturer', 'supplier', 'wholesale', 'exporter', 'factory']
    
    queries = []
    
    for sport in sport_types:
        for location in locations:
            for biz_type in business_types:
                queries.append(f"{sport} {biz_type} {location}")
    
    return queries


def format_lead_for_export(lead) -> Dict:
    """
    Format a Lead object for export/serialization.
    
    Args:
        lead: Lead model instance
    
    Returns:
        Dict with formatted lead data
    """
    return {
        'id': lead.id,
        'name': lead.name,
        'website': lead.website,
        'domain': get_domain_from_url(lead.website),
        'email': lead.email,
        'email_validated': lead.email_validated,
        'email_verified': lead.email_verified,
        'country': lead.country,
        'city': lead.city,
        'phone': lead.phone,
        'status': lead.status,
        'source': lead.source,
        'social_media': {
            'linkedin': lead.linkedin,
            'facebook': lead.facebook,
            'instagram': lead.instagram,
        },
        'scraped_pages': lead.scraped_pages,
        'created_at': lead.created_at.isoformat() if lead.created_at else None,
        'updated_at': lead.updated_at.isoformat() if lead.updated_at else None,
        'last_contacted': lead.last_contacted.isoformat() if lead.last_contacted else None,
        'contact_count': lead.contact_count,
        'notes': lead.notes,
    }
