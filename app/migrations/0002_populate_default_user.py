# Generated by Django 5.0.3 on 2024-03-20 08:55

from django.db import migrations
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist


def create_default_user_and_profile(apps, schema_editor):
    # Get the models
    Role = apps.get_model('app', 'Role')
    UserProfile = apps.get_model('app', 'UserProfile')
    User = apps.get_model('auth', 'User')

    # Create a default role if it doesn't exist
    Role.objects.create(name='Enumerator')
    role, created = Role.objects.get_or_create(name='Admin')

    # Create a default user if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        user = User.objects.create_superuser(
            'admin', 'admin@pictocensus.com', '2024@Password')
        # Create or update the user profile
        UserProfile.objects.create(
            user=user, phone='0748355080', id_number='12345678', role=role)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_user_and_profile),
    ]
