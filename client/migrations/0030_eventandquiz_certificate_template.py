# Generated by Django 5.0.4 on 2025-02-13 06:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0029_prizepayment'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventandquiz',
            name='certificate_template',
            field=models.ImageField(blank=True, null=True, upload_to='certificate_templates/'),
        ),
    ]
