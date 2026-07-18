from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0011_vendorverification'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminprofile',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='admins/avatars/'),
        ),
    ]
