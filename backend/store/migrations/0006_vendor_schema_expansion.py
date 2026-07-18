from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0005_product_is_active_adminprofile'),
    ]

    operations = [
        # ── Expand Vendor ──────────────────────────────────────────────────────
        migrations.AddField(
            model_name='vendor',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='vendor',
            name='address',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='vendor',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='vendors/logos/'),
        ),
        migrations.AddField(
            model_name='vendor',
            name='commission_rate',
            field=models.DecimalField(decimal_places=2, default=10, max_digits=5),
        ),
        migrations.AddField(
            model_name='vendor',
            name='payout_method',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='vendor',
            name='payout_details',
            field=models.JSONField(blank=True, default=dict),
        ),

        # ── Expand VendorOrder ─────────────────────────────────────────────────
        migrations.AddField(
            model_name='vendororder',
            name='vendor_earnings',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='vendororder',
            name='tracking_number',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='vendororder',
            name='shipped_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendororder',
            name='delivered_at',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # ── VendorStaffMember ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='VendorStaffMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('owner', 'Owner'), ('manager', 'Manager'), ('staff', 'Staff')],
                    default='staff', max_length=20,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('vendor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='staff_members', to='store.vendor',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vendor_staff_roles', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['vendor', 'role'], 'unique_together': {('vendor', 'user')}},
        ),

        # ── VendorDocument ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='VendorDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_type', models.CharField(
                    choices=[
                        ('registration', 'Business Registration'),
                        ('tax', 'Tax Certificate'),
                        ('identity', 'Identity Document'),
                        ('other', 'Other'),
                    ],
                    default='other', max_length=20,
                )),
                ('file', models.FileField(upload_to='vendors/documents/')),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                    default='pending', max_length=20,
                )),
                ('notes', models.TextField(blank=True, default='')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('vendor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='documents', to='store.vendor',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_vendor_docs', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-uploaded_at']},
        ),

        # ── VendorPayout ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='VendorPayout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('method', models.CharField(
                    choices=[
                        ('flutterwave', 'Flutterwave'),
                        ('paypal', 'PayPal'),
                        ('mobile_money', 'Mobile Money'),
                        ('bank_transfer', 'Bank Transfer'),
                    ],
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[
                        ('requested', 'Requested'),
                        ('processing', 'Processing'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                    ],
                    default='requested', max_length=20,
                )),
                ('reference', models.CharField(blank=True, default='', max_length=128)),
                ('payout_details', models.JSONField(blank=True, default=dict)),
                ('notes', models.TextField(blank=True, default='')),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('vendor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payouts', to='store.vendor',
                )),
            ],
            options={'ordering': ['-requested_at']},
        ),

        # ── ProductReview ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ProductReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(default=5)),
                ('title', models.CharField(blank=True, default='', max_length=120)),
                ('body', models.TextField(blank=True, default='')),
                ('reply', models.TextField(blank=True, default='')),
                ('replied_at', models.DateTimeField(blank=True, null=True)),
                ('is_visible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reviews', to='store.product',
                )),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='product_reviews', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at'], 'unique_together': {('product', 'user')}},
        ),

        # ── VendorNotification ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='VendorNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    choices=[
                        ('new_order', 'New Order'),
                        ('low_stock', 'Low Stock'),
                        ('payment',   'Payment Confirmed'),
                        ('payout',    'Payout Update'),
                        ('review',    'New Review'),
                        ('system',    'System'),
                    ],
                    default='system', max_length=20,
                )),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField(blank=True, default='')),
                ('is_read', models.BooleanField(default=False)),
                ('link', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('vendor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications', to='store.vendor',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
