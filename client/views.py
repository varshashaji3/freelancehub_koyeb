import datetime
import os
from django.contrib import messages
from django.shortcuts import redirect, render
import razorpay

from client.models import ClientProfile, FreelanceContract, PaymentInstallment, Project, Review, SharedFile, SharedNote, SharedURL, Task, ChatRoom, Message,Complaint,JobInvitation  # Add Message here
from core.decorators import nocache
from core.models import CustomUser, Event, Notification, Register


from django.contrib.auth.decorators import login_required

from freelancer.models import FreelancerProfile, Proposal, ProposalFile,Team,TeamMember
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from xhtml2pdf import pisa
from datetime import date

from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField
from .models import JobInvitation
from django.contrib.auth.models import User
from django.urls import reverse 
@login_required
@nocache
def client_view(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    logged_user = request.user
    current_date = datetime.date.today()
    one_week_later = current_date + datetime.timedelta(days=7)

    events = Event.objects.filter(user=logged_user, start_time__range=[current_date, one_week_later])

    profile1 = CustomUser.objects.get(id=logged_user.id)
    profile2 = Register.objects.get(user_id=logged_user.id)
    
    client, created = ClientProfile.objects.get_or_create(user_id=logged_user.id)
    notifications = Notification.objects.filter(user=logged_user).order_by('-created_at')[:5]

    for event in events:
        one_day_before = event.start_time.date() - datetime.timedelta(days=1)
        if one_day_before == current_date:
            Notification.objects.get_or_create(
                user=logged_user,
                message=f"Reminder: Upcoming event '{event.title}' tomorrow!",
                defaults={'is_read': False}
            )
        if event.start_time.date() == current_date:
            Notification.objects.get_or_create(
                user=logged_user,
                message=f"Reminder: Event '{event.title}' is today!",
                defaults={'is_read': False}
            )

    client_projects = Project.objects.filter(user=logged_user).select_related('freelancer', 'freelancer__register')  # Ensure freelancer and their register info are included
    project_progress_data = []

    # Project progress data
    for project in client_projects:
        tasks = Task.objects.filter(project=project)
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='Completed').count()
        progress_percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0.0

    
            
        project_progress_data.append({
            'project': project,
            'progress_percentage': progress_percentage,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks
        })

    total_projects = client_projects.count()
    completed_projects = client_projects.filter(project_status='Completed').count()
    not_completed_projects = total_projects - completed_projects
    
    client_contracts = FreelanceContract.objects.filter(client=logged_user).select_related('freelancer', 'project')
    
    # Order installments with pending first, then by due date
    payment_installments = PaymentInstallment.objects.filter(contract__in=client_contracts).annotate(
        sort_order=Case(
            When(status='pending', then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('sort_order', 'due_date')

    # Pagination
    paginator = Paginator(payment_installments, 5)  # Show 5 installments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for installment in payment_installments:
        due_date = installment.due_date
        one_day_before_due = due_date - datetime.timedelta(days=1)
        
        if installment.status == 'Pending':
            if one_day_before_due == current_date:
                Notification.objects.get_or_create(
                    user=logged_user,
                    message=f"Reminder: Payment installment for project '{installment.contract.project.title}' is due tomorrow!",
                    defaults={'is_read': False}
                )
            elif due_date == current_date:
                Notification.objects.get_or_create(
                    user=logged_user,
                    message=f"Reminder: Payment installment for project '{installment.contract.project.title}' is due today!",
                    defaults={'is_read': False}
                )

    if not profile2.phone_number and not profile2.profile_picture and not profile2.bio_description and not profile2.location:
        return render(request, 'Client/Add_profile.html', {
            'profile2': profile2,
            'profile1': profile1,
            'uid': logged_user.id,
            'notifications': notifications,
            'events': events
        })

    return render(request, 'Client/index.html', {
        'profile2': profile2,
        'profile1': profile1,
        'client': client,
        'uid': logged_user.id,
        'notifications': notifications,
        'events': events,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'not_completed_projects': not_completed_projects,
        'project_progress_data': project_progress_data,
        'page_obj': page_obj
    })




from django.views.decorators.http import require_POST

@login_required
@require_POST
def mark_project_completed(request):
    try:
        project_id = request.POST.get('project_id')
        project = Project.objects.get(id=project_id, user=request.user)
        
        # Update project status
        project.project_status = 'Completed'
        project.project_end_date = timezone.now()  # Changed from datetime.now()
        project.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Project marked as completed successfully'
        })
    except Project.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Project not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)



import joblib
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from django.http import HttpResponseServerError



def convert_to_days(date_input):
    if pd.isna(date_input):
        return None
    
    if isinstance(date_input, datetime.date):
        proposed_date = date_input
    elif isinstance(date_input, str):
        try:
            proposed_date = datetime.strptime(date_input, '%Y-%m-%d').date()
        except ValueError:
            return None
    else:
        return None
    
    days_remaining = (proposed_date - datetime.date.today()).days
    return days_remaining










client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required
@nocache
def make_payment(request, installment_id):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        if request.method == 'POST':
            installment = get_object_or_404(PaymentInstallment, id=installment_id)
            
            if installment.status == 'paid':
                return JsonResponse({'status': 'error', 'message': 'This installment has already been paid.'})
            
            # Create Razorpay order
            order_amount = int(installment.amount * 100)  # Convert to paise
            order_currency = 'INR'
            order_receipt = f'installment_{installment.id}'
            
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            try:
                order = client.order.create({
                    'amount': order_amount,
                    'currency': order_currency,
                    'receipt': order_receipt,
                    'payment_capture': '1'
                })
                installment.razorpay_order_id = order['id']
                installment.save()
                response_data = {
                    'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                    'order_id': order['id'],
                    'amount': order_amount,
                    'currency': order_currency,
                    'installment_id': installment.id,
                }
                
                return JsonResponse(response_data)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })


@csrf_exempt
def verify_payment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        signature = data.get('razorpay_signature')

        if not (payment_id and order_id and signature):
            return JsonResponse({'status': 'error', 'message': 'Missing parameters'})

        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            client.utility.verify_payment_signature(params_dict)
            installment = get_object_or_404(PaymentInstallment, razorpay_order_id=order_id)
            installment.status = 'paid'
            installment.razorpay_payment_id = payment_id
            installment.paid_at=timezone.now().date()
            installment.save()
            
            return JsonResponse({'status': 'success'})
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'status': 'error', 'message': 'Payment verification failed: Signature mismatch'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})



def payment_success(request):
    installment_id = request.GET.get('installment_id')
    
    if not installment_id:
        return HttpResponse("No installment ID provided.", status=400)
    
    installment = get_object_or_404(PaymentInstallment, id=installment_id)
    
    installment.status = 'paid'
    installment.save()

    return render(request, 'Client/success.html', {'installment': installment})



@login_required
@nocache
def notification_mark_as_read(request,not_id):
    notification = Notification.objects.get(id=not_id)
    notification.is_read = True
    notification.save()
    next_url = request.GET.get('next', 'client:client_view')
    return redirect(next_url)

@login_required
@nocache
def AddProfileClient(request, uid):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session.get('uid', uid)  # Retrieve uid from session if not passed in URL
    profile = Register.objects.get(user_id=uid)
    client_profile, created = ClientProfile.objects.get_or_create(user_id=uid)

    if request.method == 'POST':
        # Fetching data from POST request
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        phone_number = request.POST.get('phone_number')
        profile_picture = request.FILES.get('profile_picture')
        bio_description = request.POST.get('bio_description')
        location = request.POST.get('location')
        linkedin = request.POST.get('linkedin')
        instagram = request.POST.get('instagram')
        twitter = request.POST.get('twitter')
        client_type = request.POST.get('client_type')
        company_name = request.POST.get('company_name')
        website = request.POST.get('company_website')
        aadhar = request.FILES.get('aadhar')
        license_number = request.POST.get('license_number')  # CIN number

        # Update Register profile
        profile.first_name = first_name
        profile.last_name = last_name
        profile.phone_number = phone_number
        if profile_picture:
            profile.profile_picture = profile_picture
        profile.bio_description = bio_description
        profile.location = location
        profile.linkedin = linkedin
        profile.instagram = instagram
        profile.twitter = twitter
        profile.save()

        # Update ClientProfile
        client_profile.client_type = client_type
        if client_type == 'Company':
            client_profile.company_name = company_name
            client_profile.website = website
            client_profile.license_number = license_number  # Save CIN number
            client_profile.aadhaar_document = ''
        else:
            client_profile.company_name = ''
            client_profile.website = ''
            client_profile.license_number = ''
            client_profile.aadhaar_document = aadhar
        client_profile.save()

        return redirect('client:client_view')

    return render(request, 'Client/add_profile_client.html', {'profile': profile, 'client_profile': client_profile})


@login_required
@nocache   
def update_profile(request, uid):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)

    if request.method == 'POST':
        # Fetch POST data
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        phone_number = request.POST.get('phone_number')
        bio_description = request.POST.get('bio_description')
        location = request.POST.get('location')
        linkedin = request.POST.get('linkedin')
        instagram = request.POST.get('instagram')
        twitter = request.POST.get('twitter')
        license_number = request.POST.get('license_number')
        company_name = request.POST.get('company_name')
        website = request.POST.get('company_website')
        aadhar = request.FILES.get('aadhar')

        # Update Register model fields
        profile2.first_name = first_name
        profile2.last_name = last_name
        profile2.phone_number = phone_number
        profile2.bio_description = bio_description
        profile2.location = location
        profile2.linkedin = linkedin
        profile2.instagram = instagram
        profile2.twitter = twitter
        profile2.save()

        # Update ClientProfile model fields
        client_type = client.client_type
        if client_type == 'Company':
            client.company_name = company_name
            client.website = website
            client.license_number = license_number
            client.aadhaar_document = ''
        else:
            client.company_name = ''
            client.website = ''
            client.license_number = ''
            client.aadhaar_document = aadhar

        client.save()

        return redirect('client:account_settings')

    return render(request, 'Client/profile.html', {'profile1': profile1, 'profile2': profile2, 'client': client})



@login_required
@nocache
def account_settings(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role!='client':
        return redirect('login')
    uid=request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    client=ClientProfile.objects.get(user_id=uid)
    
    return render(request, 'Client/profile.html',{'profile1':profile1,'profile2':profile2,'client':client})





@login_required
@nocache
def change_password(request, uid):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    client=ClientProfile.objects.get(user_id=uid)

    if request.method == 'POST':
        current = request.POST.get('current_password')
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')

        
        if profile1.check_password(current):
            profile1.set_password(new_pass)
            profile1.save()
            messages.success(request, 'Your password has been changed successfully!')
            return render(request, 'Client/profile.html',{'profile1':profile1,'profile2':profile2,'client':client})
    
            
        else:
            messages.error(request, 'Current password is incorrect.')

    return render(request, 'Client/profile.html',{'profile1':profile1,'profile2':profile2,'client':client})
    
    
    
    
    
    

@login_required
@nocache
def change_profile_image(request,uid):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role!='client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    client=ClientProfile.objects.get(user_id=uid)
    
    if request.method=='POST':
        
        profile_picture = request.FILES.get('profile_picture')
        if profile_picture:
            profile2.profile_picture = profile_picture
            profile2.save()
            
            return redirect('client:account_settings')
    return render(request, 'Client/profile.html',{'profile1':profile1,'profile2':profile2,'client':client})

@login_required
@nocache
def download_invoice(request, contract_id):
    # Fetch the contract using the contract_id
    contract = get_object_or_404(FreelanceContract, id=contract_id)
    
    # Fetch related project and payment details
    project = contract.project
    payments = PaymentInstallment.objects.filter(contract_id=contract_id)
    today = date.today()  # Get today's date

    # Render the HTML template with context
    html_content = render_to_string('Client/InvoiceDownload.html', {
        'project': project,
        'payments': payments,
        'today': today
    })

    # Create a PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{contract_id}.pdf"'

    # Convert HTML to PDF
    pisa_status = pisa.CreatePDF(
       html_content, dest=response
    )

    # Return the response
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html_content + '</pre>')
    return response


        
