import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("Email Configuration:")
print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
print()

print("Testing email sending...")
try:
    result = send_mail(
        'Test Email from KICKLINE',
        'This is a test email to verify SMTP configuration.',
        settings.DEFAULT_FROM_EMAIL,
        ['test@example.com'],
        fail_silently=False,
    )
    print(f"Email sent successfully: {result}")
except Exception as e:
    print(f"Email failed: {e}")
    print(f"Error type: {type(e).__name__}")
