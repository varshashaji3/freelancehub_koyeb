# Generated by Django 5.0.4 on 2025-03-09 21:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0031_eventandquiz_approval_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='required_skills',
            field=models.JSONField(default=list),
        ),
    ]