@login_required
@nocache
def freelancer_list(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    uid = request.session.get('uid', request.user.id)
    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    client = get_object_or_404(ClientProfile, user_id=uid)
    
    if profile1.permission:
        search_query = request.GET.get('search', '')
        selected_professions = request.GET.getlist('profession')
        selected_skills = request.GET.getlist('skill')

        users_with_profiles = CustomUser.objects.filter(
            role='freelancer',
            freelancerprofile__professional_title__isnull=False
        ).exclude(
            freelancerprofile__professional_title__exact=''
        ).select_related('freelancerprofile', 'register')

        if search_query:
            users_with_profiles = users_with_profiles.filter(
                Q(username__icontains=search_query) |
                Q(freelancerprofile__professional_title__icontains=search_query) |
                Q(register__first_name__icontains=search_query) |
                Q(register__last_name__icontains=search_query)
            )

        if selected_professions:
            for profession in selected_professions:
                users_with_profiles = users_with_profiles.filter(
                    freelancerprofile__professional_title__icontains=profession
                )

        if selected_skills:
            for skill in selected_skills:
                users_with_profiles = users_with_profiles.filter(
                    freelancerprofile__skills__icontains=skill
                )

        registers = Register.objects.all()
        register_dict = {}
        for reg in registers:
            register_dict.setdefault(reg.user_id, []).append(reg)

        context = []
        for user in users_with_profiles:
            freelancer_profile = getattr(user, 'freelancerprofile', None)
            professions = freelancer_profile.professional_title.strip('[]').replace("'", "").split(', ') if freelancer_profile and freelancer_profile.professional_title else []
            skills = freelancer_profile.skills.strip('[]').replace("'", "").split(', ') if freelancer_profile and freelancer_profile.skills else []

            context.append({
                'user': user,
                'freelancer_profile': freelancer_profile,
                'registers': register_dict.get(user.id, []),
                'professions': [title.strip() for title in professions],
                'skills': [skill.strip() for skill in skills]
            })

        profession_choices = [
            'Web Developer', 'Front End Developer', 'Back End Developer', 'Full-Stack Developer',
            'Mobile App Developer', 'Android Developer', 'iOS Developer', 'UI/UX Designer', 'Graphic Designer',
            'Logo Designer', 'Poster Designer', 'Machine Learning Engineer', 'Artificial Intelligence Specialist', 'Software Developer'
        ]

        skill_choices = [
            "java", "c++", "python", "eclipse", "visual studio", "html","css", "javascript", "bootstrap", "sass",
            "swift", "xcode", "kotlin", "android studio", "flutter", "react native", "r", "jupyter", "pandas",
            "numpy", "tensorflow", "pytorch", "keras", "scikit-learn", "adobe xd", "sketch", "figma", "invision",
            "react", "angular", "vue.js", "webpack", "node.js", "django", "ruby on rails", "spring boot",
            "mongodb", "express.js", "php (lamp stack)", "angular (mean stack)", "adobe illustrator",
            "coreldraw", "affinity designer", "adobe photoshop", "adobe indesign", "canva", "opencv"
        ]

        template_context = {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'users': context,
            'search_query': search_query,
            'selected_professions': selected_professions,
            'selected_skills': selected_skills,
            'profession_choices': profession_choices,
            'skill_choices': skill_choices,
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return only the freelancer cards for AJAX requests
            return render(request, 'Client/ViewFreelancers.html', template_context)
        
        # Return full page for regular requests
        return render(request, 'Client/ViewFreelancers.html', template_context)
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

        
        

@login_required
@nocache
def freelancer_detail(request, fid):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        profile3 = CustomUser.objects.get(id=fid)
        profile4 = Register.objects.get(user_id=fid)
        freelancer = FreelancerProfile.objects.get(user_id=fid)
        
        skills_list = [skill.strip() for skill in freelancer.skills.strip('[]').replace("'", "").split(',')]
        
        reviews = Review.objects.filter(reviewee=profile3).order_by('-review_date')

        review_details = []
        for review in reviews:
            reviewer_profile = Register.objects.get(user_id=review.reviewer.id)
            
            if review.reviewer.clientprofile.client_type == 'Individual':
                reviewer_name = reviewer_profile.first_name + ' ' + reviewer_profile.last_name
            else:
                reviewer_name = review.reviewer.clientprofile.company_name
            
            review_details.append({
                'review': review,
                'reviewer_name': reviewer_name,
                'reviewer_image': reviewer_profile.profile_picture.url if reviewer_profile.profile_picture else None,
            })

        return render(request, 'Client/SingleFreelancer.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'client': client,
            'profile3': profile3,
            'profile4': profile4,
            'skills': skills_list,  
            "reviews": review_details,
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

         
        
                
        
@login_required
@nocache
def calendar(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    events = Event.objects.filter(user=uid)
    events_data = [
        {
            'id': event.id,  # Change this to 'id'
            'title': event.title,
            'start': event.start_time.isoformat(),
            'end': event.end_time.isoformat(),
            'description': event.description,
            'color': event.color,
        }
        for event in events
    ]

    if profile1.permission:
        return render(request, 'Client/calendar.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'events_data': events_data  
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

        

 
 
 
 
@login_required
@nocache
def add_event(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role!='client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    client=ClientProfile.objects.get(user_id=uid)
    if profile1.permission==True:
        if request.method == 'POST':
            title = request.POST.get('title')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            description = request.POST.get('description')
            color = request.POST.get('color')
            
            user=request.user
            Event.objects.create(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                color=color,
                user=user
            )
            return redirect('client:calendar')
    else:
        return render(request, 'Client/PermissionDenied.html',{'profile1': profile1,
            'profile2': profile2,
            'client': client,})   
        
@login_required
@nocache
def update_event(request):
    # Check user session and authentication
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    uid = request.session.get('uid')
    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    client = get_object_or_404(ClientProfile, user_id=uid)

    if profile1.permission:
        if request.method == 'POST':
            event_id = request.POST.get('event_id')
            if not event_id:
                # Handle missing event_id case
                return redirect('client:calendar')  # or return an error message

            event = get_object_or_404(Event, id=event_id)

            title = request.POST.get('title')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            description = request.POST.get('description')
            color = request.POST.get('color')

            # Update event details
            event.title = title
            event.start_time = start_time
            event.end_time = end_time
            event.description = description
            event.color = color
            
            event.save()

            return redirect('client:calendar')

        elif request.method == 'GET':
            event_id = request.GET.get('event_id')
            if not event_id:
                # Handle missing event_id case
                return redirect('client:calendar')  # or return an error message

            event = get_object_or_404(Event, id=event_id)

            return render(request, 'Client/edit_event.html', {
                'event': event,
                'profile1': profile1,
                'profile2': profile2,
                'client': client,
            })

    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })



@login_required
@nocache
def delete_event(request):
    if 'uid' not in request.session or not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    client = get_object_or_404(ClientProfile, user_id=uid)

    if profile1.permission:
        if request.method == 'POST':
            event_id = request.POST.get('event_id')
            if not event_id:
                return redirect('client:calendar')  
            try:
                event = Event.objects.get(id=event_id)
                event.delete()
            except Event.DoesNotExist:
                pass  
            return redirect('client:calendar')

        else:
            return redirect('client:calendar')

    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })


@login_required
@nocache
def add_new_project(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    categories = [
        "Web Development", "Front-End Development", "Back-End Development", "Full-Stack Development", "Mobile Development",
        "Android Development", "iOS Development", "UI/UX Design",
        "Graphic Design", "Logo Design", "Poster Design", "Software Development",
        "Machine Learning Engineering", "Artificial Intelligence"
    ]
    skills = [
        "Python", "JavaScript", "Java", "C++", "React", "Angular", "Vue.js",
        "Node.js", "Django", "Flask", "SQL", "MongoDB", "AWS", "Docker",
        "Git", "HTML/CSS", "TypeScript", "PHP", "Swift", "Kotlin",
        "UI Design", "UX Design", "Figma", "Adobe XD", "Photoshop",
        "Illustrator", "TensorFlow", "PyTorch", "Data Analysis"
    ]
    if profile1.permission:
        if request.method == 'POST':
            title = request.POST.get('title')
            description = request.POST.get('description')
            budget = request.POST.get('budget')
            category = request.POST.get('category')
            allow_bid = 'allow_bid' in request.POST
            end_date = request.POST.get('end_date')
            file_upload = request.FILES.get('file')
            required_skills = request.POST.getlist('required_skills')  # Get selected skills
            
            
            # Check if a project with the same title already exists for this user
            if Project.objects.filter(title=title, user=request.user).exists():
                messages.error(request, 'A project with this title already exists!')
                return render(request, 'Client/NewProject.html', {
                    'profile1': profile1, 
                    'profile2': profile2, 
                    'client': client, 
                    'categories': categories
                })
            
            project = Project(
                title=title,
                description=description,
                budget=budget,
                category=category,
                allow_bid=allow_bid,
                end_date=end_date,
                file_upload=file_upload,
                user=request.user,
                required_skills=required_skills  
                
            )
            
            project.save()
            projects = Project.objects.filter(user_id=uid)
            messages.success(request, 'New Project Added Successfully!!')
            return redirect('client:project_list')
        return render(request, 'Client/NewProject.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'categories': categories,
            'skills': skills
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

        


from django.utils.dateparse import parse_date
        
@login_required
@nocache
def edit_project(request, pid):
    if request.user.role != 'client':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    categories = [
        "Web Development", "Front-End Development", "Back-End Development", "Full-Stack Development", "Mobile Development",
        "Android Development", "iOS Development", "UI/UX Design",
        "Graphic Design", "Logo Design", "Poster Design", "Software Development",
        "Machine Learning Engineering", "Artificial Intelligence"
    ]
    skills = [
        "Python", "JavaScript", "Java", "C++", "React", "Angular", "Vue.js",
        "Node.js", "Django", "Flask", "SQL", "MongoDB", "AWS", "Docker",
        "Git", "HTML/CSS", "TypeScript", "PHP", "Swift", "Kotlin",
        "UI Design", "UX Design", "Figma", "Adobe XD", "Photoshop",
        "Illustrator", "TensorFlow", "PyTorch", "Data Analysis"
    ]

    try:
        project = Project.objects.get(id=pid, user_id=uid)
    except Project.DoesNotExist:
        return redirect('client:project_list')

    if profile1.permission:
        if request.method == 'POST':
            title = request.POST.get('title')
            description = request.POST.get('description')
            budget = request.POST.get('budget')
            category = request.POST.get('category')
            allow_bid = 'allow_bid' in request.POST
            end_date = request.POST.get('end_date')
            file_upload = request.FILES.get('file')
            required_skills = request.POST.getlist('required_skills')
            
            end_date = parse_date(end_date)
            project.title = title
            project.description = description
            project.budget = budget
            project.category = category
            project.allow_bid = allow_bid
            project.end_date = end_date
            project.file_upload = file_upload
            project.status='open'
            project.required_skills = required_skills
            project.save()
            return redirect('client:project_list')

        return render(request, 'Client/UpdateProject.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'categories': categories,
            'project': project,
            'skills': skills
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client
        })

    


@login_required
@nocache
def project_list(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        search_query = request.GET.get('search', '')
        if search_query:
            projects = Project.objects.filter(user_id=uid, title__istartswith=search_query).select_related('freelancer', 'team')
        else:
            projects = Project.objects.filter(user_id=uid).select_related('freelancer', 'team')
            
        freelancer_names = {}
        project_repos = {}
        team_details = {}  # New dictionary to hold team details

        for project in projects:
            # Handle freelancer assignment
            if project.freelancer:
                register = Register.objects.filter(user=project.freelancer).first()
                if register:
                    full_name = f"{register.first_name} {register.last_name}"
                    freelancer_names[project.id] = full_name
                else:
                    freelancer_names[project.id] = 'No name available'
            
                
            elif project.team:
                team_owner = Register.objects.get(user_id=project.team.created_by.id)  # Fetch the owner from CustomUser
                team_details[project.id] = project.team.name 
            else:
                freelancer_names[project.id] = 'No freelancer assigned'
            repository = Repository.objects.filter(project=project).first()
            project_repos[project.id] = repository.id if repository else None

        return render(request, 'Client/ProjectList.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'projects': projects,
            'freelancer_names': freelancer_names,
            'project_repos': project_repos,
            'team_details': team_details,  # Pass team details to the template
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })



from django.db.models import Avg, Q, Count
from datetime import timedelta

@login_required
@nocache
def single_project_view(request, pid):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)
    
    if profile1.permission:
        project = get_object_or_404(Project, id=pid)
        proposals = Proposal.objects.filter(project_id=project)
        
        # Get assigned freelancer details if exists
        assigned_freelancer = None
        freelancer_first_name = None
        freelancer_last_name = None
        project_manager_full_name = None
        
        if project.freelancer and isinstance(project.freelancer, CustomUser):
            try:
                assigned_freelancer = FreelancerProfile.objects.get(user=project.freelancer)
                freelancer_register = Register.objects.get(user=project.freelancer)
                freelancer_first_name = freelancer_register.first_name
                freelancer_last_name = freelancer_register.last_name
                if assigned_freelancer.skills:
                    assigned_freelancer.skills = assigned_freelancer.skills.strip('[]').replace("'", "").split(', ')
            except (FreelancerProfile.DoesNotExist, Register.DoesNotExist):
                pass
        
        # Check if the project is assigned to a team
        if project.team:
            try:
                team = project.team
                project_manager = get_object_or_404(CustomUser, id=team.created_by.id)
                project_manager_register = get_object_or_404(Register, user=project_manager)
                project_manager_full_name = f"{project_manager_register.first_name} {project_manager_register.last_name}"
            except (CustomUser.DoesNotExist, Register.DoesNotExist):
                project_manager_full_name = None
        
        # Get repository if exists
        repository = Repository.objects.filter(project=project).first()
        repository_id = repository.id if repository else None
        
        freelancer_ids = proposals.values_list('freelancer__id', flat=True)
        reg_details = Register.objects.filter(user_id__in=freelancer_ids)
        freelancer_profiles = FreelancerProfile.objects.filter(user_id__in=freelancer_ids)

        # Check for team details in proposals
        team_name = None  
        team_proposal = proposals.filter(team_id__isnull=False).first()
        if team_proposal and hasattr(team_proposal, 'team_id_id'):
            try:
                team = Team.objects.get(id=team_proposal.team_id_id)
                team_name = team.name
            except Team.DoesNotExist:
                team_name = None
        
        for profile in freelancer_profiles:
            if profile.skills:
                profile.skills = profile.skills.strip('[]').replace("'", "").split(', ')
        
        additional_files = ProposalFile.objects.filter(proposal__in=proposals)

        # Get recommended freelancers
        recommended_freelancers = get_recommended_freelancers(project)

        return render(request, 'Client/SingleProject.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'project': project,
            'proposals': proposals,
            'reg_details': reg_details,
            'freelancer_profiles': freelancer_profiles,
            'additional_files': additional_files,
            'assigned_freelancer': assigned_freelancer,
            'freelancer_first_name': freelancer_first_name,
            'freelancer_last_name': freelancer_last_name,
            'repository_id': repository_id,
            'team_name': team_name,
            'project_manager_full_name': project_manager_full_name,
            'recommended_freelancers': recommended_freelancers,
        })
    
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

def get_recommended_freelancers(project):
    """
    Get recommended freelancers based on:
    1. Similar project experience (matching category)
    2. Required skills match
    3. Ratings on similar projects
    4. Overall experience and completed projects
    """
    # Start with all freelancer profiles, ensuring valid user relationships
    base_query = FreelancerProfile.objects.filter(
        user__role='freelancer',
        user__status=CustomUser.STATUS_ACTIVE,  # Use the correct class attribute
        professional_title__isnull=False
    ).select_related(
        'user', 
        'user__register'
    ).prefetch_related(
        'user__reviews_received',  # Changed to match the related_name in Review model
        'user__freelancer_projects'  # Changed to match the related_name in Project model
    )

    # Get required skills for the project
    required_skills = []
    if project.required_skills:
        try:
            if isinstance(project.required_skills, str):
                required_skills = eval(project.required_skills)
            elif isinstance(project.required_skills, (list, tuple)):
                required_skills = project.required_skills
        except:
            required_skills = []

    scored_freelancers = []
    for freelancer_profile in base_query:
        try:
            # Ensure we have a valid user instance
            if not freelancer_profile.user or not isinstance(freelancer_profile.user, CustomUser):
                continue

            total_score = 0
            scoring_details = {}

            # 1. Similar Projects Score (0-30 points)
            similar_projects = Project.objects.filter(
                freelancer=freelancer_profile.user,
                category=project.category,
                project_status='Completed'
            ).count()
            similar_projects_score = min(similar_projects * 10, 30)
            total_score += similar_projects_score
            scoring_details['similar_projects'] = similar_projects_score

            # 2. Skills Match Score (0-30 points)
            freelancer_skills = []
            matched_skills = []  # New list for matched skills
            if freelancer_profile.skills:
                try:
                    if isinstance(freelancer_profile.skills, str):
                        freelancer_skills = [
                            skill.strip().lower() 
                            for skill in freelancer_profile.skills.strip('[]').replace("'", "").split(',')
                            if skill.strip()
                        ]
                        # Find matched skills
                        matched_skills = [
                            skill for skill in required_skills 
                            if any(skill.lower() in fs.lower() for fs in freelancer_skills)
                        ]
                except:
                    freelancer_skills = []
                    matched_skills = []

            matching_skills = len(matched_skills)
            skills_score = min((matching_skills / len(required_skills) * 30 if required_skills else 30), 30)
            total_score += skills_score
            scoring_details['skills_match'] = skills_score

            # 3. Category-specific Rating Score (0-25 points)
            category_reviews = Review.objects.filter(
                reviewee=freelancer_profile.user,
                project__category=project.category  # Only reviews from same category projects
            )
            category_rating = category_reviews.aggregate(
                Avg('overall_rating')  # Average of overall_rating field from reviews
            )['overall_rating__avg'] or 0
            rating_score = (category_rating / 5) * 25  # Convert to 25-point scale
            total_score += rating_score
            scoring_details['category_rating'] = rating_score

            # 4. Experience Score (0-15 points)
            completed_projects = Project.objects.filter(
                freelancer=freelancer_profile.user,
                project_status='Completed'
            ).count()
            experience_score = min(completed_projects * 1.5, 15)
            total_score += experience_score
            scoring_details['experience'] = experience_score

            try:
                register = Register.objects.get(user=freelancer_profile.user)
                first_name = register.first_name
                last_name = register.last_name
                profile_picture = register.profile_picture
            except Register.DoesNotExist:
                first_name = "Unknown"
                last_name = "User"
                profile_picture = None

            # Format skills for display
            display_skills = []
            if freelancer_profile.skills:
                try:
                    if isinstance(freelancer_profile.skills, str):
                        display_skills = [
                            skill.strip() 
                            for skill in freelancer_profile.skills.strip('[]').replace("'", "").split(',')
                            if skill.strip()
                        ]
                except:
                    display_skills = []

            # Format the scoring details into human-readable reasons
            recommendation_reasons = []
            
            # Similar Projects
            if similar_projects > 0:
                recommendation_reasons.append(
                    f"Has completed {similar_projects} similar {project.category} projects"
                )

            # Skills Match
            if required_skills and matching_skills > 0:
                match_percentage = (matching_skills / len(required_skills)) * 100
                recommendation_reasons.append(
                    f"Matches {match_percentage:.0f}% of required skills"
                )

            # Category Rating
            if category_rating > 0:
                recommendation_reasons.append(
                    f"Has {category_rating:.1f}/5 rating in {project.category} projects"
                )

            # Experience
            if completed_projects > 0:
                recommendation_reasons.append(
                    f"Successfully completed {completed_projects} projects overall"
                )

            scored_freelancers.append({
                'freelancer': freelancer_profile,
                'score': total_score,
                'scoring_details': scoring_details,
                'skills': display_skills,
                'matched_skills': matched_skills,  # Add matched skills to the output
                'similar_projects_count': similar_projects,
                'completed_projects': completed_projects,
                'category_rating': round(category_rating, 1),  # Rounded rating for display
                'first_name': first_name,
                'last_name': last_name,
                'profile_picture': profile_picture,
                'recommendation_reasons': recommendation_reasons  # Add the reasons
            })

        except Exception as e:
            print(f"Error processing freelancer {freelancer_profile.id}: {str(e)}")
            continue

    # Sort by total score and return top 3
    scored_freelancers.sort(key=lambda x: x['score'], reverse=True)
    return scored_freelancers[:3]




        
@login_required
@nocache
def toggle_project_status(request, pid):
    project = Project.objects.get(id=pid)
    
    if project.status == 'open':
        project.status = 'closed'
    project.save()
    return redirect('client:project_list')         
        
@login_required
@nocache
def update_proposal_status(request, pro_id):
    proposal = Proposal.objects.get(id=pro_id)
    project = proposal.project
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in ['Pending', 'Accepted', 'Rejected']:
            proposal.status = new_status
            proposal.save()

            if new_status == 'Accepted':
                # Set either freelancer or team based on proposal type
                if proposal.team_id_id:
                    project.team = Team.objects.get(id=proposal.team_id_id)  # Retrieve the Team instance
                    project.freelancer = None
                else:
                    project.freelancer = proposal.freelancer
                    project.team = None
                
                project.budget = proposal.budget
                project.project_status = 'In Progress'
                project.status = 'closed'
                project.start_date = timezone.now().date()
                
                gst_rate = 18 
                gst_amount = project.budget * gst_rate / 100
                total_including_gst = project.budget + gst_amount
                
                project.gst_amount = gst_amount
                project.total_including_gst = total_including_gst
                project.save()
                
                # Create notification for team or freelancer
                if proposal.team_id:
                    team_members = TeamMember.objects.filter(team_id=proposal.team_id)
                    if team_members.exists():  # Add check if team has members
                        for member in team_members:
                            Notification.objects.create(
                                user=member.user,
                                message=f'Congratulations! Your team\'s proposal for project "{project.title}" has been accepted.'
                            )
                    else:
                        # Log or handle case where team has no members
                        print(f"Warning: Team {proposal.team_id} has no members")
                else:
                    if proposal.freelancer:  # Add check if freelancer exists
                        Notification.objects.create(
                            user=proposal.freelancer,
                            message=f'Congratulations! Your proposal for project "{project.title}" has been accepted.'
                        )
                    else:
                        # Log or handle case where proposal has no freelancer
                        print(f"Warning: Proposal {proposal.id} has no freelancer")
                
                chatroom = ChatRoom.objects.filter(
                    participants=proposal.freelancer
                ).filter(
                    participants=project.user
                ).first()
                
                if chatroom:
                    chatroom.project = project
                    chatroom.save()
                    
                    Notification.objects.create(
                        user=proposal.freelancer,
                        message=f'You have been assigned to a new project "{project.title}" in the existing chatroom.'
                    )
                    Notification.objects.create(
                        user=project.user,
                        message=f'You have a new project "{project.title}" assigned in the existing chatroom.'
                    )
                else:
                    chatroom = ChatRoom.objects.create(
                        project=project,
                        chat_type = 'private' 
                    )
                    chatroom.participants.add(proposal.freelancer, project.user)  
                    
                    
                    Notification.objects.create(
                        user=proposal.freelancer,
                        message=f'A new chatroom has been created for project "{project.title}".'
                    )
                    Notification.objects.create(
                        user=project.user,
                        message=f'A new chatroom has been created for your project "{project.title}".'
                    )
                    
                # Handle rejection notifications
                Proposal.objects.filter(project=project).exclude(id=pro_id).update(status='Rejected')
                rejected_proposals = Proposal.objects.filter(project=project, status='Rejected')
                for other_proposal in rejected_proposals:
                    if other_proposal.team_id:
                        for member in other_proposal.team_id.members.all():
                            Notification.objects.create(
                                user=member.user,  # Access the CustomUser through TeamMember
                                message=f'Your team\'s proposal for project "{project.title}" has been rejected.'
                            )
                    else:
                        Notification.objects.create(
                            user=other_proposal.freelancer,
                            message=f'Your proposal for project "{project.title}" has been rejected.'
                        )
                
                messages.success(request, 'You have successfully selected a Freelancer/Team for this project.')
            else:
                # Handle rejection notifications
                Proposal.objects.filter(project=project).exclude(id=pro_id).update(status='Rejected')
                for other_proposal in Proposal.objects.filter(project=project, status='Rejected'):
                    if other_proposal.team_id:
                        for member in other_proposal.team_id.members.all():
                            Notification.objects.create(
                                user=member.user,  # Access the CustomUser through TeamMember
                                message=f'Your team\'s proposal for project "{project.title}" has been rejected.'
                            )
                    else:
                        Notification.objects.create(
                            user=other_proposal.freelancer,
                            message=f'Your proposal for project "{project.title}" has been rejected.'
                        )

    return redirect('client:single_project_view', pid=project.id)



@login_required
@nocache
def lock_proposal(request,prop_id):
    proposal = Proposal.objects.get(id=prop_id)
    proposal.locked = True
    proposal.save()
    return redirect('client:project_list')


     
@login_required
@nocache
def acc_deactivate(request):
    uid = request.user.id
    
    if uid is None:
        return redirect('login')
    user=CustomUser.objects.get(id=uid)
    user.status='inactive'
    user.save()
    subject = 'Account Deactivation Notice'
    
    client_profile = ClientProfile.objects.get(user_id=uid)
    if client_profile.client_type == 'Individual':
        
        register_info = Register.objects.get(user_id=uid)
        first_name = register_info.first_name
        last_name = register_info.last_name
        name = f"{first_name} {last_name}"
    else:  
        
        company_name = client_profile.company_name
        name = company_name
    context = {
        'user_name': name
    }
    html_content = render_to_string('Client/deactivation.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()
    return redirect('login')



from client.models import Repository
from django.contrib import messages

from django.http import JsonResponse

@login_required
@nocache
def create_repository(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        if request.method == 'POST':
            title = request.POST.get('repoName')
            project_id = request.POST.get('project_id')
            project = get_object_or_404(Project, id=project_id)
            # Step 1: Check if a repository with the same name exists across all projects
            if title and Repository.objects.filter(name__iexact=title).exists():
                return JsonResponse({'status': 'error', 'message': 'A repository with this name already exists.'})

            # Step 2: Check if there are any existing repositories for the specified project
            if title and Repository.objects.filter(project=project).exists():
                return JsonResponse({'status': 'error', 'message': 'A repository already exists for this project.'})

            if title:
                # Ensure to set the user field when creating the repository
                repository = Repository.objects.create(
                    name=title,
                    project=project,
                    created_by=profile1  # Set the user who created the repository
                )
                if repository:
                    if project.team:  # Check if the project has a team
                        team_members = TeamMember.objects.filter(team=project.team)  # Get all team members
                        for member in team_members:
                            Notification.objects.get_or_create(
                                user=member.user,  
                                message=f"A new repository '{title}' has been created for the project '{project.title}'.",
                                is_read=False
                            )
                    else:
                        
                        freelancer = project.freelancer 
                        Notification.objects.get_or_create(
                            user=freelancer,  
                            message=f"A new repository '{title}' has been created for the project '{project.title}'.",
                            is_read=False
                        )

                return JsonResponse({'status': 'success', 'message': 'Repository created successfully.'})
        
    return render(request, 'Client/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'client': client,
    })

@login_required
@nocache
def download_invoice(request, contract_id):
    # Fetch the contract using the contract_id
    contract = get_object_or_404(FreelanceContract, id=contract_id)
    
    project = contract.project
    payments = PaymentInstallment.objects.filter(contract_id=contract_id)
    today = date.today() 

    client_profile = ClientProfile.objects.get(user=request.user.id)
    if client_profile.client_type == 'Individual':
        register_info = Register.objects.get(user=request.user.id)
        client_name = f"{register_info.first_name} {register_info.last_name}"
    else:
        client_name = client_profile.company_name

    return render(request, 'Client/InvoiceDownload.html', {
        'project': project,
        'payments': payments,
        'today': today,
        'client_name': client_name  
    })
        
from core.models import CancellationRequest
@login_required
@nocache
def view_repository(request, repo_id):
    if 'uid' not in request.session or not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        project = get_object_or_404(Project, id=repository.project_id)
        freelancer_name = None
        freelancer_profile_picture = None

        if project.freelancer_id:
            freelancer_register = Register.objects.get(user_id=project.freelancer_id)
            freelancer_name = f"{freelancer_register.first_name} {freelancer_register.last_name}"
            freelancer_profile_picture = freelancer_register.profile_picture if freelancer_register.profile_picture else None

        shared_files = SharedFile.objects.filter(repository=repository).values(
            'file', 'uploaded_at', 'uploaded_by', 'description'
        )
        shared_urls = SharedURL.objects.filter(repository=repository).values(
            'url', 'shared_at', 'shared_by', 'description'
        )
        notes = SharedNote.objects.filter(repository=repository).order_by('added_at')
        tasks = Task.objects.filter(project=project)

        proposals = Proposal.objects.filter(project=project, status='Accepted')
        contracts = FreelanceContract.objects.filter(project=project)

        items = []
        
        for file in shared_files:
            items.append({
                'type': 'file',
                'path': file['file'],
                'date': file['uploaded_at'],
                'uploaded_by': file['uploaded_by'],
                'description': file['description']
            })
        
        for url in shared_urls:
            items.append({
                'type': 'url',
                'path': url['url'],
                'date': url['shared_at'],
                'shared_by': url['shared_by'],
                'description': url['description']
            })
        
        items.sort(key=lambda x: x['date'])

        # Fetch cancellation details related to the project
        cancellation_details = CancellationRequest.objects.filter(project=project).first()

        return render(request, 'Client/SingleRepository.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'repository': repository,
            'items': items,
            'notes': notes,
            'tasks': tasks,
            'freelancer_name': freelancer_name,
            'freelancer_profile_picture': freelancer_profile_picture,
            'proposals': proposals,
            'contracts': contracts,
            'project': project,
            'cancellation_details': cancellation_details,  # Pass cancellation details to the template
        })
        
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })







