from django.contrib import admin
from .models import (
    Category, Product, ProductImage,
    Shipment, BannerPicture, BackgroundImage,
    ContactMessage, ContactReply
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id','name', 'slug', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'size', 'price', 'is_featured', 'created_at']
    list_filter = ['category', 'size', 'is_featured', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_featured', 'size']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProductImageInline]
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'category', 'slug', 'description', 'price', 'size')
        }),
        ('Settings', {
            'fields': ('is_featured',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'icon', 'description', 'delivery_time', 'cost', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Shipment Information', {
            'fields': ('name', 'icon', 'description', 'delivery_time', 'cost')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['product__name', 'alt_text']
    readonly_fields = ['created_at']


@admin.register(BackgroundImage)
class BackgroundImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'section', 'name', 'is_active', 'overlay_opacity', 'created_at']
    list_filter = ['section', 'is_active', 'created_at']
    search_fields = ['name', 'section']
    list_editable = ['is_active', 'overlay_opacity']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Background Information', {
            'fields': ('name', 'section', 'image')
        }),
        ('Overlay Settings', {
            'fields': ('overlay_color', 'overlay_opacity'),
            'description': 'Control the overlay color and transparency over the background image'
        }),
        ('Settings', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['overlay_color'].widget.attrs['type'] = 'color'
        return form


class ContactReplyInline(admin.TabularInline):
    model = ContactReply
    extra = 1
    fields = ['reply_subject', 'reply_message', 'sent_by']
    readonly_fields = []


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'name', 'email', 'status', 'reply_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at', 'replied_at', 'reply_count']
    inlines = [ContactReplyInline]
    fieldsets = (
        ('Sender', {
            'fields': ('name', 'email', 'phone')
        }),
        ('Message', {
            'fields': ('subject', 'message')
        }),
        ('Owner', {
            'fields': ('status', 'owner_notes')
        }),
        ('Reply Info', {
            'fields': ('replied_at', 'reply_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    actions = ['mark_in_progress', 'mark_closed']

    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f"Marked {updated} message(s) as In Progress")
    mark_in_progress.short_description = 'Mark selected as In Progress'

    def mark_closed(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f"Marked {updated} message(s) as Closed")
    mark_closed.short_description = 'Mark selected as Closed'


@admin.register(ContactReply)
class ContactReplyAdmin(admin.ModelAdmin):
    list_display = ['id', 'contact_message', 'reply_subject', 'sent_by', 'email_sent', 'sent_at']
    list_filter = ['email_sent', 'sent_at', 'sent_by']
    search_fields = ['reply_subject', 'reply_message', 'contact_message__subject']
    readonly_fields = ['sent_at', 'email_sent']


@admin.register(BannerPicture)
class BannerPictureAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'title', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'title']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Banner Information', {
            'fields': ('name', 'image', 'title', 'subtitle', 'button_text', 'button_link')
        }),
        ('Settings', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
