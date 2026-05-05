import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')
django.setup()

from Kickline.models import ContactReply, ContactMessage
from Kickline.tasks import send_reply_email

print("=== Testing Reply Email Function ===\n")

# Get the most recent contact message
contact_message = ContactMessage.objects.first()
if not contact_message:
    print("No contact messages found in database")
    sys.exit(1)

print(f"Contact Message:")
print(f"  ID: {contact_message.id}")
print(f"  Name: {contact_message.name}")
print(f"  Email: {contact_message.email}")
print(f"  Subject: {contact_message.subject}")
print(f"  Status: {contact_message.status}")
print()

# Get existing replies for this message
replies = contact_message.replies.all()
print(f"Existing replies: {replies.count()}")
for reply in replies:
    print(f"  Reply ID: {reply.id}, Subject: {reply.reply_subject}, Email Sent: {reply.email_sent}")

print()

# Create a test reply
print("Creating a new test reply...")
test_reply = ContactReply.objects.create(
    contact_message=contact_message,
    reply_subject="Test Reply - Please Ignore",
    reply_message="This is a test reply to verify email sending is working correctly.",
    sent_by="Test System"
)

print(f"Test reply created with ID: {test_reply.id}")
print(f"Email sent flag after creation: {test_reply.email_sent}")
print()

# Test sending the email manually
print("Testing send_reply_email function...")
try:
    success = send_reply_email(test_reply)
    print(f"send_reply_email returned: {success}")
except Exception as e:
    print(f"Error calling send_reply_email: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== Test Complete ===")