@login_required
@nocache
def add_github_link(request,repo_id):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method=='POST':
            project_id = request.POST.get('project_id')  # Get the project_id from the hidden field
            git_repo_link = request.POST.get('git_repo_link')
            
            if git_repo_link:
                project = get_object_or_404(Project, id=project_id)
                project.git_repo_link = git_repo_link
                project.save()
                messages.success(request, 'GitHub repository link updated successfully!')
            else:
                messages.error(request, 'Failed to update GitHub repository link.')

                messages.success(request, 'Files added successfully.')
            return redirect('client:view_repository', repo_id=repository.id)
        
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })       




@login_required
@nocache
def add_file(request,repo_id):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method=='POST':
            file = request.FILES['files']
            description=request.POST.get('description')
            newfile = SharedFile(
                    file=file,
                    repository=repository,
                    description=description,
                    uploaded_by=request.user)
            newfile.save()

            messages.success(request, 'Files added successfully.')
            return redirect('client:view_repository', repo_id=repository.id)
        
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })       






@login_required
@nocache
def add_url(request,repo_id):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'client':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = ClientProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method=='POST':
            url = request.POST.get('url')
            description=request.POST.get('description')
            newurl = SharedURL(
                    url=url,
                    repository=repository,
                    description=description,
                    shared_by=request.user)
            newurl.save()

            messages.success(request, 'URL added successfully.')
            return redirect('client:view_repository', repo_id=repository.id)
        
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })       






