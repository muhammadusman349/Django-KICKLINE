from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Category, Product, Shipment, BannerPicture
from .forms import ContactForm
from .tasks import send_contact_notification_email, send_contact_confirmation_email


def home(request):
    """Homepage with featured products and categories"""
    categories = Category.objects.all()[:6]  # Show 6 categories
    featured_products = Product.objects.filter(is_featured=True)[:6]
    banner_pictures = BannerPicture.objects.all()[:5]
    # banner_products = Product.objects.filter(image__in=banner_pictures.values('image'))

    context = {
        'categories': categories,
        'featured_products': featured_products,
        'banner_pictures': banner_pictures,
        # 'banner_products': banner_products,

    }
    return render(request, 'Kickline/home.html', context)


def product_list(request):
    """View to display all products"""
    product_list = Product.objects.all().order_by('-created_at')
    categories = Category.objects.all()

    # Get category filter from query parameters
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        product_list = product_list.filter(category=category)

    # Pagination
    paginator = Paginator(product_list, 9)  # Show 9 products per page
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    context = {
        'products': products,
        'categories': categories,
        'current_category': category_slug,
    }
    return render(request, 'Kickline/product_list.html', context)


def product_detail(request, slug):
    """Product detail page showing image, price, description and contact options"""
    product = get_object_or_404(Product, slug=slug)
    related_products = Product.objects.filter(category=product.category).exclude(slug=slug)[:3]
    context = {
        'product': product,
        'category': product.category,
        'related_products': related_products,
    }
    return render(request, 'Kickline/product_detail.html', context)


def category_detail(request, slug):
    """Category page showing all products in that category"""
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category)

    context = {
        'category': category,
        'products': products,
    }
    return render(request, 'Kickline/category_detail.html', context)


def category_list(request):
    """Category list page showing all categories"""
    category_list = Category.objects.all().order_by('name')

    # Pagination
    paginator = Paginator(category_list, 6)  # Show 6 categories per page
    page_number = request.GET.get('page')
    categories = paginator.get_page(page_number)

    context = {
        'categories': categories,
    }
    return render(request, 'Kickline/category_list.html', context)


def shipment(request):
    """Shipment detail page showing image, description, delivery time and cost"""
    shipment = Shipment.objects.all()
    context = {
        'shipment': shipment,
    }
    return render(request, 'Kickline/shipment.html', context)


def contact(request):
    """Contact page to submit inquiries"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Save the contact message
            contact_message = form.save()

            # Send email notifications using tasks
            notification_sent = send_contact_notification_email(contact_message)
            confirmation_sent = send_contact_confirmation_email(contact_message)

            # Show success message to user
            messages.success(request, 'Thanks for contacting Kickline! We will get back to you shortly.')
            return redirect('Kickline:contact')
        else:
            messages.error(request, 'Please correct the errors below and resubmit.')
    else:
        form = ContactForm()

    return render(request, 'Kickline/contact.html', {'form': form})
