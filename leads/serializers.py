"""
DRF Serializers for Leads app.
"""

from rest_framework import serializers
from .models import Lead, ScrapingTask, OutreachEmail


class LeadListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    domain = serializers.SerializerMethodField()
    has_email = serializers.SerializerMethodField()
    social_media = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "website",
            "domain",
            "email",
            "has_email",
            "email_validated",
            "country",
            "city",
            "phone",
            "social_media",
            "status",
            "source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_domain(self, obj):
        from .utils import get_domain_from_url
        return get_domain_from_url(obj.website)

    def get_has_email(self, obj):
        return bool(obj.email)

    def get_social_media(self, obj):
        return {
            "linkedin": obj.linkedin,
            "facebook": obj.facebook,
            "instagram": obj.instagram,
            "twitter": "",
        }


class LeadDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail views"""
    domain = serializers.SerializerMethodField()
    social_media = serializers.SerializerMethodField()
    outreach_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "website",
            "domain",
            "email",
            "email_validated",
            "email_verified",
            "country",
            "city",
            "phone",
            "social_media",
            "status",
            "source",
            "scraped_pages",
            "notes",
            "last_contacted",
            "contact_count",
            "outreach_count",
            "task",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "contact_count", "outreach_count"]
    
    def get_domain(self, obj):
        from .utils import get_domain_from_url
        return get_domain_from_url(obj.website)
    
    def get_social_media(self, obj):
        return {
            "linkedin": obj.linkedin,
            "facebook": obj.facebook,
            "instagram": obj.instagram,
        }
    
    def get_outreach_count(self, obj):
        return obj.outreach_emails.count()


class LeadCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating leads"""
    
    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "website",
            "email",
            "country",
            "city",
            "phone",
            "linkedin",
            "facebook",
            "instagram",
            "status",
            "source",
            "notes",
        ]
        read_only_fields = ["id"]
    
    def validate_website(self, value):
        from .utils import normalize_url
        return normalize_url(value)


# Backward compatibility
LeadSerializer = LeadListSerializer


class ScrapingTaskSerializer(serializers.ModelSerializer):
    """Serializer for scraping tasks"""
    lead_count = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = ScrapingTask
        fields = [
            "id",
            "query",
            "status",
            "total_found",
            "total_saved",
            "duplicates_skipped",
            "errors",
            "lead_count",
            "started_at",
            "completed_at",
            "created_at",
            "duration_seconds",
        ]
        read_only_fields = [
            "id", "total_found", "total_saved", "duplicates_skipped",
            "started_at", "completed_at", "created_at", "lead_count", "duration_seconds"
        ]
    
    def get_lead_count(self, obj):
        return obj.leads.count()
    
    def get_duration_seconds(self, obj):
        if obj.started_at and obj.completed_at:
            return int((obj.completed_at - obj.started_at).total_seconds())
        return None


class ScrapingTaskDetailSerializer(ScrapingTaskSerializer):
    """Serializer with nested leads"""
    leads = LeadListSerializer(many=True, read_only=True)
    
    class Meta(ScrapingTaskSerializer.Meta):
        fields = ScrapingTaskSerializer.Meta.fields + ["leads"]


class ScrapingRequestSerializer(serializers.Serializer):
    """Serializer for initiating scraping requests"""
    query = serializers.CharField(required=True, max_length=255)
    max_results = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)
    max_pages_per_site = serializers.IntegerField(required=False, default=5, min_value=1, max_value=10)
    async_task = serializers.BooleanField(required=False, default=True)
    
    def validate_query(self, value):
        # Sanitize query - remove potentially harmful characters
        import re
        # Allow alphanumeric, spaces, hyphens, and common search operators
        sanitized = re.sub(r'[^\w\s\-\+\.\"\']', '', value)
        return sanitized.strip()


class BulkScrapingRequestSerializer(serializers.Serializer):
    """Serializer for bulk scraping requests"""
    queries = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_empty=False,
        max_length=20
    )
    max_results_per_query = serializers.IntegerField(required=False, default=10, min_value=1, max_value=50)
    max_pages_per_site = serializers.IntegerField(required=False, default=5, min_value=1, max_value=10)


class RescrapeRequestSerializer(serializers.Serializer):
    """Serializer for re-scraping requests"""
    lead_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        max_length=100
    )
    max_pages = serializers.IntegerField(required=False, default=5, min_value=1, max_value=10)


class OutreachEmailSerializer(serializers.ModelSerializer):
    """Serializer for outreach emails"""
    lead_name = serializers.CharField(source='lead.name', read_only=True)
    
    class Meta:
        model = OutreachEmail
        fields = [
            "id",
            "lead",
            "lead_name",
            "subject",
            "body",
            "template_used",
            "sent_at",
            "opened_at",
            "clicked_at",
        ]
        read_only_fields = ["id", "sent_at", "opened_at", "clicked_at"]


class LeadExportSerializer(serializers.Serializer):
    """Serializer for lead export requests"""
    lead_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    status = serializers.ChoiceField(
        choices=Lead.STATUS_CHOICES,
        required=False,
        allow_blank=True
    )
    email_validated = serializers.BooleanField(required=False)
    format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('json', 'JSON')],
        default='csv'
    )


class LeadFilterSerializer(serializers.Serializer):
    """Serializer for filtering leads"""
    status = serializers.ChoiceField(
        choices=Lead.STATUS_CHOICES,
        required=False
    )
    source = serializers.ChoiceField(
        choices=Lead.SOURCE_CHOICES,
        required=False
    )
    email_validated = serializers.BooleanField(required=False)
    has_email = serializers.BooleanField(required=False)
    country = serializers.CharField(required=False, max_length=100)
    search = serializers.CharField(required=False, max_length=255)
    order_by = serializers.ChoiceField(
        choices=['created_at', '-created_at', 'name', '-name', 'email'],
        default='-created_at'
    )
