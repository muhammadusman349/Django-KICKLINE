#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
from Kickline.models import ContactMessage, ContactReply
from Kickline.tasks import send_reply_email

def test_email_settings():
    """Test basic email configuration"""
    print("=== Testing Email Configuration ===")
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Not set')}")
    print(f"EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'Not set')}")
    print(f"EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', 'Not set')}")
    print(f"EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'Not set')}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"KICKLINE_SPORTS_OWNER_EMAIL: {settings.KICKLINE_SPORTS_OWNER_EMAIL}")
    print()

def test_simple_email():
    """Test sending a simple email"""
    print("=== Testing Simple Email ===")
    try:
        send_mail(
            subject='Test Email from KICKLINE Sports',
            message='This is a test email to verify email configuration.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.KICKLINE_SPORTS_OWNER_EMAIL],
            fail_silently=False,
        )
        print("✅ Simple email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Simple email failed: {str(e)}")
        return False

def test_reply_email():
    """Test reply email function with mock data"""
    print("=== Testing Reply Email Function ===")
    
    # Get or create a test contact message
    contact_message, created = ContactMessage.objects.get_or_create(
        name="Test User",
        email="test@example.com",
        subject="Test Contact Message",
        defaults={
            'phone': '123-456-7890',
            'message': 'This is a test contact message for email testing.',
            'status': 'new'
        }
    )
    
    if created:
        print("✅ Created test contact message")
    else:
        print("✅ Using existing test contact message")
    
    # Create a test reply
    reply = ContactReply.objects.create(
        contact_message=contact_message,
        reply_subject="Test Reply",
        reply_message="This is a test reply to verify the email system is working correctly.",
        sent_by="Test Admin"
    )
    print("✅ Created test reply")
    
    # Test the reply email function
    try:
        success = send_reply_email(reply)
        if success:
            print("✅ Reply email function executed successfully!")
            reply.email_sent = True
            reply.save()
        else:
            print("❌ Reply email function returned False")
        return success
    except Exception as e:
        print(f"❌ Reply email function failed: {str(e)}")
        return False

def main():
    print("🏆 KICKLINE Sports EMAIL TESTING SCRIPT")
    print("=" * 50)
    
    # Test 1: Check email settings
    test_email_settings()
    
    # Test 2: Send simple email
    simple_success = test_simple_email()
    print()
    
    # Test 3: Test reply email function
    reply_success = test_reply_email()
    print()
    
    # Summary
    print("=== TEST SUMMARY ===")
    print(f"Simple Email: {'✅ PASS' if simple_success else '❌ FAIL'}")
    print(f"Reply Email: {'✅ PASS' if reply_success else '❌ FAIL'}")
    
    if simple_success and reply_success:
        print("\n🎉 All tests passed! Email system is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()
