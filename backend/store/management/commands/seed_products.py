from django.core.management.base import BaseCommand

from store.models import Category, Product


CATEGORIES = [
    {'name': 'T-Shirts', 'slug': 't-shirts', 'description': 'Premium heavyweight graphic tees for the bold.'},
    {'name': 'Hoodies', 'slug': 'hoodies', 'description': 'Oversized and statement hoodies built for the streets.'},
    {'name': 'Jackets', 'slug': 'jackets', 'description': 'Leather, denim, and bomber jackets with attitude.'},
    {'name': 'Trousers', 'slug': 'trousers', 'description': 'Cargo, slim, and wide-leg trousers for every look.'},
    {'name': 'Footwear', 'slug': 'footwear', 'description': 'Boots, trainers, and statement shoes.'},
    {'name': 'Accessories', 'slug': 'accessories', 'description': 'Belts, chains, caps, and finishing touches.'},
]

PRODUCTS = [
    ('Black Skull Tee', 'black-skull-tee', 't-shirts', 'Heavyweight 280gsm cotton tee featuring a hand-drawn skull graphic. Relaxed fit, pre-shrunk.', 29.99, 50, True),
    ('Gold Crest Tee', 'gold-crest-tee', 't-shirts', 'Clean black tee with a gold foil Hardcore Fashion crest emblem. Slim fit, 100% organic cotton.', 34.99, 35, False),
    ('Gold Chain Hoodie', 'gold-chain-hoodie', 'hoodies', 'Oversized 400gsm fleece hoodie with embroidered gold chain graphic. Kangaroo pocket, ribbed cuffs.', 64.99, 30, True),
    ('Acid Wash Pullover', 'acid-wash-pullover', 'hoodies', 'Vintage acid-wash effect pullover in charcoal. Dropped shoulders, raw hem, unisex sizing.', 54.99, 20, False),
    ('Moto Leather Jacket', 'moto-leather-jacket', 'jackets', 'Genuine full-grain leather biker jacket with silver asymmetric zip and quilted shoulders.', 149.99, 15, True),
    ('Washed Denim Jacket', 'washed-denim-jacket', 'jackets', 'Heavy-duty washed black denim jacket with distressed detailing and oversized fit.', 89.99, 25, False),
    ('Tactical Cargo Pants', 'tactical-cargo-pants', 'trousers', 'Six-pocket tactical cargo trousers in matte black ripstop fabric. Adjustable ankle cuffs, D-ring hardware.', 74.99, 40, True),
    ('Slim Tapered Joggers', 'slim-tapered-joggers', 'trousers', 'Slim-tapered joggers in heavyweight French terry. Elasticated waist with drawstring, zip ankle.', 49.99, 45, False),
    ('Combat Lace-Up Boots', 'combat-lace-up-boots', 'footwear', 'Genuine leather combat boots with steel-toe cap, Goodyear welt construction, and chunky lug sole.', 129.99, 18, True),
    ('High-Top Trainers', 'high-top-trainers', 'footwear', 'Vulcanised high-top canvas trainers with gold eyelets and a thick cupsole. Black/gold colourway.', 69.99, 3, False),
    ('Studded Leather Belt', 'studded-leather-belt', 'accessories', 'Full-grain black leather belt with pyramid stud detailing and a matte gold pin buckle. 35mm width.', 24.99, 100, False),
    ('Gold Cuban Chain', 'gold-cuban-chain', 'accessories', '18k gold-plated 10mm Cuban link chain, 55cm length. Lobster clasp, tarnish-resistant coating.', 44.99, 60, True),
]


class Command(BaseCommand):
    help = 'Seed the database with Hardcore Fashion Store sample products'

    def handle(self, *args, **kwargs):
        cat_map = {}
        for data in CATEGORIES:
            cat, created = Category.objects.get_or_create(slug=data['slug'], defaults=data)
            cat_map[data['slug']] = cat
            self.stdout.write(f"  {'Created' if created else 'Exists '} category: {cat.name}")

        for name, slug, cat_slug, desc, price, stock, featured in PRODUCTS:
            _, created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'category': cat_map[cat_slug],
                    'description': desc,
                    'price': price,
                    'stock': stock,
                    'is_featured': featured,
                },
            )
            self.stdout.write(f"  {'Created' if created else 'Exists '} product:  {name}")

        self.stdout.write(self.style.SUCCESS('\nSeed complete - 6 categories, 12 products.'))
