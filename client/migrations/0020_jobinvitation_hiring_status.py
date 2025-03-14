# Generated by Django 5.0.4 on 2025-02-04 08:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0019_remove_jobinvitation_is_accepted_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobinvitation',
            name='hiring_status',
            field=models.CharField(choices=[('Hired', 'Hired'), ('Not Hired', 'Not Hired'), ('Pending', 'Pending')], default='Pending', max_length=10),
        ),
    ]
