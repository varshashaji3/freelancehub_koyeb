import math
import os
import random
import uuid
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import render,redirect

from client.models import ClientProfile, Project, Review
from .models import EmailVerification, Notification, PasswordReset, CustomUser, Register, SiteReview
from django.core.mail import EmailMessage
from django.contrib import messages
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout 
from freelancer.views import freelancer_view
from client.views import client_view
from administrator.views import admin_view
from urllib.parse import urlparse, parse_qs, urlunparse
from urllib.parse import urlencode
from django.http import JsonResponse


def index(request):
    close_expired_projects()
    reviews = SiteReview.objects.all().order_by('-created_at')

    # Add counts for facts section
    client_count = CustomUser.objects.filter(role='client', status='active').count()
    freelancer_count = CustomUser.objects.filter(role='freelancer', status='active').count()
    project_count = Project.objects.filter(project_status='Completed').count()  # Changed to 'Completed' with capital C

    if request.user.is_authenticated or 'uid' in request.session:
        uid = request.user
        print(uid)
        return redirect_based_on_user_type(request, request.user)
        
    review_details = []
    for review in reviews:
        user = review.user
        user_info = {}

        if hasattr(user, 'register'): 
            register = user.register
            user_type = user.role 
            
            if user_type == 'freelancer':
                user_info = {
                    'name': f"{register.first_name} {register.last_name}",
                    'profile_picture': register.profile_picture.url if register.profile_picture else None
                }
            elif user_type == 'client':
                try:
                    client_profile = ClientProfile.objects.get(user=user)
                    if client_profile.client_type == 'Individual':
                        user_info = {
                            'name': f"{register.first_name} {register.last_name}",
                            'profile_picture': register.profile_picture.url if register.profile_picture else None
                        }
                    else:
                        user_info = {
                            'name': client_profile.company_name,
                            'profile_picture': register.profile_picture.url if register.profile_picture else None
                        }
                except ClientProfile.DoesNotExist:
                    user_info = None
        
        review_details.append({
            'review': review,
            'user_info': user_info
        })

    context = {
        'review_details': review_details,
        'client_count': client_count,
        'freelancer_count': freelancer_count,
        'project_count': project_count,
    }

    return render(request, 'index.html', context)


def check_email(request):
    email = request.POST.get('email', None)
    data = {
        'is_taken': CustomUser.objects.filter(email__iexact=email).exists()
    }
    return JsonResponse(data)


def close_expired_projects():
    now = timezone.now()
    expired_projects = Project.objects.filter(end_date__lt=now, status='open')
    count = expired_projects.update(status='closed')
    return count
    




def about(request):
    if request.user.is_authenticated:
        uid=request.user
        return redirect_based_on_user_type(request, request.user)
    return render(request,'about.html')

def contact(request):
    if request.user.is_authenticated:
        uid=request.user
        return redirect_based_on_user_type(request, request.user)
    if request.method == 'POST':
        name = request.POST.get('name')
        subjects = request.POST.get('subject')
        sender = request.POST.get('email')
        recipient = 'freelancehub76@gmail.com'
        message = request.POST.get('message')
        msg = message + '\n\n\nEmail : ' + sender
        from_email = name

        email = EmailMessage(
            subject=subjects,
            body=msg,
            from_email=from_email,
            to=[recipient],
            reply_to=[sender]
            )

        email.send(fail_silently=False)
        msg = "Thank you for contacting us. We will get back to you soon."
        return render(request, 'contact.html', {'msg': msg})
    return render(request, 'contact.html')

def service(request):
    if request.user.is_authenticated:
        uid=request.user
        return redirect_based_on_user_type(request, request.user)
    return render(request,'service.html')


def login_view(request):
    if request.user.is_authenticated and request.user.status=='active' :
        print(f"User {request.user} is already authenticated, redirecting...")
        return redirect_based_on_user_type(request, request.user)
    
    return render(request, 'login.html', {'page': 'sign-in'})



def register_view(request):
    if request.user.is_authenticated:
        print(f"User {request.user} is already authenticated, redirecting...")
        return redirect_based_on_user_type(request, request.user)
    print("Rendering register page")
    return render(request, 'login.html', {'page': 'sign-up'})

