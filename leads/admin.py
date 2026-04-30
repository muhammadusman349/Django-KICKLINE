"""
Admin configuration for leads app.
"""

from django.contrib import admin
from .models import Lead, ScrapingTask, OutreachEmail


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'website', 'email', 'email_validated',
        'country', 'status', 'source', 'created_at'
    ]
    list_filter = [
        'status', 'source', 'email_validated', 'email_verified',
        'country', 'created_at'
    ]
    search_fields = ['name', 'website', 'email', 'country', 'city', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'last_contacted', 'contact_count']
    date_hierarchy = 'created_at'
    actions = ['mark_validated', 'mark_as_contacted', 'mark_invalid']
    
    fieldsets = (
        ('Company Info', {
            'fields': ('name', 'website', 'email', 'phone')
        }),
        ('Location', {
            'fields': ('country', 'city'),
        }),
        ('Social Media', {
            'fields': ('linkedin', 'facebook', 'instagram'),
            'classes': ('collapse',),
        }),
        ('Email Status', {
            'fields': ('email_validated', 'email_verified'),
        }),
        ('Lead Status', {
            'fields': ('status', 'source', 'notes'),
        }),
        ('Scraping Metadata', {
            'fields': ('task', 'scraped_pages'),
            'classes': ('collapse',),
        }),
        ('Outreach Tracking', {
            'fields': ('last_contacted', 'contact_count'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    @admin.action(description='Mark selected emails as validated')
    def mark_validated(self, request, queryset):
        queryset.update(email_validated=True)
    
    @admin.action(description='Mark selected as contacted')
    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='contacted', last_contacted=timezone.now())
    
    @admin.action(description='Mark selected as invalid')
    def mark_invalid(self, request, queryset):
        queryset.update(status='invalid', email_validated=False)


@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'query', 'status', 'total_found', 'total_saved',
        'duplicates_skipped', 'created_at', 'duration_display'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['query', 'errors']
    readonly_fields = [
        'id', 'total_found', 'total_saved', 'duplicates_skipped',
        'created_at', 'started_at', 'completed_at', 'errors'
    ]
    date_hierarchy = 'created_at'
    
    def duration_display(self, obj):
        if obj.started_at and obj.completed_at:
            seconds = int((obj.completed_at - obj.started_at).total_seconds())
            return f"{seconds}s"
        return "-"
    duration_display.short_description = 'Duration'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('leads')


@admin.register(OutreachEmail)
class OutreachEmailAdmin(admin.ModelAdmin):
    list_display = ['lead', 'subject', 'template_used', 'sent_at', 'opened_at', 'clicked_at']
    list_filter = ['template_used', 'sent_at']
    search_fields = ['lead__name', 'subject', 'body']
    readonly_fields = ['sent_at', 'opened_at', 'clicked_at']
    date_hierarchy = 'sent_at'