@login_required
@nocache
def add_note(request, repo_id):
    # Check if user has required permission
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    # Fetch user profiles
    profile1 = CustomUser.objects.get(id=request.user.id)
    profile2 = Register.objects.get(user_id=request.user.id)
    client = ClientProfile.objects.get(user_id=request.user.id)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method == 'POST':
            note_content = request.POST.get('content')
            print(f"Note Content: {note_content}")  
            if note_content:
                new_note=SharedNote(
                    repository=repository,  
                    note=note_content,
                    added_by=request.user
                )
                new_note.save()
                messages.success(request, 'Note added successfully.')
                return redirect('client:view_repository', repo_id=repository.id)
            else:
                messages.error(request, 'Note content cannot be empty.')
        
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

    return redirect('client:view_repository', repo_id=repo_id) 




@login_required
@nocache
def add_task(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = CustomUser.objects.get(id=request.user.id)
    profile2 = Register.objects.get(user_id=request.user.id)
    client = ClientProfile.objects.get(user_id=request.user.id)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        project = repository.project
        if request.method == "POST":
            title = request.POST.get('title')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            due_date = request.POST.get('due_date')

            if project.freelancer:
                assigned_freelancer = project.freelancer
                # Create the task and assign it to the freelancer
                task = Task.objects.create(
                    project=project,
                    title=title,
                    description=description,
                    start_date=start_date,
                    due_date=due_date,
                    assigned_to=assigned_freelancer  # Assuming 'assigned_to' is a field in Task model
                )
            else:
                task = Task.objects.create(
                    project=project,
                    title=title,
                    description=description,
                    start_date=start_date,
                    due_date=due_date,
                )

            task.save()

            # Update project status to 'In Progress' when a task is added
            project.project_status = 'In Progress'
            project.save()

    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

    return redirect('client:view_repository', repo_id=repo_id)



@login_required
@nocache
def update_task_progress(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = CustomUser.objects.get(id=request.user.id)
    profile2 = Register.objects.get(user_id=request.user.id)
    client = ClientProfile.objects.get(user_id=request.user.id)
    
    if profile1.permission:
        if request.method == "POST":
            progress_percentage = request.POST.get('progress_percentage')
            task_id = request.POST.get('task_id')
            
            try:
                progress = int(progress_percentage)
                task = Task.objects.get(id=task_id)
                
                # Update progress and automatically set status based on progress
                task.progress_percentage = progress
                task.status = 'Completed' if progress == 100 else 'In Progress'
                task.save()
                
                return redirect('client:view_repository', repo_id=repo_id)
                
            except (ValueError, Task.DoesNotExist):
                messages.error(request, 'Invalid progress value or task not found')
                
    return render(request, 'Client/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'client': client,
    })









@login_required
@nocache
def update_task_status(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = CustomUser.objects.get(id=request.user.id)
    profile2 = Register.objects.get(user_id=request.user.id)
    client = ClientProfile.objects.get(user_id=request.user.id)
    
    if profile1.permission:
        if request.method == "POST":
            task_id = request.POST.get('task_id')
            new_status = request.POST.get('status')
            
            try:
                task = Task.objects.get(id=task_id)
                task.status = new_status
                
                # Automatically update progress when status changes
                if new_status == 'Completed':
                    task.progress_percentage = 100
                elif new_status == 'In Progress' and task.progress_percentage == 100:
                    # If moving back to "In Progress", reset progress to 99%
                    task.progress_percentage = 99
                    
                task.save()
                return redirect('client:view_repository', repo_id=repo_id)
                
            except Task.DoesNotExist:
                messages.error(request, 'Task not found')

    return render(request, 'Client/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'client': client,
    })






@login_required
@nocache
def edit_task(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = CustomUser.objects.get(id=request.user.id)
    profile2 = Register.objects.get(user_id=request.user.id)
    client = ClientProfile.objects.get(user_id=request.user.id)
    
    if profile1.permission:
        if request.method == "POST":
            task_id = request.POST.get('task_id')
            title = request.POST.get('title')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            due_date = request.POST.get('due_date')

            task = get_object_or_404(Task, id=task_id)

            task.title = title
            task.description = description
            task.start_date = start_date
            task.due_date = due_date

            task.save()

            return redirect('client:view_repository', repo_id=repo_id) 

    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

    return redirect('client:view_repository', repo_id=repo_id)



@login_required
@nocache
def submit_contract(request, pro_id):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)
    
    if profile1.permission:
        project = Project.objects.get(id=pro_id) 
        if project.team:  
            team = project.team 
            team_data = Team.objects.get(id=team.id)  # Ensure to use team.id
            user = CustomUser.objects.get(id=team_data.created_by.id)
            freelancer = user.id
            proposal = Proposal.objects.get(project=project, team_id=freelancer)  # Ensure to use freelancer ID
        else:
            freelancer = project.freelancer 
            proposal = Proposal.objects.get(project=project, freelancer=project.freelancer)
        freelancer_data = Register.objects.get(user_id=freelancer)
        freelancer_name = f"{freelancer_data.first_name} {freelancer_data.last_name}"
        
        existing_contract = FreelanceContract.objects.filter(client=profile1, project=project).first()

        if request.method == 'POST' and not existing_contract:
            client_instance = CustomUser.objects.get(id=request.POST.get('client_id'))
            freelancer_instance = CustomUser.objects.get(id=request.POST.get('freelancer_id'))
            signature = request.FILES.get('client_signature')
            project_instance = Project.objects.get(id=request.POST.get('project_id'))

            # Ensure that the instances are not None
            if client_instance and freelancer_instance and project_instance:
                contract = FreelanceContract(
                    client=client_instance,
                    freelancer=freelancer_instance,
                    project=project_instance,
                    client_signature=signature
                )
                contract.save()

                amounts = request.POST.getlist('installment_amount[]')
                due_dates = request.POST.getlist('installment_due_date[]')

                for amount, due_date in zip(amounts, due_dates):
                    PaymentInstallment.objects.create(contract=contract, amount=amount, due_date=due_date)

                Notification.objects.create(
                    user=freelancer_instance,
                    message=f'You have received a new agreement for the project "{project.title}" from the client.'
                )
                return redirect('client:project_list')
            else:
                # Handle the case where one of the instances is None
                messages.error(request, 'Invalid data provided. Please check your inputs.')
                return redirect('client:some_view')  # Redirect to an appropriate view

        payment_installments = PaymentInstallment.objects.filter(contract=existing_contract) if existing_contract else None
        
        return render(request, 'Client/Agreement_template.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'project': project,
            'freelancer_name': freelancer_name,
            'proposal': proposal,
            'freelancer': freelancer_data,
            'existing_contract': existing_contract,  # Pass existing contract to the template
            'payment_installments': payment_installments, 
            'team_name':team_data.name # Pass payment installments to the template
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })



