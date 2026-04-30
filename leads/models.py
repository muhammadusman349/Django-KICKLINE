from django.db import models
from django.core.validators import URLValidator
import uuid

class ScrapingTask(models.Model):
    """Track async scraping tasks"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.CharField(max_length=255, help_text="Search query used")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_found = models.IntegerField(default=0)
    total_saved = models.IntegerField(default=0)
    duplicates_skipped = models.IntegerField(default=0)
    errors = models.TextField(blank=True, help_text="Error messages if failed")
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Task {self.id} - {self.query} ({self.status})"


class Lead(models.Model):
    """Sports company leads with enhanced tracking"""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('responded', 'Responded'),
        ('converted', 'Converted'),
        ('invalid', 'Invalid'),
    ]
    
    SOURCE_CHOICES = [
        ('search', 'Search Engine'),
        ('manual', 'Manual Entry'),
        ('import', 'Import'),
    ]
    
    name = models.CharField(max_length=255)
    website = models.URLField(unique=True, validators=[URLValidator()])
    email = models.EmailField(blank=True, null=True)
    email_validated = models.BooleanField(default=False, help_text="Email format validated")
    email_verified = models.BooleanField(default=False, help_text="Email deliverability verified")
    
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    # Social media
    linkedin = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='search')
    
    # Scraping metadata
    task = models.ForeignKey(ScrapingTask, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads')
    scraped_pages = models.JSONField(default=list, help_text="Pages scraped for emails")
    notes = models.TextField(blank=True)
    
    # Outreach tracking
    last_contacted = models.DateTimeField(null=True, blank=True)
    contact_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['email_validated']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email or 'No email'})"
    
    def get_absolute_url(self):
        return self.website


class OutreachEmail(models.Model):
    """Track outreach emails sent to leads"""
    TEMPLATE_CHOICES = [
        ('introduction', 'Introduction'),
        ('follow_up', 'Follow Up'),
        ('proposal', 'Proposal'),
        ('custom', 'Custom'),
    ]
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='outreach_emails')
    subject = models.CharField(max_length=255)
    body = models.TextField()
    template_used = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='custom')
    
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Email to {self.lead.name} - {self.subject}"