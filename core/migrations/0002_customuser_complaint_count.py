# Generated by Django 5.0.4 on 2024-09-06 11:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='complaint_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