@login_required
def submit_review(request):
    if request.method == 'POST':
        quality_of_work = float(request.POST.get('quality_of_work'))
        communication = float(request.POST.get('communication'))
        adherence_to_deadlines = float(request.POST.get('adherence_to_deadlines'))
        professionalism = float(request.POST.get('professionalism'))
        problem_solving_ability = float(request.POST.get('problem_solving_ability'))
        review_text = request.POST.get('review')
        reviewer_id = request.user.id
        reviewee_id = int(request.POST.get('freelancer_id'))
        project_id = int(request.POST.get('project_id'))

        overall_rating = (quality_of_work + communication + adherence_to_deadlines + professionalism + problem_solving_ability) / 5

        review = Review(
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            project_id=project_id,
            quality_of_work=quality_of_work,
            communication=communication,
            adherence_to_deadlines=adherence_to_deadlines,
            professionalism=professionalism,
            problem_solving_ability=problem_solving_ability,
            overall_rating=overall_rating,
            review_text=review_text
        )
        review.save()
        project = Project.objects.get(id=project_id)
        if project.user.id == reviewer_id:
            project.client_review_given = True
            project.save()
        return redirect('client:client_view')



@login_required
@nocache
def chat_view(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)
    
    if profile1.permission:
        # Fetch all chat rooms related to the client
        chat_rooms = ChatRoom.objects.filter(participants=client.user_id).prefetch_related('participants')

        # Fetch freelancer details for each chat room
        chat_details = []
        for chat in chat_rooms:
            if chat.chat_type == 'group':
                # For group chats, add group details
                members = []
                for participant in chat.participants.all():
                    try:
                        register = Register.objects.get(user_id=participant.id)
                        members.append({
                            'name': f"{register.first_name} {register.last_name}",
                            'profile_picture': register.profile_picture.url if register.profile_picture else None
                        })
                    except Register.DoesNotExist:
                        continue
                
                chat_details.append({
                    'chat_room_id': chat.id,
                    'chat_type': 'group',
                    'name': chat.name,
                    'members': members
                })
            else:
                # For private chats, fetch freelancer details
                for participant in chat.participants.exclude(id=client.user_id):
                    try:
                        freelancer_profile = FreelancerProfile.objects.get(user=participant)
                        freelancer_register = Register.objects.get(user_id=participant.id)
                        chat_details.append({
                            'chat_room_id': chat.id,
                            'chat_type': 'private',
                            'user': participant,
                            'profile': freelancer_profile,
                            'register': freelancer_register
                        })
                    except (FreelancerProfile.DoesNotExist, Register.DoesNotExist):
                        continue
        
        return render(request, 'Client/chat.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'chat_rooms': chat_rooms,
            'chat_details': chat_details,  # Replace freelancers with chat_details
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })
        
        
        
@login_required
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            chat_room_id = data.get('chat_room_id')
            content = data.get('content')

            # Validate inputs
            if not chat_room_id or not content:
                return JsonResponse({'success': False, 'error': 'Missing chat_room_id or content'}, status=400)

            # Fetch the chat room
            try:
                chat_room = ChatRoom.objects.get(id=chat_room_id)
            except ChatRoom.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Chat room does not exist'}, status=404)

            # Create and save the message
            message = Message.objects.create(
                chat_room=chat_room,
                content=content,
                sender=request.user
            )

            return JsonResponse({'success': True, 'message': message.content, 'sender': message.sender.username, 'timestamp': message.timestamp.isoformat()}, status=200)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


