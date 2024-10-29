from client.models import Repository
from core.decorators import nocache
from core.models import CustomUser, Notification, Register, SiteReview
from client.models import Project

def unread_notifications(request):
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    else:
        unread_notifications = []
    return {'unread_notifications': unread_notifications}


def repository_list(request):
    if request.user.is_authenticated:
        assigned_projects = Project.objects.filter(freelancer=request.user)
        
        client_projects = Project.objects.filter(user=request.user)
        
        repositories = Repository.objects.filter(
            project__in=assigned_projects | client_projects
        ).distinct()
    else:
        repositories = []
    return {'repositories': repositories}



from django.shortcuts import get_object_or_404
from client.models import Project, ClientProfile

from django.contrib.auth.decorators import login_required
def project_status(request):
    context = {}
    current_user = request.user
    
    completed_projects = Project.objects.filter(
        project_status='Completed',
        freelancer=current_user.id
    ) | Project.objects.filter(
        project_status='Completed',
        user=current_user.id
    ).order_by('-project_end_date')  # Order by completion date, most recent first

    print("Completed Projects:")
    for project in completed_projects:
        freelancer = get_object_or_404(Register, user=project.freelancer)
        client_profile = get_object_or_404(ClientProfile, user=project.user)
        client_type = client_profile.client_type
        
        client_name = None
        client_id = None

        if client_type == 'Individual':
            client = get_object_or_404(Register, user=project.user)
            client_name = client.first_name
            client_id = client.user.id
        elif client_type == 'Company':
            client_name = client_profile.company_name
            client_id = project.user.id
        
        print(f"Project ID: {project.id}")
        print(f"Title: {project.title}")
        print(f"Status: {project.project_status}")
        print(f"Freelancer: {freelancer.first_name} (ID: {freelancer.user.id})")
        print(f"Client: {client_name} (ID: {client_id})")
        print(f"Client Type: {client_type}")
        print(f"Freelancer Review Given: {project.freelancer_review_given}")
        print(f"Client Review Given: {project.client_review_given}")
        print("---")

    # Find the most recent project that needs a review
    project_needing_review = completed_projects.filter(
        freelancer_review_given=False
    ).first() or completed_projects.filter(
        client_review_given=False
    ).first()

    if project_needing_review:
        freelancer = get_object_or_404(Register, user=project_needing_review.freelancer)
        client_profile = get_object_or_404(ClientProfile, user=project_needing_review.user)
        client_type = client_profile.client_type
        
        client_name = None
        client_id = None

        if client_type == 'Individual':
            client = get_object_or_404(Register, user=project_needing_review.user)
            client_name = client.first_name
            client_id = client.user.id
        elif client_type == 'Company':
            client_name = client_profile.company_name
            client_id = project_needing_review.user.id
        
        context['project_status'] = {
            'status': project_needing_review.project_status,
            'freelancer_name': freelancer.first_name,
            'client_name': client_name,
            'project_id': project_needing_review.id,
            'freelancer_id': freelancer.user.id,
            'client_id': client_id,
            'project_title': project_needing_review.title,
            'freelancer_review_given': project_needing_review.freelancer_review_given,
            'client_review_given': project_needing_review.client_review_given
        }
        
        is_client = client_profile.user == current_user
        context['is_client'] = is_client
    
    print("Context:", context)
    return context




from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import timedelta
def review_due(request):
    if request.user.is_authenticated:
        user = request.user
        registration_date = user.joined
        now = timezone.now()
        threshold_date = registration_date + timedelta(days=90)  
        
        existing_review = SiteReview.objects.filter(user=user).order_by('-created_at').first()
        
        if existing_review:
            last_review_date = existing_review.created_at
            if now >= last_review_date + timedelta(days=90):
                return {'review_due': True}
            else:
                return {'review_due': False}
        else:
            if now >= threshold_date:
                return {'review_due': True}
            else:
                return {'review_due': False}
    return {'review_due': False}


import razorpay
from django.conf import settings
from .models import RefundPayment
def refund_payment_context(request):
    context = {}
    if request.user.is_authenticated:
        refund_payment = RefundPayment.objects.filter(user_id=request.user.id).first()
        if refund_payment:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            amount_in_paisa = int(refund_payment.amount * 100)  # Convert to paisa as Razorpay expects amounts in paisa
            data = {
                "amount": amount_in_paisa,
                "currency": "INR",
                "receipt": f"refund_{refund_payment.id}",
                "payment_capture": 1,
            }
            order = client.order.create(data=data)

            context.update({
                'has_refund_payment': True,
                'refund_payment': refund_payment,
                'razorpay_order_id': order['id'],
                'razorpay_key': settings.RAZORPAY_KEY_ID,
                'amount_in_paisa': amount_in_paisa,
            })
        else:
            context['has_refund_payment'] = False

    return context
