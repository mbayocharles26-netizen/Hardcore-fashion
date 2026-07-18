from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0012_adminprofile_avatar'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('pending',   'Pending'),
                        ('approved',  'Approved'),
                        ('rejected',  'Rejected'),
                        ('processed', 'Processed'),
                    ],
                    default='pending', max_length=20,
                )),
                ('reason',     models.TextField()),
                ('notes',      models.TextField(blank=True, default='')),
                ('admin_note', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refunds', to='store.order',
                )),
                ('customer', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='refunds', to=settings.AUTH_USER_MODEL,
                )),
                ('vendor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='refunds', to='store.vendor',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
