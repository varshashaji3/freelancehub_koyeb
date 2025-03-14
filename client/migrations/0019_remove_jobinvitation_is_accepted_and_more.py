# Generated by Django 5.0.4 on 2025-02-03 23:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0018_jobinvitation_client'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='jobinvitation',
            name='is_accepted',
        ),
        migrations.AddField(
            model_name='jobinvitation',
            name='status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Accepted', 'Accepted'), ('Rejected', 'Rejected')], default='Pending', max_length=10),
        ),
    ]