def faqs(request):
    if request.user.is_authenticated:
        uid=request.user
        return redirect_based_on_user_type(request, request.user)
    return render(request,'faqs.html')


from allauth.socialaccount.models import SocialAccount
def login(request):
    if request.method == 'POST':
        email = request.POST.get('mail')
        password = request.POST.get('pass')
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if not user.welcome_email_sent:
                user.welcome_email_sent = True
                user.save()
                
                send_welcome_email(request, user)
                
            return redirect_based_on_user_type(request, user)
        
        else:
            return render(request, 'login.html', {'error_msg': 'Invalid credentials', 'page': 'sign-in'})
    
    elif request.user.is_authenticated:
        user = request.user
        user_id = user.id
        socialacc = SocialAccount.objects.filter(user_id=user_id).first()
        if socialacc:
            user.email_verified = True
            user.google = True
            user.save()
        
        if not user.welcome_email_sent:
            user.welcome_email_sent = True
            user.save()
            
            send_welcome_email(request, user)
                
        return redirect_based_on_user_type(request, user)
    
    url_parts = urlparse(request.get_full_path())
    query = parse_qs(url_parts.query)
    if 'next' in query:
        query.pop('next')
        url_parts = url_parts._replace(query=urlencode(query, doseq=True))
        clean_url = urlunparse(url_parts)
        return HttpResponseRedirect(clean_url)
    
    return render(request, 'login.html', {'page': 'sign-in'})



def redirect_based_on_user_type(request, user):
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    print(f"Redirecting user: {user}")
    
    existing_entry = Register.objects.filter(user_id=user.id).first()
    if not existing_entry:
        user2 = Register(user_id=user.id)
        user2.save()
        print(f"Created Register entry for user: {user}")
    
    print(f"User role: {user.role}")
    if not user.role:
        print(f"User role not set, redirecting to add_user_type for user: {user}")
        return add_user_type(request, user.id)
    
    if user.status != 'active':
        print(f"User status is not active, logging out user: {user}")
        return redirect('logout')
    
    
    if user.role == 'admin':
        auth_login(request, user)
        request.session['uid'] = user.id
        print(f"Redirecting admin user: {user}")
        return redirect('administrator:admin_view')
    elif user.role == 'client':
        auth_login(request, user)
        request.session['uid'] = user.id
        print(f"Redirecting client user: {user}")
        return redirect('client:client_view')
    elif user.role == 'freelancer':
        auth_login(request, user)
        request.session['uid'] = user.id
        print(f"Redirecting freelancer user: {user}")
        return redirect('freelancer:freelancer_view')
    else:
        print(f"User role is undefined, redirecting to login for user: {user}")
        return redirect('login')




def register(request):
    if request.method == 'POST':
        fname = request.POST.get('fname')
        lname = request.POST.get('lname')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if CustomUser.objects.filter(username=fname).exists() or CustomUser.objects.filter(email=email).exists():
            return render(request, 'login.html', {'page':'sign-up','error_msg': 'User with this email already exists'})
        else:
            user_type=''
            user = CustomUser.objects.create_user(username=fname,email=email, password=password,role=user_type)
            user.role = user_type
            user.save()
            
            uid=user.id
            reg=Register.objects.create(user_id=uid,first_name=fname,last_name=lname)
            reg.save()
            return redirect('add_user_type', uid=user.id)
        
            
    else:
        return redirect(register_view)



def add_user_type(request,uid):
    
    user = CustomUser.objects.get(id=uid)
    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        user.role=user_type
        user.save()
        return redirect(login)
    return render(request, 'register.html', {'uid': uid,'user':user})
    
    

