from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0006_vendor_schema_expansion'),
    ]

    operations = [

        # ── Expand Product ─────────────────────────────────────────────────────
        migrations.AddField(
            model_name='product',
            name='compare_at_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='attributes',
            field=models.JSONField(blank=True, default=dict),
        ),

        # ── Expand Order ───────────────────────────────────────────────────────
        migrations.AddField(
            model_name='order',
            name='shipping_address',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='subtotal',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='order',
            name='tax_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_earned',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_used',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='order',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),

        # ── CustomerProfile ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='CustomerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, default='', max_length=30)),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='customers/avatars/')),
                ('loyalty_points', models.PositiveIntegerField(default=0)),
                ('preferred_currency', models.CharField(default='GBP', max_length=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='customer_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),

        # ── Address ────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(blank=True, default='', max_length=60)),
                ('type', models.CharField(
                    choices=[('shipping', 'Shipping'), ('billing', 'Billing')],
                    default='shipping', max_length=10,
                )),
                ('full_name', models.CharField(max_length=200)),
                ('line1', models.CharField(max_length=255)),
                ('line2', models.CharField(blank=True, default='', max_length=255)),
                ('city', models.CharField(max_length=100)),
                ('state', models.CharField(blank=True, default='', max_length=100)),
                ('postcode', models.CharField(max_length=20)),
                ('country', models.CharField(default='United Kingdom', max_length=100)),
                ('phone', models.CharField(blank=True, default='', max_length=30)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='addresses',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-is_default', '-created_at'], 'verbose_name_plural': 'Addresses'},
        ),

        # ── WishlistItem ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WishlistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='wishlist',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='wishlisted_by',
                    to='store.product',
                )),
            ],
            options={'ordering': ['-added_at'], 'unique_together': {('user', 'product')}},
        ),

        # ── ProductReviewReport ────────────────────────────────────────────────
        migrations.CreateModel(
            name='ProductReviewReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(
                    choices=[
                        ('spam', 'Spam'),
                        ('offensive', 'Offensive'),
                        ('fake', 'Fake Review'),
                        ('other', 'Other'),
                    ],
                    default='other', max_length=20,
                )),
                ('details', models.TextField(blank=True, default='')),
                ('resolved', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('review', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reports',
                    to='store.productreview',
                )),
                ('reporter', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='review_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at'], 'unique_together': {('review', 'reporter')}},
        ),

        # ── SupportTicket ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    choices=[
                        ('general', 'General Enquiry'),
                        ('order',   'Order Issue'),
                        ('return',  'Return Request'),
                        ('refund',  'Refund Request'),
                    ],
                    default='general', max_length=20,
                )),
                ('subject', models.CharField(max_length=200)),
                ('status', models.CharField(
                    choices=[
                        ('open',        'Open'),
                        ('in_progress', 'In Progress'),
                        ('resolved',    'Resolved'),
                        ('closed',      'Closed'),
                    ],
                    default='open', max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='support_tickets',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('order', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='support_tickets',
                    to='store.order',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── SupportMessage ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='SupportMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('attachment', models.FileField(blank=True, null=True, upload_to='support/attachments/')),
                ('is_staff', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='store.supportticket',
                )),
                ('sender', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='support_messages',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['created_at']},
        ),

        # ── LoyaltyTransaction ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='LoyaltyTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    choices=[('earn', 'Earned'), ('spend', 'Spent'), ('adjust', 'Manual Adjustment')],
                    max_length=10,
                )),
                ('points', models.IntegerField()),
                ('balance_after', models.PositiveIntegerField()),
                ('note', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='loyalty_transactions',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('order', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='loyalty_transactions',
                    to='store.order',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
