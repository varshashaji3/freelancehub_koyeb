# Generated by Django 5.0.4 on 2024-10-20 17:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('freelancer', '0004_document_cover_image'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='freelancerprofile',
            name='status',
        ),
    ]