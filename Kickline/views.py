from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.db.models import Count
from .models import Category, Product, Shipment, BannerPicture, Catalog
from .forms import ContactForm, CatalogPasswordForm
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
    paginator = Paginator(product_list, 6)  # Show 9 products per page
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
    products = Product.objects.filter(category=category).order_by('-created_at')

    # Pagination
    paginator = Paginator(products, 9)  # Show 9 products per page
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    # Get related categories (exclude current category, limit to 3)
    related_categories = Category.objects.exclude(id=category.id)[:3]

    context = {
        'category': category,
        'products': products,
        'related_categories': related_categories,
    }
    return render(request, 'Kickline/category_detail.html', context)


def category_list(request):
    """Category list page showing all categories with sorting and search"""
    category_list = Category.objects.all()
    
    # Handle search query
    search_query = request.GET.get('search')
    if search_query:
        category_list = category_list.filter(name__icontains=search_query)
    
    # Handle sorting
    sort_by = request.GET.get('sort', 'name')  # Default sort by name
    
    if sort_by == 'name':
        category_list = category_list.order_by('name')
    elif sort_by == 'name_desc':
        category_list = category_list.order_by('-name')
    elif sort_by == 'products':
        # Annotate with product count and sort
        category_list = category_list.annotate(product_count=Count('products')).order_by('product_count')
    elif sort_by == 'products_desc':
        category_list = category_list.annotate(product_count=Count('products')).order_by('-product_count')
    else:
        category_list = category_list.order_by('name')

    # Pagination
    paginator = Paginator(category_list, 6)  # Show 6 categories per page
    page_number = request.GET.get('page')
    categories = paginator.get_page(page_number)

    context = {
        'categories': categories,
        'sort_by': sort_by,
        'search_query': search_query,
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


def catalog_list(request):
    """Display all catalogs organized by category with optional filtering"""
    catalogs = Catalog.objects.all().order_by('-year', 'category')
    
    # Get category filter from query parameters
    category_code = request.GET.get('category')
    if category_code:
        catalogs = catalogs.filter(category=category_code)

    # Pagination
    paginator = Paginator(catalogs, 9) # Show 9 catalogs per page
    page_number = request.GET.get('page')
    catalogs = paginator.get_page(page_number)

    context = {
        'catalogs': catalogs,
        'categories': Catalog.CATEGORY_CHOICES,
        'current_category': category_code,
    }
    return render(request, 'Kickline/catalog_list.html', context)


def catalog_download(request, catalog_id):
    """Verify password and serve PDF with download count increment"""
    catalog = get_object_or_404(Catalog, pk=catalog_id)

    if request.method == 'POST':
        # If no password is set, allow direct download without form validation
        if not catalog.password:
            catalog.increase_download()
            try:
                return FileResponse(
                    catalog.catalog_file.open(),
                    as_attachment=True,
                    filename=f"{catalog.title}.pdf"
                )
            except FileNotFoundError:
                raise Http404("PDF file not found")

        # Password-protected download
        form = CatalogPasswordForm(request.POST)
        if form.is_valid():
            entered_password = form.cleaned_data['password']

            if entered_password == catalog.password:
                # Password correct - increment count and serve file
                catalog.increase_download()

                try:
                    return FileResponse(
                        catalog.catalog_file.open(),
                        as_attachment=True,
                        filename=f"{catalog.title}.pdf"
                    )
                except FileNotFoundError:
                    raise Http404("PDF file not found")
            else:
                # Password incorrect
                messages.error(request, 'Incorrect password. Please try again.')
                return redirect('Kickline:catalog_list')

    # Redirect to list if accessed via GET
    return redirect('Kickline:catalog_list')