@csrf_exempt
def fetch_messages(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        chat_room_id = data.get('chat_room_id')
        chat_room = ChatRoom.objects.get(id=chat_room_id)
        messages = Message.objects.filter(chat_room_id=chat_room_id).order_by('timestamp')

        messages_list = []
        for message in messages:
            # Get sender's Register information
            try:
                sender_register = Register.objects.get(user_id=message.sender.id)
                sender_name = f"{sender_register.first_name} {sender_register.last_name}"
                sender_profile_picture = sender_register.profile_picture.url if sender_register.profile_picture else None
            except Register.DoesNotExist:
                sender_name = message.sender.username
                sender_profile_picture = None

            message_data = {
                'content': message.content if message.content else '',
                'type': 'sent' if message.sender == request.user else 'received',
                'image': message.image.url if message.image else None,
                'file': message.file.url if message.file else None,
                'is_group_chat': chat_room.chat_type == 'group',
                'sender_name': sender_name,
                'sender_profile_picture': sender_profile_picture,
                'timestamp': message.timestamp.strftime("%I:%M %p")  # Adding time in 12-hour format
            }
            messages_list.append(message_data)

        return JsonResponse({
            'success': True,
            'messages': messages_list
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})




from django.core.files.storage import default_storage
from .models import Message  # Import your Message model

@csrf_exempt
def send_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        chat_room_id = request.POST.get('chat_room_id')
        uploaded_file = request.FILES['file']
        
        # Determine the type of file and save accordingly
        try:
            if uploaded_file.content_type.startswith('image/'):
                # Save as an image
                message = Message(
                    image=uploaded_file,
                    sender=request.user,
                    chat_room_id=chat_room_id
                )
            else:
                # Save as a regular file
                message = Message(
                    file=uploaded_file,
                    sender=request.user,
                    chat_room_id=chat_room_id
                )

            message.save()  # Save the message with the file

            return JsonResponse({'success': True, 'message': 'File uploaded successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'File saving error: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request.'})




@login_required
@nocache
def add_complaint(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)
    
    if profile1.permission:
        projects = Project.objects.filter(user=profile1)
        freelancer_ids = projects.values_list('freelancer', flat=True).distinct()
        freelancers = CustomUser.objects.filter(id__in=freelancer_ids)
        freelancer_registers = Register.objects.filter(user__in=freelancers)
        if request.method == 'POST':
            complaint_type = request.POST.get('complaint_type')
            subject = request.POST.get('subject')
            complainee_id = request.POST.get('complainee')  # This may be empty if not applicable
            description = request.POST.get('description')

            # Validate fields
            if not complaint_type or not subject or not description:
                messages.error(request, 'Please fill out all required fields.')
            else:
                complaint = Complaint(
                    user=profile1,
                    complaint_type=complaint_type,
                    subject=subject,
                    description=description
                )
                
                # Set the complainee if complaint is about freelancer or client
                if complaint_type in ['Freelancer', 'Client']:
                    complainee = CustomUser.objects.filter(id=complainee_id).first()
                    if complainee:
                        complaint.complainee = complainee
                    else:
                        messages.error(request, 'Invalid complainee ID.')
                
                complaint.save()

                # Notify admin if the complaint is about a site issue
                if complaint_type == 'Site Issue':
                    admin_user = CustomUser.objects.get(id=1)  # Assuming user ID 1 is the admin
                    Notification.objects.create(
                        user=admin_user,
                        message=f'New site issue complaint from {profile1.username}: {subject}'
                    )
                else:
                    # Notify the accused if it's about a freelancer or client
                    if complaint_type in ['Freelancer', 'Client']:
                        complainee = CustomUser.objects.filter(id=complainee_id).first()
                        if complainee:
                            Notification.objects.create(
                                user=complainee,
                                message=f'You have received a complaint: {subject}'
                            )

                messages.success(request, 'Complaint submitted successfully.')
                return redirect('client:client_view') 
        return render(request, 'Client/AddComplaint.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'freelancer_registers': freelancer_registers,
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })
        
        
        
@login_required
def view_complaints(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)
    
    if profile1.permission:
        complaints = Complaint.objects.filter(user=profile1)
        return render(request, 'Client/Complaints.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'complaints': complaints,
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })
        
        
def view_complaints_recieved(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)
    
    if profile1.permission:
        complaints = Complaint.objects.filter(complainee=profile1)
        return render(request, 'Client/RecievedComplaints.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'complaints': complaints,
        })
    else:
        return render(request, 'Client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })
        
        
        

def update_solution(request):
    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        solution = request.POST.get('solution')
        
        # Update the complaint's solution
        complaint = Complaint.objects.get(id=complaint_id)
        complaint.resolution = solution
        complaint.save()
        
        # Notify the user about the solution
        Notification.objects.create(
            user=complaint.user,  # Notify the user who made the complaint
            message=f'A solution has been provided for your complaint: "{complaint.subject}".'
        )
        
        return redirect("client:view_complaints_recieved")
    return redirect("client:view_complaints_recieved")


def update_complaint_status(request):
    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        satisfaction_status = request.POST.get('satisfaction_status')

        # Update the complaint status in the database
        try:
            complaint = Complaint.objects.get(id=complaint_id)
            # Update the status based on satisfaction
            if satisfaction_status == 'Satisfactory':
                complaint.resolution_status = "Satisfactory"
                complaint.status = 'Resolved'  # Adjust field name and value as necessary
                # Notify the accused about the positive resolution
                Notification.objects.create(
                    user=complaint.complainee,
                    message=f'Your complaint has been resolved: "{complaint.subject}".'
                )
            elif satisfaction_status == 'Unsatisfactory':
                complaint.resolution_status = "Unsatisfactory"
                complaint.status = 'Pending'  # Adjust field name and value as necessary
                # Notify the accused about the negative resolution
                Notification.objects.create(
                    user=complaint.complainee,
                    message=f'Your solution is marked as unsatisfactory: "{complaint.subject}".'
                )
            complaint.satisfaction_status = satisfaction_status  # Store satisfaction status
            complaint.save()
            return JsonResponse({'success': True})
        except Complaint.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Complaint not found.'})

    return JsonResponse({'success': False, 'error': 'Invalid request.'})


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from client.models import FreelanceContract, PaymentInstallment, Project
from core.models import Register
from core.models import RefundPayment

@login_required
def payments(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    user_id = request.user.id
    contracts = FreelanceContract.objects.filter(client=user_id).select_related('project')
    payments_details = {}

    for contract in contracts:
        project_payments = PaymentInstallment.objects.filter(contract=contract)
        refund_payments = RefundPayment.objects.filter(project=contract.project)
        
        project_id = contract.project.id
        contract_id = contract.id

        if project_id not in payments_details:
            project_title = contract.project.title
            total_amount = contract.project.total_including_gst
            team_name = None
            project_manager_full_name = None
            freelancer_first_name = None
            freelancer_last_name = None

            if contract.project.team:  # If project has a team
                team = contract.project.team
                team_name = team.name  # Assuming team has a name field
                project_manager = CustomUser.objects.get(id=team.created_by.id)  # Get the project manager
                project_manager_full_name = project_manager.username if project_manager else "Unknown"
            
            elif contract.project.freelancer:  # If project has a freelancer
                freelancer_register = Register.objects.filter(user=contract.project.freelancer).first()
                if freelancer_register:
                    freelancer_first_name = freelancer_register.first_name
                    freelancer_last_name = freelancer_register.last_name
                else:
                    freelancer_first_name = "Unknown"
                    freelancer_last_name = ""

            payments_details[project_id] = {
                'project_title': project_title,
                'total_amount': total_amount,
                'contract_id': contract_id,
                'team_name': team_name,
                'project_manager_full_name': project_manager_full_name,
                'freelancer_first_name': freelancer_first_name,
                'freelancer_last_name': freelancer_last_name,
                'payments': [],
                'refunds': []
            }

        # Add regular payments
        for payment in project_payments:
            payments_details[project_id]['payments'].append({
                'amount': payment.amount,
                'due_date': payment.due_date,
                'status': payment.status,
                'paid_at': payment.paid_at
            })

        # Add refund payments
        for refund in refund_payments:
            payments_details[project_id]['refunds'].append({
                'amount': refund.amount,
                'reason': refund.reason,
                'status': refund.status,
                'created_at': refund.created_at,
                'processed_at': refund.processed_at
            })

    payments_details_list = list(payments_details.values())

    return render(request, 'Client/payments.html', {
        'payments_details': payments_details_list,
    })

    
    

import pdfkit  

from datetime import date

def view_invoice(request, contract_id):
    contract = get_object_or_404(FreelanceContract, id=contract_id)
    project = contract.project
    payments = PaymentInstallment.objects.filter(contract_id=contract_id)
    today = date.today()  # Get today's date
    return render(request, 'Client/PaymentInvoice.html', {
        'project': project,
        'payments': payments,
        'today': today  # Pass today's date to the template
    })



from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.shortcuts import get_object_or_404
from client.models import FreelanceContract, PaymentInstallment
from datetime import date

@login_required
@nocache
def download_invoice(request, contract_id):
    # Fetch the contract using the contract_id
    contract = get_object_or_404(FreelanceContract, id=contract_id)
    
    project = contract.project
    payments = PaymentInstallment.objects.filter(contract_id=contract_id)
    today = date.today()  # Get today's date

    client_profile = ClientProfile.objects.get(user=request.user.id)
    if client_profile.client_type == 'Individual':
        register_info = Register.objects.get(user=request.user.id)
        client_name = f"{register_info.first_name} {register_info.last_name}"
    else:
        client_name = client_profile.company_name

    return render(request, 'Client/InvoiceDownload.html', {
        'project': project,
        'payments': payments,
        'today': today,
        'client_name': client_name  
    })

@csrf_exempt  # Use with caution; consider using CSRF tokens
def hire_freelancer(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        job_role = request.POST.get('job_role')
        job_description = request.POST.get('job_description')
        compensation = request.POST.get('compensation')
        bond_period = request.POST.get('bond_period')
        contract_needed = request.POST.get('contract_needed').lower() == 'true'
        work_mode = request.POST.get('work_mode')
        benefits = request.POST.get('benefits')

        # Get the freelancer's user object
        freelancer = CustomUser.objects.get(id=user_id)

        # Check for existing invitation with same job role
        existing_invitation = JobInvitation.objects.filter(
            freelancer=freelancer,
            client=request.user,
            job_role=job_role
        ).exists()

        if existing_invitation:
            return JsonResponse({
                'success': False, 
                'error': 'You have already sent an invitation to this freelancer for this job role.'
            })

        # Get the current user's profile to determine the client name
        current_user = request.user
        client_name = ""
        client_email = current_user.email  # Assuming the email is from the current user

        # Check if the current user is a company or an individual
        try:
            client_profile = ClientProfile.objects.get(user=current_user)
            if client_profile.company_name:  # If company name exists
                client_name = client_profile.company_name
            else:
                # If no company name, get first and last name from Register table
                register = Register.objects.get(user=current_user)
                client_name = f"{register.first_name} {register.last_name}"
        except ClientProfile.DoesNotExist:
            # Handle case where ClientProfile does not exist
            register = Register.objects.get(user=current_user)
            client_name = f"{register.first_name} {register.last_name}"

        # Create a JobInvitation instance
        invitation = JobInvitation.objects.create(
            freelancer=freelancer,
            job_role=job_role,
            job_description=job_description,
            compensation=compensation,
            client=request.user,
            bond_period=bond_period,
            contract_needed=contract_needed,
            work_mode=work_mode,
            benefits=benefits
        )

        # Get freelancer's name for personalization
        freelancer_register = Register.objects.get(user=freelancer)
        freelancer_name = f"{freelancer_register.first_name} {freelancer_register.last_name}"

        # Get client's profile picture
        client_profile_picture = None
        try:
            register = Register.objects.get(user=current_user)
            if register.profile_picture:
                client_profile_picture = request.build_absolute_uri(register.profile_picture.url)
        except Register.DoesNotExist:
            pass

        context = {
            'freelancer_name': freelancer_name,
            'client_name': client_name,
            'client_email': client_email,
            'client_profile_picture': client_profile_picture,
            'job_role': job_role,
            'job_description': job_description,
            'compensation': compensation,
            'bond_period': bond_period,
            'contract_needed': contract_needed,
            'work_mode': work_mode,
            'benefits': benefits,
            'accept_link': f"{settings.BASE_URL}/client/accept_interview/{invitation.id}/",
            'reject_link': f"{settings.BASE_URL}/client/reject_interview/{invitation.id}/"
        }

        # Render email template
        html_content = render_to_string('Client/email/job_invitation.html', context)
        text_content = strip_tags(html_content)

        # Create email subject
        subject = f"Interview Invitation: {job_role} Position at {client_name}"

        # Create and send email
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [freelancer.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

def accept_interview(request, invitation_id):
    try:
        invitation = JobInvitation.objects.get(id=invitation_id)
        invitation.status = 'Accepted'  # Set is_accepted to True
        invitation.save()

        # Send follow-up email with meeting details (you can customize this)
        subject = f"Interview Confirmation for {invitation.job_role}"
        message = (
            f"Your interview for the role of {invitation.job_role} has been confirmed.\n"
            "The meeting link and schedule will be shared later.\n"  # Updated message
            "Instructions: Please join the meeting at the scheduled time."
        )
        
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invitation.freelancer.email])

        return HttpResponse("Interview accepted and confirmation email sent.")
    except JobInvitation.DoesNotExist:
        return HttpResponse("Invitation not found.", status=404)

def reject_interview(request, invitation_id):
    try:
        invitation = JobInvitation.objects.get(id=invitation_id)
        invitation.status = 'Rejected'  # Set is_accepted to False
        invitation.save()  # Save the updated status

        # Send rejection email to the client (optional)
        subject = f"Interview Invitation Rejected for {invitation.job_role}"
        message = f"The invitation for {invitation.job_role} has been rejected by {invitation.freelancer.username}."
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invitation.freelancer.email])

        return HttpResponse("Interview invitation rejected.")
    except JobInvitation.DoesNotExist:
        return HttpResponse("Invitation not found.", status=404)

@login_required
@nocache
def track_hiring(request):
    if not request.user.is_authenticated or request.user.role != 'client':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    client = get_object_or_404(ClientProfile, user_id=request.user.id)

    # Fetching job invitations related to the current client
    invitations = JobInvitation.objects.filter(client=request.user)

    # Fetch freelancer details for each invitation
    for invitation in invitations:
        freelancer_register = Register.objects.filter(user=invitation.freelancer).first()
        if freelancer_register:
            invitation.freelancer_first_name = freelancer_register.first_name
            invitation.freelancer_last_name = freelancer_register.last_name
            invitation.freelancer_profile_picture = freelancer_register.profile_picture.url if freelancer_register.profile_picture else None

    # Ensure invitations are being passed to the template
    return render(request, 'Client/TrackHiring.html', {
        'profile1': profile1,
        'profile2': profile2,
        'client': client,
        'invitation_details': invitations,  # Ensure this variable is populated
    })
    

