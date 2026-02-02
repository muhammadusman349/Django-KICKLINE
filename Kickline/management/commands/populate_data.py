from django.core.management.base import BaseCommand
from Kickline.models import Category, Product, Shipment, BannerPicture


class Command(BaseCommand):
    help = 'Populate the database with sample sports products'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')

        # Clear existing data
        self.stdout.write('Clearing existing data...')
        Category.objects.all().delete()
        Product.objects.all().delete()
        Shipment.objects.all().delete()
        BannerPicture.objects.all().delete()

        # Create categories
        self.stdout.write('Creating categories...')
        categories = [
            {'name': 'Football', 'slug': 'football'},
            {'name': 'Goalkeeper Gloves', 'slug': 'goalkeeper-gloves'},
            {'name': 'Shirts', 'slug': 'shirts'},
            {'name': 'Football Boots', 'slug': 'football-boots'},
            {'name': 'Training Equipment', 'slug': 'training-equipment'},
            {'name': 'Accessories', 'slug': 'accessories'}
        ]

        for cat_data in categories:
            Category.objects.get_or_create(**cat_data)

        football_cat = Category.objects.get(slug='football')
        gloves_cat = Category.objects.get(slug='goalkeeper-gloves')
        shirts_cat = Category.objects.get(slug='shirts')
        boots_cat = Category.objects.get(slug='football-boots')
        training_cat = Category.objects.get(slug='training-equipment')
        accessories_cat = Category.objects.get(slug='accessories')

        # Create sample products
        self.stdout.write('Creating products...')
        products_data = [
            # Football products
            {
                'category': football_cat,
                'name': 'Professional FIFA Football',
                'description': 'Official FIFA approved football with premium leather construction.',
                'price': 45.99,
                'is_featured': True
            },
            {
                'category': football_cat,
                'name': 'Training Football Set',
                'description': 'Set of 5 high-quality training footballs. Durable synthetic material.',
                'price': 89.99,
                'is_featured': False
            },

            # Goalkeeper Gloves
            {
                'category': gloves_cat,
                'name': 'Pro Goalkeeper Gloves',
                'description': 'Professional grade goalkeeper gloves with superior grip and finger protection.',
                'price': 79.99,
                'is_featured': True
            },

            # Shirts
            {
                'category': shirts_cat,
                'name': 'Team Jersey Home',
                'description': 'Official team home jersey with moisture-wicking fabric.',
                'price': 65.99,
                'is_featured': True
            },

            # Football Boots
            {
                'category': boots_cat,
                'name': 'Pro FG Football Boots',
                'description': 'Firm ground football boots with advanced traction and comfort technology.',
                'price': 149.99,
                'is_featured': True
            },

            # Training Equipment
            {
                'category': training_cat,
                'name': 'Agility Ladder Set',
                'description': '12-rung agility ladder with carrying case.',
                'price': 29.99,
                'is_featured': True
            },

            # Accessories
            {
                'category': accessories_cat,
                'name': 'Shin Guards',
                'description': 'Lightweight shin guards with ankle protection.',
                'price': 19.99,
                'is_featured': True
            }
        ]

        # Create products
        for product_data in products_data:
            Product.objects.create(**product_data)

        # Create shipment methods
        self.stdout.write('Creating shipment methods...')
        shipment_methods = [
            {
                'name': 'Air Cargo',
                'icon': '',
                'description': 'Fast international shipping via air cargo',
                'delivery_time': '3-5 business days',
                'cost': 'Varies by weight and destination'
            },
            {
                'name': 'TCS',
                'icon': '',
                'description': 'Reliable ground shipping with tracking. 3-5 business days.',
                'delivery_time': '2-3 business days',
                'cost': 'Free on orders over $50, otherwise $4.99'
            },
            {
                'name': 'DHL',
                'icon': '',
                'description': 'Next business day delivery with DHL.',
                'delivery_time': '1-3 business days',
                'cost': '$9.99'
            },

            {
             'name': 'Local Delivery',
             'icon': '',
             'description': 'Same-day delivery within city limits',
             'delivery_time': 'Same day',
             'cost': 'Flat rate within city'
             }
        ]

        for method in shipment_methods:
            Shipment.objects.create(**method)

        # Create banner pictures
        self.stdout.write('Creating banner pictures...')
        banners = [
            {'name': 'Main Banner', 'image': 'banner/banner1.jpg'},
            {'name': 'Summer Sale', 'image': 'banner/banner2.jpg'},
            {'name': 'New Arrivals', 'image': 'banner/banner3.jpg'}
        ]

        for banner in banners:
            BannerPicture.objects.create(**banner)

        self.stdout.write(self.style.SUCCESS('Successfully populated database with sample data!'))
