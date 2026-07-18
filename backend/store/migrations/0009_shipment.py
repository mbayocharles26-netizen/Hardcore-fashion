from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0008_rls_policies'),
    ]

    operations = [
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracking_number', models.CharField(blank=True, db_index=True, max_length=32, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('shipped', 'Shipped'), ('in_transit', 'In transit'), ('delivered', 'Delivered')], default='pending', max_length=20)),
                ('estimated_arrival', models.DateField(blank=True, null=True)),
                ('current_location', models.CharField(blank=True, default='', max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='shipment', to='store.order')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