@csrf_exempt  # Use this only for testing; consider using CSRF protection in production
def submit_meeting(request):
    if request.method == 'POST':
        invitation_id = request.POST.get('invitationId')
        meeting_link = request.POST.get('link')
        meeting_date = request.POST.get('date')

        # Update the JobInvitation record
        invitation = JobInvitation.objects.get(id=invitation_id)
        invitation.meeting_link = meeting_link  # Assuming you have a field for this
        invitation.meeting_datetime = meeting_date  # Assuming you have a field for this
        invitation.save()

        # Fetch freelancer details
        freelancer = invitation.freelancer
        freelancer_register = Register.objects.get(user=freelancer)

        # Prepare email details
        subject = f"Meeting Scheduled for {invitation.job_role}"
        message = (
            f"Dear {freelancer_register.first_name} {freelancer_register.last_name},\n\n"
            f"A meeting has been scheduled for the interview section for the role of {invitation.job_role}.\n"
            f"Meeting Link: {meeting_link}\n"
            f"Meeting Date: {meeting_date}\n\n"
            "Please join the meeting at the scheduled time.\n\n"
            "Best regards,\n"
            
        )

        # Send email to the freelancer
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [freelancer.email])

        return JsonResponse({'status': 'success', 'message': 'Meeting scheduled successfully and email sent.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt  
def toggle_hiring_status(request):
    if request.method == 'POST':
        invitation_id = request.POST.get('invitationId')
        new_status = request.POST.get('status')

        try:
            invitation = JobInvitation.objects.get(id=invitation_id)
            invitation.hiring_status = new_status
            invitation.save()

            freelancer = invitation.freelancer
            freelancer_register = Register.objects.get(user=freelancer)

            if new_status == 'hired':
                subject = f"Congratulations! You've been hired for {invitation.job_role}"
                message = (
                    f"Dear {freelancer_register.first_name},\n\n"
                    f"Congratulations! You have been hired for the role of {invitation.job_role}.\n"
                    "We look forward to working with you.\n\n"
                    "Thank you for your interest and effort in applying.\n"
                    
                )
            elif new_status == 'not hired':
                subject = f"Update on Your Application for {invitation.job_role}"
                message = (
                    f"Dear {freelancer_register.first_name},\n\n"
                    f"Thank you for your interest in the role of {invitation.job_role}. Unfortunately, you have not been selected for this position.\n"
                    "We appreciate your time and effort in applying.\n\n"
                    "Thank you for your understanding.\n"
                    
                )

            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [freelancer.email])

            return JsonResponse({'success': True})
        except JobInvitation.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invitation not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def manage_event_quizzes(request):
    # Fetch events and quizzes created by the current user
    events_and_quizzes = EventAndQuiz.objects.filter(client=request.user).order_by('-date')
    
    # Get counts for different types
    total_events = events_and_quizzes.filter(type='event').count()
    total_quizzes = events_and_quizzes.filter(type='quiz').count()
    
    # Get upcoming and past events/quizzes
    today = timezone.now().date()
    upcoming = events_and_quizzes.filter(date__gte=today)
    past = events_and_quizzes.filter(date__lt=today)
    
    context = {
        'events_and_quizzes': events_and_quizzes,
        'total_events': total_events,
        'total_quizzes': total_quizzes,
        'upcoming': upcoming,
        'past': past,
    }
    
    return render(request, 'Client/manage_event_quizzes.html', context)

import pandas as pd
import io
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from .models import EventAndQuiz, QuizQuestion

from datetime import timedelta
from django.utils.dateparse import parse_duration

@login_required
def create_event(request):
    if request.method == 'POST':
        try:
            # Log all POST data for debugging
            print("POST data received:")
            for key, value in request.POST.items():
                print(f"{key}: {value}")
            
            print("\nFILES received:")
            for key, value in request.FILES.items():
                print(f"{key}: {value}")

            # Extract data from form with validation logging
            try:
                title = request.POST.get('title')
                if not title:
                    raise ValueError("Title is required")
                
                date = request.POST.get('date')
                if not date:
                    raise ValueError("Date is required")
                print(f"Date received: {date}")
                
                event_type = request.POST.get('type')
                if not event_type:
                    raise ValueError("Event type is required")
                print(f"Event type: {event_type}")
                
                description = request.POST.get('description')
                max_participants = request.POST.get('max_participants')
                
                # Convert max_participants with error checking
                try:
                    max_participants = int(max_participants) if max_participants else None
                except ValueError as e:
                    print(f"Error converting max_participants: {e}")
                    max_participants = None
                
                # Boolean fields
                certificate_provided = request.POST.get('certificate_provided', 'off') == 'on'
                prize_enabled = request.POST.get('prize_enabled', 'off') == 'on'
                print(f"Certificate provided: {certificate_provided}")
                print(f"Prize enabled: {prize_enabled}")
                
                # Conditional fields
                prize_amount = request.POST.get('prize_amount') if prize_enabled else None
                type_of_event = request.POST.get('type_of_event') if event_type == 'event' else None
                online_link = request.POST.get('online_link') if event_type == 'event' else None

                # Handle duration field
                duration_str = request.POST.get('duration')
                duration = None
                if duration_str:
                    try:
                        # If duration is in minutes (e.g., "60")
                        minutes = int(duration_str)
                        duration = timedelta(minutes=minutes)
                    except ValueError:
                        try:
                            # If duration is in HH:MM:SS format
                            duration = parse_duration(duration_str)
                        except ValueError:
                            print(f"Invalid duration format: {duration_str}")
                            messages.error(request, 'Invalid duration format. Please use minutes (e.g., 60) or HH:MM:SS format.')
                            return redirect('client:manage_event_quizzes')
                
                # File handling with validation
                poster = request.FILES.get('poster')
                if poster:
                    print(f"Poster file received: {poster.name}, size: {poster.size}")
                
                quiz_file = request.FILES.get('quiz_file')
                if quiz_file:
                    print(f"Quiz file received: {quiz_file.name}, size: {quiz_file.size}")
                
                registration_end_date = request.POST.get('registration_end_date')
                print(f"Registration end date: {registration_end_date}")

                # Print all data before creating event
                print("\nAttempting to create event with data:")
                event_data = {
                    'title': title,
                    'date': date,
                    'type': event_type,
                    'type_of_event': type_of_event,
                    'description': description,
                    'max_participants': max_participants,
                    'online_link': online_link,
                    'certificate_provided': certificate_provided,
                    'prize_enabled': prize_enabled,
                    'prize_amount': prize_amount,
                    'poster': poster,
                    'client': request.user,
                    'quiz_file': quiz_file,
                    'registration_end_date': registration_end_date,
                    'duration': duration,
                }
                for key, value in event_data.items():
                    print(f"{key}: {value}")

                # Create the event
                event = EventAndQuiz.objects.create(**event_data)
                print(f"Event created successfully with ID: {event.id}")

                # Process quiz file if present
                if quiz_file and event_type == 'quiz':
                    print("\nProcessing quiz file...")
                    try:
                        quiz_file.seek(0)
                        quiz_data = io.StringIO(quiz_file.read().decode('utf-8'))
                        df = pd.read_csv(quiz_data)
                        print(f"CSV data loaded, {len(df)} questions found")

                        if df.empty:
                            raise ValueError('CSV file is empty')

                        required_columns = {'Question', 'Option 1', 'Option 2', 'Option 3', 'Option 4', 'Correct Answer', 'Points'}
                        missing_columns = required_columns - set(df.columns)
                        if missing_columns:
                            raise ValueError(f'Missing required columns: {missing_columns}')

                        # Save quiz questions
                        for index, row in df.iterrows():
                            print(f"Processing question {index + 1}")
                            QuizQuestion.objects.create(
                                quiz=event,
                                question=row['Question'],
                                option1=row['Option 1'],
                                option2=row['Option 2'],
                                option3=row['Option 3'],
                                option4=row['Option 4'],
                                correct_answer=row['Correct Answer'],
                                points=int(row['Points'])
                            )

                    except Exception as e:
                        print(f"Error processing quiz file: {str(e)}")
                        event.delete()
                        raise

                messages.success(request, 'Event created successfully!')
                return redirect('client:manage_event_quizzes')

            except ValueError as e:
                print(f"Validation error: {str(e)}")
                messages.error(request, f'Validation error: {str(e)}')
                return redirect('client:manage_event_quizzes')

        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            messages.error(request, f'Error creating event: {str(e)}')
            return redirect('client:manage_event_quizzes')

    else:
        print("Non-POST request received")
    
    return redirect('client:manage_event_quizzes')





from django.http import JsonResponse

def get_event_details(request, event_id):
    try:
        event = EventAndQuiz.objects.get(id=event_id)
        data = {
            'title': event.title,
            'type': event.type,
            'date': event.date.isoformat(),
            'max_participants': event.max_participants,
            'description': event.description,
            'online_link': event.online_link,
            'prize_enabled': event.prize_enabled,
            'prize_amount': event.prize_amount,
            'certificate_provided': event.certificate_provided,
            'poster': event.poster.url,
            'type_of_event': event.type_of_event,
            'online_link': event.online_link,  # Added this field to display the online link if applicable
        }
        return JsonResponse(data)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)

from django.shortcuts import get_object_or_404, redirect
from .models import EventAndQuiz  # Adjust the import based on your model's location

def remove_event(request, event_id):  # Renamed function
    event = get_object_or_404(EventAndQuiz, id=event_id)  # Use EventAndQuiz model
    event.delete()
    return redirect('client:manage_event_quizzes')  # Redirect to the appropriate page after deletion

