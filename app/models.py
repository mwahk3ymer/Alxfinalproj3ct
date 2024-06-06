from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Define roles


class Role(models.Model):
    name = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name

# Extend User model using a one-to-one link


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=100, default='')
    id_number = models.CharField(max_length=100, default='')
    role = models.ForeignKey(
        Role, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username

# Signal to automatically create/update UserProfile when User is created/updated
# python manage.py makemigrations app --empty --name populate_default_roles

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    instance.userprofile.save()


class UserData(models.Model):
    # Link UserData to a User
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=120, default='')
    phone = models.CharField(max_length=100, default='')
    age = models.IntegerField(default=0)
    region = models.CharField(max_length=100, default='')
    gender = models.CharField(max_length=10, choices=(
        ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')), default='Other')
    occupation = models.CharField(max_length=120, default='Other')
    education_level = models.CharField(max_length=100, choices=(
        ('None', 'None'), ('Primary', 'Primary'), ('Secondary', 'Secondary'), ('Tertiary', 'Tertiary')), default='None')
    marital_status = models.CharField(max_length=50, choices=(('Single', 'Single'), (
        'Married', 'Married'), ('Divorced', 'Divorced'), ('Widowed', 'Widowed')), default='Single')
    number_of_dependents = models.IntegerField(default=0)
    income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    image = models.ImageField(upload_to='user_images/')

    def __str__(self):
        return f"{self.name} ({self.region})"


class FaceMetadata(models.Model):
    user_data = models.OneToOneField(UserData, on_delete=models.CASCADE)
    face_encoding = models.TextField()
