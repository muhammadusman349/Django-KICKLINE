from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def send_contact_notification_email(contact_message):
    try:
        subject = f"New Contact Message: {contact_message.subject}"

        # Context for the HTML template
        context = {
            'contact_message': contact_message,
            'current_year': timezone.now().year,
        }

        # Render HTML and text templates
        html_content = render_to_string('emails/contact_notification.html', context)
        text_content = render_to_string('emails/contact_notification.txt', context)

        # Create email with both HTML and text versions
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.KICKLINE_SPORTS_OWNER_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Contact notification email sent successfully for message ID: {contact_message.id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send contact notification email for message ID: {contact_message.id}. Error: {str(e)}")
        return False


def send_contact_confirmation_email(contact_message):
    try:
        subject = "Thank you for contacting KICKLINE Sports!"

        # Context for the HTML template
        context = {
            'contact_message': contact_message,
            'current_year': timezone.now().year,
            'whatsapp_number': settings.WHATSAPP_NUMBER,
            'contact_email': settings.CONTACT_EMAIL,
        }

        # Render HTML and text templates
        html_content = render_to_string('emails/contact_confirmation.html', context)
        text_content = render_to_string('emails/contact_confirmation.txt', context)

        # Create email with both HTML and text versions
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[contact_message.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Contact confirmation email sent successfully to: {contact_message.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send contact confirmation email to: {contact_message.email}. Error: {str(e)}")
        return False


def send_reply_email(reply):
    try:
        subject = f"Re: {reply.contact_message.subject}"

        # Debug logging
        print(f"DEBUG: Attempting to send reply email to {reply.contact_message.email}")
        print(f"DEBUG: Subject: {subject}")

        # Context for the HTML template
        context = {
            'reply': reply,
            'current_year': timezone.now().year,
            'whatsapp_number': settings.WHATSAPP_NUMBER,
            'contact_email': settings.CONTACT_EMAIL,
        }

        # Render HTML and text templates
        html_content = render_to_string('emails/reply_email.html', context)
        text_content = render_to_string('emails/reply_email.txt', context)

        print(f"DEBUG: Templates rendered successfully")

        # Create email with both HTML and text versions
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[reply.contact_message.email],
        )
        email.attach_alternative(html_content, "text/html")

        print(f"DEBUG: Email object created, attempting to send...")
        email.send()
        print(f"DEBUG: Email sent successfully!")

        logger.info(f"Reply email sent successfully to: {reply.contact_message.email}")
        return True

    except Exception as e:
        print(f"DEBUG: Email sending failed: {str(e)}")
        logger.error(f"Failed to send reply email to: {reply.contact_message.email}. Error: {str(e)}")
        return False