from .models import EventRegistration,QuizAttempt
@login_required
@nocache
def manage_single_event(request, event_id):
    event = EventAndQuiz.objects.get(id=event_id)
    registrations = EventRegistration.objects.filter(event=event)
    leaderboard_data = []
    prize_paid = False

    # Fetch all registered participants
    registered_participants = []
    for registration in registrations:
        freelancer = registration.freelancer
        register_info = Register.objects.get(user=freelancer)
        registered_participants.append({
            'name': f"{register_info.first_name} {register_info.last_name}",
            'email': freelancer.email,
            'profile_picture': register_info.profile_picture.url if register_info.profile_picture else None,
            'registered_at': registration.registration_time,
            'attended': registration.attended,  # Include attendance status
            'registration_id': registration.id  # Include registration ID for potential actions
        })

    # Fetch freelancers who attended the event
    attended_freelancers = []
    for registration in registrations:
        if registration.attended:  # Check if the freelancer attended
            freelancer = registration.freelancer
            register_info = Register.objects.get(user=freelancer)
            attended_freelancers.append({
                'name': f"{register_info.first_name} {register_info.last_name}",
                'email': freelancer.email,
                'profile_picture': register_info.profile_picture.url if register_info.profile_picture else None,
                'registered_at': registration.registration_time,
            })

    # Existing logic for quizzes
    if event.type == 'quiz':
        # Get all questions and their points for this quiz
        quiz_questions = QuizQuestion.objects.filter(quiz=event)
        total_possible_points = sum(question.points for question in quiz_questions)
        
        quiz_attempts = QuizAttempt.objects.filter(
            quiz=event
        ).order_by('-score')
        
        # Check if prize payment exists for the winner (first place)
        prize_paid = False
        if event.prize_enabled and quiz_attempts.exists():
            winner = quiz_attempts.first().freelancer
            prize_paid = PrizePayment.objects.filter(
                event=event,
                winner=winner,
                payment_status='completed'
            ).exists()
        
        for attempt in quiz_attempts:
            try:
                freelancer_register = Register.objects.get(user=attempt.freelancer)
                accuracy = (attempt.score / total_possible_points * 100) if total_possible_points > 0 else 0
                attempt_time = attempt.attempt_time.strftime("%B %d, %Y %I:%M %p")
                
                participant_data = {
                    'name': f"{freelancer_register.first_name} {freelancer_register.last_name}",
                    'profile_picture': freelancer_register.profile_picture.url if freelancer_register.profile_picture else None,
                    'score': attempt.score,
                    'attempt_time': attempt_time,
                    'accuracy': round(accuracy, 1),
                    'email': attempt.freelancer.email,
                    'total_questions': quiz_questions.count(),
                    'total_possible_points': total_possible_points,
                    'id': attempt.freelancer.id,
                }
                leaderboard_data.append(participant_data)
            except Register.DoesNotExist:
                continue

    context = {
        'event': event,
        'registrations': registrations,
        'registered_participants': registered_participants,  # Add registered participants to context
        'attendees': attended_freelancers,
        'leaderboard': leaderboard_data,
        'prize_paid': prize_paid if event.type == 'quiz' and event.prize_enabled else False,
        'total_registered': len(registered_participants),  # Add total registration count
        'total_attended': len(attended_freelancers),  # Add total attendance count
    }
    
    return render(request, 'Client/manage_single_event.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from client.models import FreelanceContract, PaymentInstallment, Project
from core.models import Register
from core.models import RefundPayment

@require_POST
def update_event_settings(request, event_id):
    event = get_object_or_404(EventAndQuiz, id=event_id)
    
    event.date = request.POST.get('event_date')
    event.max_participants = request.POST.get('max_participants')
    event.registration_status = request.POST.get('registration_enabled')  # This will now be 'open' or 'closed'
    event.registration_end_date=request.POST.get('registration_end_date')
    event.save()
    
    return redirect('client:manage_single_event', event_id=event.id)  

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail

@csrf_exempt  # Use with caution; consider using CSRF tokens in production
def send_event_link(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        try:
            event = EventAndQuiz.objects.get(id=event_id)

            # Get all registered participants for the event
            registrations = EventRegistration.objects.filter(event=event)
            emails = [registration.freelancer.email for registration in registrations if registration.freelancer.email]

            # Determine the link to send based on event type
            if event.type == 'event':
                link_to_send = event.online_link
            elif event.type == 'quiz':
                link_to_send = f'http://127.0.0.1:8000/freelancer/quiz_view/{event.id}/'  # Use event ID for quiz link
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid event type.'})

            for email in emails:
                send_mail(
                    'Event Link',
                    f'You can join the event using this link: {link_to_send}',
                    'from@example.com', 
                    [email],
                    fail_silently=False,
                )

            return JsonResponse({'status': 'success', 'message': 'Emails sent successfully.'})
        except EventAndQuiz.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Event not found.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


import razorpay
from django.conf import settings
from django.http import JsonResponse
from .models import PrizePayment
from decimal import Decimal

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

def create_prize_payment(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        winner_id = request.POST.get('winner_id')
        amount = request.POST.get('amount')

        print("Received data:", {
            "event_id": event_id,
            "winner_id": winner_id,
            "amount": amount
        })

        try:
            event = EventAndQuiz.objects.get(id=event_id)
            winner = CustomUser.objects.get(id=winner_id)
            print("Found event:", event)
            print("Found winner:", winner)
            winner_register = Register.objects.get(user=winner)
            # Convert amount to paise (Razorpay expects amount in smallest currency unit)
            amount_in_paise = int(Decimal(amount) * 100)
            print("Amount in paise:", amount_in_paise)
            razorpay_order = razorpay_client.order.create({
                'amount': amount_in_paise,
                'currency': 'INR',
                'payment_capture': '1'
            })
            print("Razorpay order created:", razorpay_order)

            # Create payment record
            payment = PrizePayment.objects.create(
                event=event,
                winner=winner,
                amount=amount,
                razorpay_order_id=razorpay_order['id']
            )
            print("Payment record created:", payment)

            response_data = {
                'status': 'success',
                'order_id': razorpay_order['id'],
                'amount': amount_in_paise,
                'key': settings.RAZORPAY_KEY_ID,
                'currency': 'INR',
                'name': f"Prize for {event.title}",
                'description': f"Prize payment to {winner_register.first_name} {winner_register.last_name}",  # Use winner_register
                'winner_email': winner.email,
                'winner_contact': winner_register.phone_number or '',
            }
            print("Sending response:", response_data)
            return JsonResponse(response_data)

        except Exception as e:
            print("Error occurred:", str(e))
            print("Error type:", type(e))
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

def verify_prize_payment(request):
    if request.method == 'POST':
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')

        try:
            # Verify the payment signature
            params_dict = {
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': razorpay_signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)

            # Update payment record
            payment = PrizePayment.objects.get(razorpay_order_id=razorpay_order_id)
            payment.payment_status = 'completed'
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.save()

            # Update event with payment reference
            event = payment.event
            event.prize_payment = payment
            event.save()

            return JsonResponse({'status': 'success'})

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)
    
    

from django.http import JsonResponse
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

@require_POST
def upload_certificate_template(request, event_id):
    try:
        event = EventAndQuiz.objects.get(id=event_id)
        
        if 'certificate_template' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No template file provided'}, status=400)
        
        template = request.FILES['certificate_template']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png']
        if template.content_type not in allowed_types:
            return JsonResponse({'status': 'error', 'message': 'Invalid file type'}, status=400)
        
        # Save the template
        file_path = f'certificate_templates/event_{event_id}_template{os.path.splitext(template.name)[1]}'
        if event.certificate_template:
            # Delete old template if exists
            default_storage.delete(event.certificate_template.path)
        
        path = default_storage.save(file_path, template)
        event.certificate_template = path
        event.save()
        
        return JsonResponse({'status': 'success', 'message': 'Template uploaded successfully'})
        
    except Event.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from .models import EventAndQuiz, EventRegistration

import requests
from pathlib import Path
import tempfile

@login_required
@nocache
def generate_certificates(request, event_id):
    try:
        event = EventAndQuiz.objects.get(id=event_id)
        
        if not event.certificate_template:
            return JsonResponse({
                'status': 'error', 
                'message': 'No certificate template found. Please upload a template first.'
            }, status=400)
        
        # Get participants who attended the event
        registrations = EventRegistration.objects.filter(
            event=event,
            attended=True
        ).select_related('freelancer')
        
        if not registrations:
            return JsonResponse({
                'status': 'error', 
                'message': 'No attended participants found'
            }, status=400)

        certificates_sent = 0
        errors = []
        
        # Load the certificate template
        template = Image.open(event.certificate_template.path)
        
        # Load the local DancingScript font from static folder
        try:
            font_path = os.path.join(settings.STATIC_ROOT, 'fonts', 'dancingscript-regular.ttf')
            if not os.path.exists(font_path):
                # Fallback to STATICFILES_DIRS if STATIC_ROOT doesn't have the file
                for static_dir in settings.STATICFILES_DIRS:
                    potential_path = os.path.join(static_dir, 'fonts', 'dancingscript-regular.ttf')
                    if os.path.exists(potential_path):
                        font_path = potential_path
                        break
            
            # Load the font with larger size
            name_font_size = 180
            font = ImageFont.truetype(font_path, name_font_size)
        except Exception as e:
            print(f"Font loading error: {str(e)}")
            font = ImageFont.load_default()

        for registration in registrations:
            try:
                # Get participant name and freelancer ID
                freelancer = registration.freelancer
                register_info = Register.objects.get(user=freelancer)
                participant_name = f"{register_info.first_name} {register_info.last_name}"
                freelancer_id = freelancer.id  # Get freelancer ID
                
                freelancer_folder = os.path.join(settings.MEDIA_ROOT, 'certificates', str(freelancer_id))
                # Check if the folder already exists before creating it
                if not os.path.exists(freelancer_folder):
                    os.makedirs(freelancer_folder) 
                
                certificate = template.copy()
                draw = ImageDraw.Draw(certificate)
                
                text_bbox = draw.textbbox((0, 0), participant_name, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                x = (certificate.width - text_width) / 2
                y = (certificate.height - text_height) / 2
                
                # Add name to certificate with a decorative color
                draw.text(
                    (x, y),
                    participant_name,
                    font=font,
                    fill=(44, 62, 80)  # Dark blue color for elegance
                )
                
                # Save certificate in the freelancer's folder
                certificate_path = os.path.join(freelancer_folder, f'certificate_{event.title}.pdf')
                certificate.save(certificate_path, format='PDF')
                
                # Send email with HTML content
                subject = f'Your Certificate for {event.title}'
                html_message = render_to_string('Client/email/certificate_email.html', {
                    'participant_name': participant_name,
                    'event_title': event.title
                })
                
                # Create email with HTML content
                email = EmailMessage(
                    subject=subject,
                    body=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[freelancer.email]
                )
                email.content_subtype = "html"  # This is the crucial line
                
                # Attach the certificate
                email.attach_file(certificate_path)  # Attach the saved certificate
                email.send()
                certificates_sent += 1
                
            except Exception as e:
                errors.append(f"Error for {participant_name}: {str(e)}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully sent {certificates_sent} certificates',
            'certificates_sent': certificates_sent,
            'errors': errors if errors else None
        })
        
    except EventAndQuiz.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Event not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'An error occurred: {str(e)}'
        }, status=500)
        
        
        
        

def client_repositories(request):
    if request.user.is_authenticated:
        # Get projects where the user is the freelancer or is a member of the assigned team
        assigned_projects = Project.objects.filter(
            freelancer=request.user
        ) | Project.objects.filter(
            team_id__in=TeamMember.objects.filter(user=request.user).values('team_id')
        )
        
        client_projects = Project.objects.filter(user=request.user)
        
        repositories = Repository.objects.filter(
            project__in=assigned_projects | client_projects
        ).distinct()

        repository_data = []
        for repo in repositories:
            project = repo.project
            
            # Get client profile picture
            client_profile_picture = project.user.register.profile_picture.url if project.user.register.profile_picture else None
            
            # Get freelancer profile picture if project has individual freelancer
            freelancer_profile_picture = None
            if project.freelancer:
                try:
                    freelancer_register = Register.objects.get(user=project.freelancer)
                    freelancer_profile_picture = freelancer_register.profile_picture.url if freelancer_register.profile_picture else None
                except Register.DoesNotExist:
                    pass

            # Get team members if project has a team
            team_members = []
            if project.team:
                team_members = TeamMember.objects.filter(team=project.team)
                team_members = [{
                    'user_id': member.user.id,
                    'profile_picture': member.user.register.profile_picture.url if member.user.register.profile_picture else None,
                    'name': f"{member.user.register.first_name} {member.user.register.last_name}"
                } for member in team_members]

            repository_data.append({
                'repository': repo,
                'repository_id': repo.id,
                'project_title': project.title,
                'project_category': getattr(project, 'category', 'N/A'),
                'client_profile_picture': client_profile_picture,
                'client_name': f"{project.user.register.first_name} {project.user.register.last_name}",
                'freelancer_profile_picture': freelancer_profile_picture,
                'freelancer_name': f"{project.freelancer.register.first_name} {project.freelancer.register.last_name}" if project.freelancer else None,
                'team_members': team_members if project.team else [],
                'is_team_project': bool(project.team)
            })

        is_project_manager = TeamMember.objects.filter(user=request.user, role='PROJECT_MANAGER').exists()
        
    else:
        repository_data = []
        is_project_manager = False
        
    return render(request, 'Client/Repositories.html', {
        'repositories': repository_data,
        'is_project_manager': is_project_manager
    })

from core.models import SubscriptionPlan
def plans(request):
    plans = SubscriptionPlan.objects.all()
    
    for plan in plans:
        plan.features_list = plan.features.split(',')  
    return render(request, 'Client/plans.html', {'plans': plans})
