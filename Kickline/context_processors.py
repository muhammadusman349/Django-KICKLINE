from django.conf import settings
import re
from .models import BackgroundImage


def site_contacts(request):
    return {
        "CONTACT_EMAIL": getattr(settings, "CONTACT_EMAIL", ""),
        "WHATSAPP_NUMBER_1": getattr(settings, "WHATSAPP_NUMBER_1", ""),
        "WHATSAPP_NUMBER_2": getattr(settings, "WHATSAPP_NUMBER_2", ""),
    }


def background_images(request):
    """Make background images available in all templates"""
    backgrounds = {}
    try:
        for bg in BackgroundImage.objects.filter(is_active=True):
            backgrounds[f'bg_{bg.section}'] = bg
    except:
        # Handle case when table doesn't exist yet (during migrations)
        pass
    return {'backgrounds': backgrounds}
