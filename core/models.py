from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from django.conf import settings

from dateutil.relativedelta import relativedelta


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    username=models.CharField(max_length=128)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    joined = models.DateTimeField(auto_now_add=True)

    ADMIN = 'admin'
    CLIENT = 'client'
    FREELANCER = 'freelancer'

    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (CLIENT, 'Client'),
        (FREELANCER, 'Freelancer'),
    ]

    role = models.CharField(max_length=20, blank=True, null=True, choices=ROLE_CHOICES, default='')
    welcome_email_sent = models.BooleanField(default=False)
    permission = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    google=models.BooleanField(default=False)
    complaint_count = models.PositiveIntegerField(default=0)
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'  

    REQUIRED_FIELDS = []  
    def __str__(self):
        return self.email

  

    
class Register(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    phone_number = models.CharField(max_length=10, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    bio_description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    linkedin = models.URLField(max_length=255, blank=True, null=True)
    instagram = models.URLField(max_length=255, blank=True, null=True)
    twitter = models.URLField(max_length=255, blank=True, null=True)
    
    
    
    
class PasswordReset(models.Model):
    user_id = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=50, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)  # New field for expiration time

    def is_expired(self):
        return timezone.now() > self.expires_at  # Method to check if the token is expired


class EmailVerification(models.Model):
    user_id = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=50, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)  # New field for expiration time

    def is_expired(self):
        return timezone.now() > self.expires_at  # Method to check if the token is expired
    
    
    
class Event(models.Model):
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#ffffff')  # Hex color code
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='events')


class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    

class SiteReview(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # The user who wrote the review
    review_text = models.TextField()  
    rating = models.PositiveIntegerField()  
    created_at = models.DateTimeField(default=timezone.now)  

    def __str__(self):
        return f"Review by {self.user} on {self.created_at}"

    def is_due_for_review(self, months=3):
        """
        Check if the review should be requested based on the given number of months.
        """
        threshold_date = self.created_at + relativedelta(months=months)
        return timezone.now() >= threshold_date
    
    
    
from client.models import Project,FreelanceContract
from django.conf import settings
from django.utils import timezone
class CancellationRequest(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cancellation_requests_made')
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cancellation_requests_to_approve')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    requested_date = models.DateTimeField(default=timezone.now)
    response_date = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True) 
    def __str__(self):
        return f"Cancellation Request for Project {self.project.id} by {self.requested_by}"



class RefundPayment(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    pay_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=255, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_refund_payments')
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    compensation_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    project = models.ForeignKey('client.Project', on_delete=models.CASCADE, null=True, blank=True)  # New field

    def __str__(self):
        return f"Refund Payment of {self.amount} to {self.pay_to} for Project {self.project.id}"
