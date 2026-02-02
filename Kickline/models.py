from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
import re
from urllib.parse import quote


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('Kickline:category_detail', kwargs={'slug': self.slug})


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=100, default='N/A')
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('Kickline:product_detail', kwargs={'slug': self.slug})

    # WhatsApp contact
    def get_whatsapp_url(self):
        size_info = f" (Size: {self.size})" if self.size and self.size != 'N/A' else ""
        message = f"Hi, I'm interested in {self.name}{size_info} - ${self.price}"
        # Clean number to digits only for wa.me compatibility
        raw = getattr(settings, 'WHATSAPP_NUMBER', '')
        phone_number = re.sub(r"\D", "", raw)
        return f"https://wa.me/{phone_number}?text={quote(message)}"

    # Email contact
    def get_email_recipient(self):
        return settings.CONTACT_EMAIL

    def get_email_subject(self):
        return f"Inquiry about {self.name}"

    def get_email_body(self):
        size_info = f"\nSize: {self.size}" if self.size and self.size != 'N/A' else ""
        return (
            f"Hi,\n\nI'm interested in the following product:\n\n"
            f"Product: {self.name}\nPrice: ${self.price}{size_info}\n"
            f"Description: {self.description}\n\n"
            f"Please provide more details.\n\nThank you!"
        )


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']

    def __str__(self):
        return f"{self.product.name} - Image {self.id}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary image per product
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class Shipment(models.Model):
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to='shipment/icons/', blank=True, null=True)
    description = models.TextField()
    delivery_time = models.CharField(max_length=100)
    cost = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class BackgroundImage(models.Model):
    SECTION_CHOICES = [
        ('hero', 'Hero Section'),
        ('categories', 'Premium Categories'),
        ('featured', 'Featured Products'),
        ('about', 'About Section'),
        ('contact', 'Contact Section'),
    ]

    name = models.CharField(max_length=100)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, unique=True)
    image = models.ImageField(upload_to='backgrounds/')
    overlay_opacity = models.FloatField(default=0.8, help_text="Overlay opacity (0.0 to 1.0)")
    overlay_color = models.CharField(max_length=7, default='#0E1C36', help_text="Overlay color (hex code)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['section']
        verbose_name = 'Background Image'
        verbose_name_plural = 'Background Images'

    def __str__(self):
        return f"{self.get_section_display()} - {self.name}"

    def get_css_background(self):
        """Generate CSS background property with overlay"""
        return f"""
            background: 
                linear-gradient(135deg, rgba({self.hex_to_rgb(self.overlay_color)}, {self.overlay_opacity}) 0%, rgba({self.hex_to_rgb(self.overlay_color)}, {self.overlay_opacity - 0.05}) 100%),
                url('{self.image.url}') center/cover !important;
            background-attachment: fixed;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
        """

    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB values"""
        hex_color = hex_color.lstrip('#')
        return ', '.join(str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4))


class ContactMessage(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    owner_notes = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'

    def __str__(self):
        return f"{self.subject} - {self.name}"

    @property
    def has_reply(self):
        return self.replies.exists()

    @property
    def reply_count(self):
        return self.replies.count()


class ContactReply(models.Model):
    contact_message = models.ForeignKey(ContactMessage, on_delete=models.CASCADE, related_name='replies')
    reply_subject = models.CharField(max_length=200)
    reply_message = models.TextField()
    sent_by = models.CharField(max_length=100, default='Kickline Team')
    sent_at = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Contact Reply'
        verbose_name_plural = 'Contact Replies'

    def __str__(self):
        return f"Reply to: {self.contact_message.subject}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Send email automatically when reply is created
        if is_new and not self.email_sent:
            from django.utils import timezone
            from .tasks import send_reply_email
            try:
                print(f"Success: New reply created, sending email to {self.contact_message.email}")
                success = send_reply_email(self)
                if success:
                    # Update fields without triggering save again
                    ContactReply.objects.filter(pk=self.pk).update(email_sent=True)
                    ContactMessage.objects.filter(pk=self.contact_message.pk).update(
                        replied_at=timezone.now(),
                        status='in_progress'
                    )
                    print(f"Success: Email sent successfully and status updated")
                else:
                    print(f"ERROR: Email sending failed")
            except Exception as e:
                print(f"ERROR: Error sending email: {str(e)}")


class BannerPicture(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='banner/')
    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    button_text = models.CharField(max_length=50, default='Shop Now')
    button_link = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
