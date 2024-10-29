from datetime import datetime, date
from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import CustomUser
from decimal import Decimal

class ClientProfile(models.Model):
    CLIENT_TYPE_CHOICES = (
        ('Individual', 'Individual'),
        ('Company', 'Company'),
    )
    
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_type = models.CharField(max_length=50, choices=CLIENT_TYPE_CHOICES, default='Individual')
    company_name = models.CharField(max_length=255, null=True, blank=True)
    website = models.URLField(max_length=255, null=True, blank=True)
    license_number = models.CharField(max_length=255, null=True, blank=True)
    
    aadhaar_document = models.FileField(upload_to='aadhaar/', null=True, blank=True)
    
    
class Project(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
    )
    
    PROGRESS_CHOICES = (
        ('Not Started', 'Not Started'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled','Cancelled')
    )
    
    SCOPE_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    budget = models.IntegerField()
    category = models.CharField(max_length=605)  
    allow_bid = models.BooleanField(default=False)
    end_date = models.DateField(null=True, blank=True)
    file_upload = models.FileField(upload_to='project_files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='client_projects')  
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    start_date = models.DateField(null=True, blank=True)
    project_end_date = models.DateField(null=True, blank=True)
    project_status = models.CharField(max_length=50, default='Not Started')
    freelancer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='freelancer_projects')
    git_repo_link = models.URLField(max_length=200, blank=True, null=True)

    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)  # GST rate (e.g., 18%)
    gst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)
    total_including_gst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, editable=False)

    client_review_given = models.BooleanField(default=False)
    freelancer_review_given = models.BooleanField(default=False)
    
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='medium')

    def save(self, *args, **kwargs):
        if isinstance(self.budget, str):
            self.budget = int(self.budget)
        
        budget_decimal = Decimal(self.budget)
        gst_rate_decimal = Decimal(self.gst_rate)
        
        self.gst_amount = budget_decimal * (gst_rate_decimal / Decimal('100'))
        self.total_including_gst = budget_decimal + self.gst_amount
        
        if self.end_date:
            # Convert end_date to date object if it's a string
            if isinstance(self.end_date, str):
                try:
                    self.end_date = datetime.strptime(self.end_date, '%Y-%m-%d').date()
                except ValueError:
                    # Handle invalid date format
                    pass
            
            # Now compare with today's date
            if self.end_date < date.today():
                self.status = 'closed'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title



class Repository(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='repositories')
    name = models.CharField(max_length=255, default='Default Repository')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return f'Repository for {self.project.name}'


class SharedFile(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='shared_files')
    file = models.FileField(upload_to='shared_files/')
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class SharedURL(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='shared_urls')
    url = models.URLField(max_length=200)
    description = models.TextField(blank=True, null=True)
    shared_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    shared_at = models.DateTimeField(auto_now_add=True)

class SharedNote(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='shared_notes')
    note = models.TextField()
    added_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    

class Task(models.Model):
    PROJECT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('On Hold', 'On Hold'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=PROJECT_STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    progress_percentage = models.FloatField(default=0.0)
    
    def save(self, *args, **kwargs):
        if self.start_date and self.start_date == timezone.now().date():
            self.status = 'In Progress'
        super().save(*args, **kwargs)
        
    
        
        
        


class FreelanceContract(models.Model):
    client = models.ForeignKey(CustomUser, related_name='client_contracts', on_delete=models.CASCADE)
    freelancer = models.ForeignKey(CustomUser, related_name='freelancer_contracts', on_delete=models.CASCADE)

    project = models.OneToOneField(Project, related_name='contract', on_delete=models.CASCADE)

    client_signature = models.ImageField(upload_to='signatures/client/', null=True, blank=True)
    freelancer_signature = models.ImageField(upload_to='signatures/freelancer/', null=True, blank=True)
    contract_date = models.DateField(auto_now_add=True)

    pdf_version = models.FileField(upload_to='contracts/', null=True, blank=True)

    def __str__(self):
        return f'Contract {self.id} for Project {self.project_id}'
    

class PaymentInstallment(models.Model):
    contract = models.ForeignKey(FreelanceContract, related_name='installments', on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ], default='pending')
    
    razorpay_order_id = models.CharField(max_length=255, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=255, null=True, blank=True)
    paid_at=models.DateField(null=True, blank=True)
    def __str__(self):
        return f'Installment {self.id} for Contract {self.contract.id}'
    
    
    
    
    