def send_welcome_email(request,user):
    subject = 'Welcome to FreelanceHub'
    context = {
        'user': user
    }
    html_content = render_to_string('welcome.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()
    



def logout(request):
    auth_logout(request)
    for key in list(request.session.keys()):
        del request.session[key]
    return HttpResponseRedirect(reverse('login'))





def send_forget_password_mail(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            token = str(uuid.uuid4())
            msg = request.build_absolute_uri(f'/reset_password/{token}/')
            context = {
                'user': user,
                'reset_link': msg
            }
            html_content = render_to_string('forgot_password.html', context)
            text_content = strip_tags(html_content)
            email = EmailMultiAlternatives('Password Reset', text_content, settings.EMAIL_HOST_USER, [user.email])
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            # Add expiration time of 1 minute
            expires_at = timezone.now() + timezone.timedelta(minutes=1)
            data = PasswordReset.objects.create(user_id=user, token=token, expires_at=expires_at)
            return redirect('login_view')
        except CustomUser.DoesNotExist:
            return render(request, 'mail_read.html', {'error': 'User with this email does not exist'})

    return render(request, 'mail_read.html')



def reset_password(request, token):
    reset_user = PasswordReset.objects.filter(token=token).first()

    if reset_user is None:
        return render(request, 'password_reset.html', {'error': 'Invalid or expired token'})

    uid = reset_user.user_id.id
    sent_time = reset_user.created_at  # Capture the sent time

    if request.method == 'POST':
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']
        user_id = request.POST.get('user_id')

        if user_id is None:
            return render(request, 'password_reset.html', {'error': 'No user found'})

        if new_password != confirm_password:
            return render(request, 'password_reset.html', {'error': 'Passwords do not match'})

        user_obj = CustomUser.objects.get(id=user_id)
        user_obj.set_password(new_password)
        user_obj.save()
        
        # Delete the token after password reset
        reset_user.delete()  # Remove the PasswordReset entry
        
        return redirect('login_view')

    return render(request, 'password_reset.html', {'user_id': uid, 'sent_time': sent_time})  # Pass sent_time to the template

def resend_password_link(request):
    if request.method == 'POST':
        reset_user_id = request.POST.get('user_id')  # Changed variable name for clarity
        try:
            # Ensure reset_user_id is not None
            if reset_user_id is None:
                return JsonResponse({'success': False, 'error': 'Invalid or expired token.'})

            # Fetch the PasswordReset entry using the reset_user_id
            reset_user = PasswordReset.objects.filter(user_id=reset_user_id).first()  
            if reset_user is None:  # Check if reset_user exists
                return JsonResponse({'success': False, 'error': 'Invalid or expired token.'})

            user = reset_user.user_id  # Get the user associated with the reset request
            
            # Remove expired tokens
            PasswordReset.objects.filter(user_id=user, expires_at__lt=timezone.now()).delete()

            # Create a new token
            new_token = str(uuid.uuid4())
            expires_at = timezone.now() + timezone.timedelta(minutes=1)  # Set expiration time to 1 minute from now

            # Create a new PasswordReset entry
            PasswordReset.objects.create(user_id=user, token=new_token, expires_at=expires_at)

            # Prepare the reset link
            msg =  request.build_absolute_uri(f'/reset_password/{new_token}/')
            context = {
                'user': user,
                'reset_link': msg
            }
            html_content = render_to_string('forgot_password.html', context)
            text_content = strip_tags(html_content)
            email_msg = EmailMultiAlternatives('Password Reset', text_content, settings.EMAIL_HOST_USER, [user.email])
            email_msg.attach_alternative(html_content, "text/html")
            email_msg.send(fail_silently=False)  # Ensure fail_silently is set to False for debugging

            # Redirect to password_reset.html with success message
            return render(request, 'password_reset.html', {'success_msg': 'New password reset link sent.'})
        except CustomUser.DoesNotExist:
            return render(request, 'password_reset.html', {'error': 'User not found.'})

    return render(request, 'password_reset.html', {'error': 'Invalid request.'})



def send_verification_mail(request):
    email = request.user.email
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('login_view')

    token = str(uuid.uuid4())
    
    verification_link =  request.build_absolute_uri(f'/email_verification/{token}/')
    context = {
        'user': user,
        'reset_link': verification_link,
    }
    
    html_content = render_to_string('mail_send.html', context)
    text_content = strip_tags(html_content)
 
    email_msg = EmailMultiAlternatives('Email Verification', text_content, settings.EMAIL_HOST_USER, [user.email])
    email_msg.attach_alternative(html_content, "text/html")
    email_msg.send()
    
    # Add expiration time of 5 minutes
    expires_at = timezone.now() + timezone.timedelta(minutes=5)
    EmailVerification.objects.create(user_id=user, token=token, expires_at=expires_at)
    messages.success(request, 'Verification email sent. Please check your inbox.')
    
    return redirect('login_view')



def email_verification(request, token):
    verification = EmailVerification.objects.filter(token=token).first()
    if not verification:
        print('Invalid or expired token.')
        return redirect('login_view')
    
    # Check if the token has expired
    is_expired = False
    if verification.expires_at:
        is_expired = verification.expires_at < timezone.now()
    else:
        print('Expiration time not set for this token.')
    
    if is_expired:
        print('Token has expired.')
        return render(request, 'email_verification.html', {'expired': True})

    uid = verification.user_id_id
    user = CustomUser.objects.get(id=uid) 
    user.email_verified = True
    user.save()
    verification.delete()

    print('Email verified successfully.')

    context = {
        'token': token,
        'expired': is_expired,
        'verified': True
    }
    return render(request, 'email_verification.html', context)



def resend_verification_email(request):
    if request.method == 'POST':
        token = request.POST.get('token')
        verification = EmailVerification.objects.filter(token=token).first()
        if verification:
            user = verification.user_id  
            
            verification.delete()
            
            new_token = str(uuid.uuid4())
            verification_link = request.build_absolute_uri(f'/email_verification/{new_token}/')
            context = {
                'user': user,
                'reset_link': verification_link,
            }
            
            html_content = render_to_string('mail_send.html', context)
            text_content = strip_tags(html_content)

            email_msg = EmailMultiAlternatives('Email Verification', text_content, settings.EMAIL_HOST_USER, [user.email])
            email_msg.attach_alternative(html_content, "text/html")
            email_msg.send()

            # Create a new EmailVerification entry with the new token
            EmailVerification.objects.create(user_id=user, token=new_token)

            return redirect('login_view')    







@login_required
def site_review(request):
    if request.method == 'POST':
        review_text = request.POST.get('review_text')
        rating = request.POST.get('rating')
        user = request.user 

        if review_text and rating:
            SiteReview.objects.create(
                user=user, 
                review_text=review_text,
                rating=rating
            )
            admin_user = CustomUser.objects.get(id=1)
            Notification.objects.create(
                user=admin_user,
                message=f'New review submitted by {user.username}: {review_text} (Rating: {rating})'
            )
            next_url = request.POST.get('next', '/')
            return redirect(next_url)
        
        
# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CancellationRequest
from client.models import Project,Repository

@login_required
def request_cancellation(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    repository=Repository.objects.get(project=project.id)
    if request.method == 'POST':
        reason=request.POST.get("cancellation_reason")
        if request.user == project.user:  
            approver = project.freelancer  
        else:
            approver = project.user  

        cancellation_request = CancellationRequest.objects.create(
            project=project,
            requested_by=request.user,
            approver=approver,
            status='Pending',
            reason=reason
        )
        
        messages.success(request, 'Cancellation request submitted successfully.')
        
        Notification.objects.create(
            user=approver,
            message=f'You have a new cancellation request for project: {project.title}.'
        )

        return redirect('client:view_repository', repository.id) if request.user == project.user else redirect('freelancer:view_repository', repository.id)


from client.models import FreelanceContract,PaymentInstallment
from core.models import RefundPayment
from django.http import JsonResponse
from django.utils import timezone

from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum

from decimal import Decimal  # Make sure Decimal is imported

def update_cancellation_status(request, cancellation_id):
    if request.method == 'POST':
        status = request.POST.get('status')
        try:
            cancellation = CancellationRequest.objects.get(id=cancellation_id)
            cancellation.status = status
            cancellation.response_date = timezone.now()
            cancellation.save()
            
            if status == 'Approved':  
                project = cancellation.project  
                project.project_status = 'Cancelled'  
                project.save()  
                
                # Fetch related data
                budget = project.budget
                tasks = project.task_set.all()

                total_tasks = tasks.count()
                completed_tasks = tasks.filter(status='completed').count()
                
                amount_per_task = Decimal(budget) / Decimal(total_tasks) if total_tasks > 0 else Decimal('0')
                
                total_completed_amount = Decimal(completed_tasks) * amount_per_task
                compensation_amount = Decimal(budget) * Decimal('0.10')
                
                total_paid_result = PaymentInstallment.objects.filter(contract=project.contract).aggregate(Sum('amount'))
                total_paid = total_paid_result['amount__sum'] or Decimal('0')
                total_paid -= project.gst_amount
                
                # Determine if the requester is a client or freelancer
                if cancellation.requested_by == project.user:  # Client cancels
                    if total_paid > total_completed_amount:
                        overpayment = total_paid - total_completed_amount
                        if overpayment >= compensation_amount:
                            # Sufficient overpayment for compensation, refund excess overpayment
                            amount_due = Decimal('0')
                            refund_amount = overpayment - compensation_amount
                            if refund_amount > Decimal('0'):
                                RefundPayment.objects.create(
                                    user_id=project.freelancer.id,
                                    pay_to=cancellation.requested_by,  # Refund to client
                                    amount=refund_amount,
                                    total_paid=total_paid,  # New entry
                                    compensation_amount=compensation_amount  # New entry
                                )
                                print(f"Refund entry created: {refund_amount} from freelancer {project.freelancer.id} to client {cancellation.requested_by.id}")
                        else:
                            # Not enough overpayment for compensation
                            amount_due = compensation_amount - overpayment
                            RefundPayment.objects.create(
                                user_id=cancellation.requested_by.id,
                                pay_to=project.freelancer,  # Pay to freelancer
                                amount=overpayment,
                                total_paid=total_paid,  # New entry
                                compensation_amount=compensation_amount  # New entry
                            )
                            print(f"Refund entry created: {overpayment} from client {cancellation.requested_by.id} to freelancer {project.freelancer.id}")
                    else:
                        # Client is underpaid
                        amount_due = (total_completed_amount - total_paid) + compensation_amount

                else:  # Freelancer cancels
                    if total_paid > total_completed_amount:
                        overpayment = total_paid - total_completed_amount
                        amount_due = overpayment + compensation_amount
                        RefundPayment.objects.create(
                            user_id=cancellation.requested_by.id,
                            pay_to=project.user,  # Pay to client
                            amount=amount_due,
                            total_paid=total_paid,  # New entry
                            compensation_amount=compensation_amount,  # New entry
                            project=project  # New entry
                        )
                        print(f"Refund entry created: {amount_due} from freelancer {cancellation.requested_by.id} to client {project.user.id}")
                    else:
                        # Freelancer is underpaid
                        amount_due = Decimal('0')

                print(f"Amount due for cancellation: {amount_due}")
            
            return JsonResponse({'success': True})
        except CancellationRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Cancellation not found.'})
    return JsonResponse({'success': False, 'error': 'Invalid request.'})

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from .models import RefundPayment  # Update the import to match your model path


@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        # Debug print statements to check the received data
        print("Received POST request for payment success")
        print(request.POST)

        # Get payment details from the request
        refund_payment_id = request.POST.get('refund_payment_id')
        payment_id = request.POST.get('payment_id')
        order_id = request.POST.get('order_id')

        if refund_payment_id and payment_id:
            try:
                # Update the RefundPayment entry in the database
                refund_payment = RefundPayment.objects.get(id=refund_payment_id)
                refund_payment.razorpay_payment_id = payment_id
                refund_payment.razorpay_order_id = order_id  # Save the order_id if needed
                refund_payment.is_paid = True
                refund_payment.payment_date = timezone.now()
                refund_payment.save()

                # Return a JSON response indicating success
                return JsonResponse({'status': 'success'})
            except RefundPayment.DoesNotExist:
                return JsonResponse({'status': 'failed', 'error': 'Refund payment not found'}, status=404)
        else:
            return JsonResponse({'status': 'failed', 'error': 'Invalid data received'}, status=400)
    

















