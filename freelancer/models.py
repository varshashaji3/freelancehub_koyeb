from django.db import models

from client.models import Project
from core.models import CustomUser  

    
from ckeditor.fields import RichTextField
from django.utils import timezone
class FreelancerProfile(models.Model):
    

    WORK_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
    ]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    professional_title = models.TextField(max_length=255)
    skills = models.TextField(max_length=255)
    experience_level = models.CharField(max_length=50, blank=True, null=True)
    portfolio_link = models.URLField(max_length=255, blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    aadhaar_document = models.FileField(upload_to='aadhaar/', null=True, blank=True)
    work_type = models.CharField(max_length=10, choices=WORK_TYPE_CHOICES, default='part_time')
    is_open_to_work = models.BooleanField(default=False)  # New field added
    hiring_status = models.CharField(max_length=20, choices=[
        ('NOT_HIRED', 'Not Hired'),
        ('HIRED', 'Hired'),
    ], default='NOT_HIRED')
    def __str__(self):
        return f"{self.user.username}'s Profile"

class Todo(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=50,default=None)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    

class Proposal(models.Model):
    PENDING = 'Pending'
    ACCEPTED = 'Accepted'
    REJECTED = 'Rejected'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='proposals')
    
    freelancer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='proposals')

    date_issued = models.DateField(default=timezone.now)
    proposal_details = RichTextField()  
    budget = models.DecimalField(max_digits=10, decimal_places=2)  
    deadline = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    fancy_num=models.CharField(max_length=5, unique=True, blank=True)
    proposal_file = models.FileField(upload_to='proposals/', null=True, blank=True)
    locked = models.BooleanField(default=False)
    team_id = models.ForeignKey('Team', on_delete=models.SET_NULL, null=True, blank=True)
    

    

class ProposalFile(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='proposal_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


from administrator.models import Template

class Document(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    resume_file = models.FileField(upload_to='resume/', null=True, blank=True)
    portfolio_file = models.FileField(upload_to='portfolios/', null=True, blank=True)
    template = models.ForeignKey(Template, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    cover_image = models.ImageField(upload_to='cover_images/', null=True, blank=True) 
    
    def __str__(self):
        return f"{self.user.username} - {self.template.name if self.template else 'No Template'} - {self.id}"


from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Team(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    join_code = models.CharField(max_length=8, unique=True)

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class TeamMember(models.Model):
    ROLE_CHOICES = [
        ('PROJECT_MANAGER', 'Project Manager & Team Leader'),
        ('DESIGNER', 'Designer (UI/UX)'),
        ('FRONTEND_DEV', 'Frontend Developer'),
        ('BACKEND_DEV', 'Backend Developer'),
        ('QA_TESTER', 'Quality Assurance Tester'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships',null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    salary_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0,null=True, blank=True)

    class Meta:
        unique_together = ('team', 'user')

class TeamInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=TeamMember.ROLE_CHOICES)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        if not self.expires_at:
            self.expires_at = self.created_at + timezone.timedelta(days=15)
        super().save(*args, **kwargs)

    def is_valid(self):
        if timezone.now() >= self.expires_at:
            self.status = 'rejected'
            self.save()
            return False
        return True

    @classmethod
    def accept_invitation(cls, invitation_id):
        invitation = cls.objects.get(id=invitation_id)
        invitation.status = 'accepted'
        invitation.save()

        cls.objects.filter(team=invitation.team, role=invitation.role).exclude(id=invitation_id).update(
            status='rejected',
            expires_at=timezone.now()
        )

    @classmethod
    def check_expired_invitations(cls):
        expired_invitations = cls.objects.filter(expires_at__lt=timezone.now(), status='pending')
        expired_invitations.update(status='rejected')

class SalaryPayment(models.Model):
    team_member = models.ForeignKey(TeamMember, on_delete=models.CASCADE)  
    project = models.ForeignKey(Project, on_delete=models.CASCADE) 
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2) 
    payment_date = models.DateTimeField(auto_now_add=True) 
    paid_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)  
    status = models.CharField(max_length=20, default='pending')

    def __str__(self):
        return f"{self.team_member.user.username} - {self.amount_paid} on {self.payment_date} by {self.paid_by.username if self.paid_by else 'Unknown'}"