from django.core.validators import MinValueValidator, MaxValueValidator

class Review(models.Model):
    project = models.ForeignKey('client.Project', on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey('core.CustomUser', on_delete=models.CASCADE, related_name='reviews_given')
    reviewee = models.ForeignKey('core.CustomUser', on_delete=models.CASCADE, related_name='reviews_received')
    review_text = models.TextField()
    overall_rating = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        default=0
    )
    quality_of_work = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True, blank=True,
        default=0
    )
    communication = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True, blank=True,
        default=0
    )
    adherence_to_deadlines = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True, blank=True,
        default=0
    )
    professionalism = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True, blank=True,
        default=0
    )
    problem_solving_ability = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True, blank=True,
        default=0
    )
    review_date = models.DateTimeField(auto_now_add=True)
    
    
    
    

    
    
    
    

class ChatRoom(models.Model):
    participants = models.ManyToManyField('core.CustomUser', related_name='chat_rooms')
    project = models.ForeignKey('client.Project', on_delete=models.CASCADE, related_name='chat_rooms')

    def __str__(self):
        return f"Chat Room {self.id} for Project {self.project.id}"

    
    
class Message(models.Model):
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('core.CustomUser', on_delete=models.CASCADE, related_name='sent_messages')
    
    # Fields for different types of content
    content = models.TextField(null=True, blank=True)  # Text content
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)  # Image content
    file = models.FileField(upload_to='chat_files/', null=True, blank=True)  # File content
    
    # Timestamp for the message
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Message from {self.sender.username} in {self.chat_room} at {self.timestamp}"

    def has_content(self):
        return bool(self.content or self.image or self.file)
    
    
    
    
    
    
class Complaint(models.Model):
    COMPLAINT_TYPE_CHOICES = [
        ('Client', 'Complaint about Client'),
        ('Freelancer', 'Complaint about Freelancer'),
        ('Site Issue', 'Site Issue'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Resolved', 'Resolved'),
        ('Rejected','Rejected')
    ]
    RESOLUTION_STATUS_CHOICES = [
    ('Satisfactory', 'Satisfactory'),
    ('Unsatisfactory', 'Unsatisfactory'),
    ('Pending', 'Pending'),  # New status added
]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='complaints')  # Complainant
    complainee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_complaints')  # Complainee (only for Client and Freelancer complaints)
    complaint_type = models.CharField(max_length=20, choices=COMPLAINT_TYPE_CHOICES)
    subject = models.CharField(max_length=100)  # Added field for subject
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    date_filed = models.DateTimeField(auto_now_add=True)
    resolution = models.TextField(null=True, blank=True)
    resolution_status = models.CharField(max_length=15, choices=RESOLUTION_STATUS_CHOICES, null=True, blank=True, default='Pending')
    resolution_date = models.DateTimeField(null=True, blank=True)  # New field for resolution date

    def save(self, *args, **kwargs):
        # Check if the complaint is resolved and set the resolution date
        if self.status == 'Resolved' and not self.resolution_date:
            self.resolution_date = timezone.now()
        
        # Automatically reject if not resolved within 30 days
        if self.date_filed and self.status != 'Resolved':
            if timezone.now() > self.date_filed + timezone.timedelta(days=30):
                self.status = 'Rejected'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subject} - {self.complaint_type} Complaint by {self.user}"
