# Generated by Django 5.0.4 on 2025-01-15 22:58

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('freelancer', '0005_remove_freelancerprofile_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('join_code', models.CharField(max_length=8, unique=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_teams', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TeamInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('role', models.CharField(choices=[('PROJECT_MANAGER', 'Project Manager & Team Leader'), ('DESIGNER', 'Designer (UI/UX)'), ('FRONTEND_DEV', 'Frontend Developer'), ('BACKEND_DEV', 'Backend Developer'), ('QA_TESTER', 'Quality Assurance Tester')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('token', models.CharField(max_length=100, unique=True)),
                ('is_accepted', models.BooleanField(default=False)),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_invitations', to=settings.AUTH_USER_MODEL)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='freelancer.team')),
            ],
        ),
        migrations.CreateModel(
            name='TeamMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('PROJECT_MANAGER', 'Project Manager & Team Leader'), ('DESIGNER', 'Designer (UI/UX)'), ('FRONTEND_DEV', 'Frontend Developer'), ('BACKEND_DEV', 'Backend Developer'), ('QA_TESTER', 'Quality Assurance Tester')], max_length=20)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='freelancer.team')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('team', 'user')},
            },
        ),
    ]
