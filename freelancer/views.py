from datetime import datetime
import random
import string
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import io
import os
from django.shortcuts import get_object_or_404, redirect, render

from client.models import Message,ClientProfile, FreelanceContract, PaymentInstallment, Project, Review,SharedFile, SharedNote,SharedURL,Repository, Task,Complaint
from core.decorators import nocache
from core.models import CustomUser, Event, Notification, Register

from django.contrib.auth.decorators import login_required

from freelancer.models import FreelancerProfile, Proposal, ProposalFile, Todo,Document
from administrator.models import Template
from django.contrib import messages
from django.db.models import Q


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import json
from io import BytesIO
from xhtml2pdf import pisa
from datetime import timedelta
from django.utils import timezone

from django.db.models import Sum,Avg
from django.db.models.functions import TruncMonth
@login_required
@nocache
def freelancer_view(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'freelancer':
        return redirect('login')
        
    uid = request.session['uid']
    logged_user = request.user
    uid = request.user.id
    profile2 = Register.objects.get(user_id=uid)
    todos = Todo.objects.filter(user_id=uid)
    profile1 = CustomUser.objects.get(id=uid)
    notifications = Notification.objects.filter(user=logged_user).order_by('-created_at')[:5]

    current_date = timezone.now().date()
    one_week_later = current_date + timedelta(days=7)
    
    events = Event.objects.filter(
        user=logged_user,
        start_time__range=[current_date, one_week_later]
    ).order_by('start_time')

    total_projects = Project.objects.filter(freelancer=logged_user).count()
    completed_projects = Project.objects.filter(freelancer=logged_user, project_status='Completed').count()
    not_completed_projects = total_projects - completed_projects

    for event in events:
        one_day_before = event.start_time.date() - timedelta(days=1)
        
        if one_day_before == current_date:
            notification_message = f"Reminder: Upcoming event '{event.title}' tomorrow!"
            Notification.objects.get_or_create(
                user=logged_user,
                message=notification_message,
                defaults={'is_read': False}
            )
        
        if event.start_time.date() == current_date:
            notification_message = f"Reminder: Event '{event.title}' is today!"
            Notification.objects.get_or_create(
                user=logged_user,
                message=notification_message,
                defaults={'is_read': False}
            )
    freelancer_projects = Project.objects.filter(freelancer=logged_user)
    project_progress_data = []

    for project in freelancer_projects:
        tasks = Task.objects.filter(project=project)
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='Completed').count()
        progress_percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0.0

        if progress_percentage == 100:
            project.project_status = 'Completed'
            project.save()
        
        client_profile = ClientProfile.objects.get(user=project.user_id)
        if client_profile.client_type == 'Individual':
            register_instance = Register.objects.get(user=project.user_id)

            first_name = register_instance.first_name
            last_name = register_instance.last_name

            client_name = f"{first_name} {last_name}"
        else:
            client_name = client_profile.company_name
        project_progress_data.append({
            'project': project,
            'progress_percentage': progress_percentage,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'client_name': client_name  
        })
        
    if logged_user.is_authenticated and profile2 and not any([
        profile2.phone_number or '',
        profile2.profile_picture or '',
        profile2.bio_description or '',
        profile2.location or ''
    ]):
        return render(request, 'freelancer/Add_profile.html', {
            'profile1': profile1,
            'profile2': profile2,
            'uid': uid,
            'todos': todos,
            'notifications': notifications,
            'events': events
        })
    
    # Calculate monthly earnings based on the paid_at date and status
    monthly_earnings = PaymentInstallment.objects.filter(
        contract__freelancer=logged_user,  # Ensure the contract is associated with the logged-in freelancer
        status='paid',  # Only include installments with status 'paid'
        paid_at__isnull=False  # Ensure only paid installments are considered
    ).annotate(
        month=TruncMonth('paid_at')
    ).values('month').annotate(
        total_earnings=Sum('amount')
    ).order_by('month')

    # Prepare data for the chart
    earnings_data = {
        'months': [entry['month'].strftime('%B') for entry in monthly_earnings],
        'earnings': [float(entry['total_earnings']) for entry in monthly_earnings]
    }

    # Calculate top clients by revenue
    top_clients = Project.objects.filter(freelancer=logged_user).values(
        'user__id',
        'user__register__first_name',
        'user__register__last_name',
        'user__clientprofile__company_name'
    ).annotate(
        total_revenue=Sum('budget')
    ).order_by('-total_revenue')[:5]

    top_clients_data = {
        'clients': [],
        'revenues': []
    }

    for client in top_clients:
        if client['user__clientprofile__company_name']:
            client_name = client['user__clientprofile__company_name']
        else:
            client_name = f"{client['user__register__first_name']} {client['user__register__last_name']}"
        
        top_clients_data['clients'].append(client_name)
        top_clients_data['revenues'].append(float(client['total_revenue']))

    # Calculate average ratings for each category
    avg_ratings = Review.objects.filter(
        reviewer=logged_user
    ).aggregate(
        overall_rating=Avg('overall_rating'),
        quality_of_work=Avg('quality_of_work'),
        communication=Avg('communication'),
        adherence_to_deadlines=Avg('adherence_to_deadlines'),
        professionalism=Avg('professionalism'),
        problem_solving_ability=Avg('problem_solving_ability')
    )

    # Prepare data for the chart
    rating_data = {
        'categories': [
            'Overall Rating', 'Quality of Work', 'Communication',
            'Adherence to Deadlines', 'Professionalism', 'Problem Solving'
        ],
        'values': [
            avg_ratings['overall_rating'] or 0,
            avg_ratings['quality_of_work'] or 0,
            avg_ratings['communication'] or 0,
            avg_ratings['adherence_to_deadlines'] or 0,
            avg_ratings['professionalism'] or 0,
            avg_ratings['problem_solving_ability'] or 0
        ]
    }

    return render(request, 'freelancer/index.html', {
        'profile2': profile2,
        'profile1': profile1,
        'uid': uid,
        'todos': todos,
        'notifications': notifications,
        'events': events,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'not_completed_projects': not_completed_projects,
        'project_progress_data': project_progress_data,
        'earnings_data': json.dumps(earnings_data),
        'top_clients_data': json.dumps(top_clients_data),
        'rating_data': rating_data,
    })



    
@login_required
@nocache
def tasks_list(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission:
        
        tasks = Task.objects.filter(project__freelancer=profile1).order_by('due_date')

        return render(request, 'freelancer/tasks.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'tasks': tasks,  
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })
        


@login_required
@nocache
def AddProfileFreelancer(request, uid):
    if not request.user.is_authenticated:
        return redirect('login')

    user = CustomUser.objects.get(id=uid)
    profile, created = FreelancerProfile.objects.get_or_create(user=user)
    todos = Todo.objects.filter(user_id=uid)
    if request.method == 'POST':
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        phone_number = request.POST.get('phone_number')
        profile_picture = request.FILES.get('profile_picture')
        bio_description = request.POST.get('bio_description')
        location = request.POST.get('location')
        linkedin = request.POST.get('linkedin')
        instagram = request.POST.get('instagram')
        twitter = request.POST.get('twitter')
        professional_titles = request.POST.getlist('professional_titles')
        experience_level = request.POST.get('experience_level')
        portfolio_link = request.POST.get('portfolio_link')
        education = request.POST.get('education')
        resume = request.FILES.get('resume')
        aadhaar = request.FILES.get('aadhaar')
        selected_skills = request.POST.getlist('skills')
        work=request.POST.get('work_type')

        register, _ = Register.objects.get_or_create(user=user)
        register.first_name = first_name
        register.last_name = last_name
        register.phone_number = phone_number
        if profile_picture:
            register.profile_picture = profile_picture
        register.bio_description = bio_description
        register.location = location
        register.linkedin = linkedin
        register.instagram = instagram
        register.twitter = twitter
        register.save()

        # Update FreelancerProfile (freelancer-specific fields)
        profile.experience_level = experience_level
        profile.portfolio_link = portfolio_link
        profile.education = education
        if resume:
            profile.resume = resume
        if aadhaar:
            profile.aadhaar_document=aadhaar
        profile.skills = selected_skills
        profile.professional_title = professional_titles
        profile.work_type=work
        profile.save()

        return redirect('freelancer:freelancer_view')

    context = {
        'profile': profile,
        'uid': uid,
        'todos': todos,
    }

    return render(request, 'freelancer/Add_profile.html', context)




@login_required
@nocache
def account_settings(request):
    uid=request.user.id
    profession = [
    'Web Developer','Front-End Developer','Back-End Developer','Full-Stack Developer',
    'Mobile App Developer','Android Developer','iOS Developer','UI/UX Designer','Graphic Designer',
    'Logo Designer','Poster Designer','Machine Learning Engineer','Artificial Intelligence Specialist','Software Developer',
]
    skills = [
    "java", "c++", "python", "eclipse", "visual studio", "html/css", "javascript", "bootstrap", "sass", 
    "swift", "xcode", "kotlin", "android studio", "flutter", "react native", "r", "jupyter", "pandas", 
    "numpy", "tensorflow", "pytorch", "keras", "scikit-learn", "adobe xd", "sketch", "figma", "invision", 
    "react", "angular", "vue.js", "webpack", "node.js", "django", "ruby on rails", "spring boot", 
    "mongodb", "express.js", "php (lamp stack)", "angular (mean stack)", "adobe illustrator", 
    "coreldraw", "affinity designer", "adobe photoshop", "adobe indesign", "canva", "opencv"
]

    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    todos = Todo.objects.filter(user_id=uid)
    if freelancer.professional_title:
        freelancer.professional_title = freelancer.professional_title.strip('[]').replace("'", "").split(', ')
    else:
        freelancer.professional_title = []

    if freelancer.skills:
        freelancer.skills = freelancer.skills.strip('[]').replace("'", "").split(', ')
    else:
        freelancer.skills = []
    return render(request, 'freelancer/accounts.html',{'profile1':profile1,
                                                       'profile2':profile2,
                                                       
                                                       'freelancer':freelancer,
                                                       'profession':profession,
                                                       'skills':skills,'todos':todos,
                                                       
                                                       })


@login_required
@nocache
def notification_mark_as_read(request,not_id):
    notification = Notification.objects.get(id=not_id)
    notification.is_read = True
    notification.save()
    next_url = request.GET.get('next', 'freelancer:freelancer_view')
    return redirect(next_url)





@login_required
@nocache
def change_password(request, uid):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    todos = Todo.objects.filter(user_id=uid)

    if request.method == 'POST':
        current = request.POST.get('current_password')
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')

        
        if profile1.check_password(current):
            profile1.set_password(new_pass)
            profile1.save()
            messages.success(request, 'Your password has been changed successfully!')
            return render(request, 'freelancer/accounts.html', {
                'profile1': profile1,
                'profile2': profile2,
                'freelancer': freelancer,
                'todos': todos,
            })
            
        else:
            messages.error(request, 'Current password is incorrect.')

    return render(request, 'freelancer/accounts.html', {
        'profile1': profile1,
        'profile2': profile2,
        'freelancer': freelancer,
        'todos': todos,
    })


@login_required
@nocache
def update_profile(request,uid):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    todos = Todo.objects.filter(user_id=uid)
    
    if request.method == 'POST':
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        phone_number = request.POST.get('phone_number')
        bio_description = request.POST.get('bio_description')
        location = request.POST.get('location')
        linkedin = request.POST.get('linkedin')
        instagram = request.POST.get('instagram')
        twitter = request.POST.get('twitter')
        professional_titles = request.POST.getlist('professional_titles')
        experience_level = request.POST.get('experience_level')
        portfolio_link = request.POST.get('portfolio_link')
        education = request.POST.get('education')
        resume = request.FILES.get('resume')
        aadhaar = request.FILES.get('aadhaar')
        selectedskills = request.POST.getlist('skills')
        profile2.first_name = first_name
        profile2.last_name = last_name
        profile2.phone_number = phone_number
        
        profile2.bio_description = bio_description
        profile2.location = location
        profile2.linkedin = linkedin
        profile2.instagram = instagram
        profile2.twitter = twitter
        profile2.save()

        freelancer.experience_level = experience_level
        freelancer.portfolio_link = portfolio_link
        freelancer.education = education
        if resume:
            freelancer.resume = resume
        if aadhaar:
            freelancer.aadhaar_document = aadhaar
        freelancer.skills=selectedskills
        
        freelancer.professional_title = professional_titles
        freelancer.save()
        messages.success(request, 'Your profile has been changed successfully!')
        return redirect('freelancer:account_settings')
    return render(request, 'freelancer/accounts.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer,'todos':todos,})  
  
  

@login_required
@nocache
def change_profile_image(request,uid):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    todos = Todo.objects.filter(user_id=uid)
    if request.method=='POST':
        
        profile_picture = request.FILES.get('profile_picture')
        if profile_picture:
            profile2.profile_picture = profile_picture
            profile2.save()
            messages.success(request, 'Your profile picture has been changed successfully!')
            return redirect('freelancer:account_settings')
    return render(request, 'freelancer/accounts.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer,'todos':todos,})  


   
        
@login_required
@nocache
def client_list(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission:
        todos = Todo.objects.filter(user_id=uid)
        
        users_with_profiles = CustomUser.objects.filter(role='client').exclude(
            clientprofile__client_type__exact=''
        ).select_related('clientprofile')

        registers = Register.objects.all()
        register_dict = {reg.user_id: reg for reg in registers}  

        
        search_query = request.GET.get('search', '').lower()
        filter_query = request.GET.get('filter', '')

        if search_query:
            users_with_profiles = users_with_profiles.filter(
                Q(clientprofile__company_name__icontains=search_query) |
                Q(register__first_name__icontains=search_query) |
                Q(register__last_name__icontains=search_query) |
                Q(clientprofile__license_number__icontains=search_query)
            )

        if filter_query:
            users_with_profiles = users_with_profiles.filter(clientprofile__client_type=filter_query)
        
        context = [
            {
                'user': user,
                'client_profile': user.clientprofile if hasattr(user, 'clientprofile') else None,
                'register': register_dict.get(user.id)  
            }
            for user in users_with_profiles
        ]

        return render(request, 'freelancer/ViewClients.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'users': context,
            'todos': todos,
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })
        
        
        
@login_required
@nocache
def client_detail(request, cid):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        profile3 = CustomUser.objects.get(id=cid)
        profile4 = Register.objects.get(user_id=cid)
        client = ClientProfile.objects.get(user_id=cid)
        todos = Todo.objects.filter(user_id=uid)
        
        reviews = Review.objects.filter(reviewee=profile3).order_by('-review_date')

        review_details = []
        for review in reviews:
            
            reviewer_profile = Register.objects.get(user_id=review.reviewer.id)
            
           
            reviewer_name = reviewer_profile.first_name + ' ' + reviewer_profile.last_name
          
            review_details.append({
                'review': review,
                'reviewer_name': reviewer_name,
                'reviewer_image': reviewer_profile.profile_picture.url if reviewer_profile.profile_picture else None,
            })

        return render(request, 'freelancer/SingleClient.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'profile3': profile3,
            'profile4': profile4,
            'client': client,
            'todos': todos,
            'reviews': review_details,  # Include reviews in context
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })

        
        
      


           
        
@login_required
@nocache
def calendar(request):
    if 'uid' not in request.session and not request.user.is_authenticated and request.user.role != 'freelancer':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    client = FreelancerProfile.objects.get(user_id=uid)
    events = Event.objects.filter(user=uid)
    events_data = [
        {
            'id': event.id,  # Change this to 'id'
            'title': event.title,
            'start': event.start_time.isoformat(),
            'end': (event.end_time + timedelta(days=1)).isoformat(),  
            'description': event.description,
            'color': event.color,
        }
        for event in events
    ]

    if profile1.permission:
        return render(request, 'freelancer/calendar.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
            'events_data': events_data  
        })
    else:
        return render(request, 'client/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        })

        

 
 
 
 
@login_required
@nocache
def add_new_event(request):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.session.get('uid')
    if not uid:
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    freelancer = get_object_or_404(FreelancerProfile, user_id=uid)

    if profile1.permission:
        if request.method == 'POST':
            title = request.POST.get('title')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            description = request.POST.get('description')
            color = request.POST.get('color')

            user = request.user
            Event.objects.create(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                color=color,
                user=user
            )
            return redirect('freelancer:calendar')  
        
    
    return render(request, 'freelancer/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'freelancer': freelancer,
    })
    
    
        
@login_required
@nocache
def update_event(request):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.session.get('uid')
    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    freelancer = get_object_or_404(FreelancerProfile, user_id=uid)

    if profile1.permission:
        if request.method == 'POST':
            event_id = request.POST.get('event_id')
            if not event_id:
              
                return redirect('freelancer:calendar')  

            event = get_object_or_404(Event, id=event_id)

            title = request.POST.get('title')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            description = request.POST.get('description')
            color = request.POST.get('color')

            event.title = title
            event.start_time = start_time
            event.end_time = end_time
            event.description = description
            event.color = color
            
            event.save()

            return redirect('freelancer:calendar')

        

    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })



@login_required
@nocache
def delete_event(request):
    if 'uid' not in request.session or not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.session['uid']
    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    freelancer = get_object_or_404(FreelancerProfile, user_id=uid)

    if profile1.permission:
        if request.method == 'POST':
            event_id = request.POST.get('event_id')
            if not event_id:
                return redirect('freelancer:calendar')  # Handle missing event_id case

            try:
                event = Event.objects.get(id=event_id)
                event.delete()
            except Event.DoesNotExist:
                pass  # Handle case where event does not exist

            return redirect('freelancer:calendar')

        else:
            return redirect('freelancer:calendar')

    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })





@login_required
@nocache
def todo(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission==True:
        todos = Todo.objects.filter(user_id=uid)
        return render(request, 'freelancer/todo.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer,'todos':todos})
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
        


@login_required
@nocache
def add_todo(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission==True:
        if request.method=='POST':
            title=request.POST.get('title')
            next_url = request.POST.get('next')
            Todo.objects.create(user=profile1,title=title)
            return redirect(next_url)
        todos = Todo.objects.filter(user_id=uid)
        return render(request, 'freelancer/todo.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer,'todos':todos})
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
        
                            


@login_required
@nocache
def update_todo(request):
    uid = request.session.get('uid')
    
    if uid is None:
        return redirect('login')

    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission:
        if request.method == 'POST':
            todo_title = request.POST.get('title')
            todo_id = request.POST.get('todo_id')
            if todo_id:
                todo = get_object_or_404(Todo, id=todo_id)
                todo.title = todo_title
                todo.save()
                return redirect('freelancer:todo')  
        
        return redirect('freelancer:todo') 

    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })




@login_required
@nocache
def delete_todo(request, todo_id):
    uid = request.session.get('uid')

    if uid is None:
        return redirect('login')

    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        if request.method == 'POST':
            Todo.objects.filter(id=todo_id).delete()
            return redirect(request.POST.get('next')) 
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })

    todos = Todo.objects.filter(user_id=uid)
    return render(request, 'freelancer/todo.html', {
        'profile1': profile1,
        'profile2': profile2,
        'freelancer': freelancer,
        'todos': todos
    })

        
        
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Todo

@require_POST
def update_todo_status(request):
    todo_id = request.POST.get('todo_id')
    is_completed = request.POST.get('is_completed') == 'true'
    
    try:
        todo = Todo.objects.get(id=todo_id)
        todo.is_completed = is_completed
        todo.save()
        return JsonResponse({'status': 'success'})
    except Todo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Todo not found'}, status=404)
               
        

@login_required
@nocache
def view_project(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    # Mapping professions to corresponding categories
    profession_category_map = {
        'Web Developer': 'Web Development',
        'Front-End Developer': 'Front-End Development',
        'Back-End Developer': 'Back-End Development',
        'Full-Stack Developer': 'Full-Stack Development',
        'Mobile App Developer': 'Mobile Development',
        'Android Developer': 'Android Development',
        'iOS Developer': 'iOS Development',
        'UI/UX Designer': 'UI/UX Design',
        'Graphic Designer': 'Graphic Design',
        'Logo Designer': 'Logo Design',
        'Poster Designer': 'Poster Design',
        'Machine Learning Engineer': 'Machine Learning Engineering',
        'Artificial Intelligence Specialist': 'Artificial Intelligence',
        'Software Developer': 'Software Development'
    }

    if profile1.permission:
        professions = []
        if freelancer and freelancer.professional_title:
            professions = freelancer.professional_title.strip('[]').replace("'", "").split(', ')

        profession_categories = [profession_category_map.get(profession) for profession in professions if profession in profession_category_map]

        todos = Todo.objects.filter(user_id=uid)

        search = request.GET.get('search', '')
        filter_type = request.GET.get('filter_type', '')
        status = request.GET.get('status', '')
        cat = request.GET.get('category', '')


        projects = Project.objects.all()

        if profession_categories:
            query = Q()
            for category in profession_categories:
                query |= Q(category=category)
            projects = projects.filter(query)

        if search:
            projects = projects.filter(Q(title__icontains=search) | Q(category__icontains=search))

        if filter_type == 'category' and cat:
            projects = projects.filter(category=cat)

        if filter_type == 'status' and status:
            projects = projects.filter(status=status)

        project_details = []
        for project in projects:
            cid = project.user_id
            client_profile = ClientProfile.objects.get(user_id=cid)
            client_register = Register.objects.get(user_id=cid)

            has_proposal = Proposal.objects.filter(project_id=project.id, freelancer_id=uid).exists()

            project_details.append({
                'project': project,
                'client_profile': client_profile,
                'client_register': client_register,
                'has_proposal': has_proposal  # Pass proposal status to template
            })

        categories = [
            "Web Development", "Front-End Development", "Back-End Development", "Full-Stack Development", "Mobile Development",
            "Android Development", "iOS Development", "UI/UX Design", "Graphic Design", "Logo Design", "Poster Design", 
            "Software Development", "Machine Learning Engineering", "Artificial Intelligence"
        ]

        return render(request, 'freelancer/ViewProjects.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'todos': todos,
            'project_details': project_details,
            'categories': categories
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })


  
  
  
@login_required
@nocache
def single_project_view(request, pid):
    uid = request.user.id  # Use request.user.id to get the logged-in user's ID
    
    # Fetch user profiles and project
    profile1 = get_object_or_404(CustomUser, id=uid)
    profile2 = get_object_or_404(Register, user_id=uid)
    freelancer = get_object_or_404(FreelancerProfile, user_id=uid)
    
    if profile1.permission:
        project = get_object_or_404(Project, id=pid)
        client_user_id = project.user_id  
        client_profile = get_object_or_404(ClientProfile, user_id=client_user_id)
        client_register = get_object_or_404(Register, user_id=client_user_id)
        
        proposal_exists = Proposal.objects.filter(freelancer=uid, project_id=pid).exists()
        
        todos = Todo.objects.filter(user_id=uid)
        
        context = {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'todos': todos,
            'project': project,
            'client_profile': client_profile,
            'client_register': client_register,
            'proposal_exists': proposal_exists,
        }
        return render(request, 'freelancer/SingleProject.html', context)
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
        
    
    
 
@login_required
@nocache
def add_new_proposal(request,pid):
    
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission==True:
        todos = Todo.objects.filter(user_id=uid)
        project=Project.objects.get(id=pid)
        uid=project.user_id
        client_profile = ClientProfile.objects.get(user_id=uid)
        client_register = Register.objects.get(user_id=uid)
        if request.method == 'POST':
            title = request.POST.get('proposal_title')
            description = request.POST.get('proposal_description')
            budget = request.POST.get('proposal_budget')
            end_date = request.POST.get('proposal_deadline')
            
            proposal = Proposal(
                project=project,
                freelancer=profile1,
                title=title,
                description=description,
                budget=budget,
                proposed_deadline=end_date
            )
            proposal.save()
            return render(request, 'freelancer/SingleProject.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer,'todos':todos,'project':project,'client_profile':client_profile,'client_register':client_register})
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
         
         
 
        
@login_required
@nocache
def proposal_list(request):
    uid = request.session.get('uid')
    
    if uid is None:
        return redirect('login')

    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        todos = Todo.objects.filter(user_id=uid)
        
        proposals = Proposal.objects.filter(freelancer_id=uid).select_related('project')
        
        project_details = []
        for proposal in proposals:
            project = proposal.project
            client_profile = ClientProfile.objects.get(user_id=project.user_id)
            reg = Register.objects.get(user_id=project.user_id)
            
            print(f"Proposal: {proposal}, Project: {project}, Client: {reg.first_name} {reg.last_name}")

            if client_profile.client_type == 'Individual':
                client_name = f"{reg.first_name} {reg.last_name}"
            else:
                client_name = client_profile.company_name
            
            project_details.append({
                'proposal': proposal,
                'project': project,
                'client_name': client_name
            })
        
        return render(request, 'freelancer/Proposals.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'todos': todos,
            'project_details': project_details
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })


        
        
@login_required
@nocache        
def generate_proposal(request,pid):
    
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission==True:
        todos = Todo.objects.filter(user_id=uid)
        project=Project.objects.get(id=pid)
        uid=project.user_id
        client_profile = ClientProfile.objects.get(user_id=uid)
        client_register = Register.objects.get(user_id=uid)
        userprofile=CustomUser.objects.get(id=uid)
        fancy_id=generate_fancy_proposal_id()
        
        if request.method == 'POST':
            description = request.POST.get('proposal_description')
            if project.allow_bid:
                budget = request.POST.get('proposal_budget')
            else:
                budget = project.budget
            end_date = request.POST.get('proposal_deadline')
            
            proposal = Proposal(
                project=project,
                freelancer=profile1,
                proposal_details=description,
                budget=budget,
                deadline=end_date,
                fancy_num=fancy_id
            )
            proposal.save()
            return redirect('freelancer:proposal_detail1', prop_id=proposal.id)
        return render(request, 'freelancer/template.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer,'todos':todos,'project':project,'client_profile':client_profile,'client_register':client_register,'userprofile':userprofile,'number':fancy_id})
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
         
     
  
from django.core.files.base import ContentFile

@login_required
@nocache
def proposal_detail1(request, prop_id):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    proposal = get_object_or_404(Proposal, id=prop_id)
    project = Project.objects.get(id=proposal.project_id)
    client_profile = ClientProfile.objects.get(user_id=project.user_id)
    client_register = Register.objects.get(user_id=project.user_id)
    userprofile = CustomUser.objects.get(id=project.user_id)

    if profile1.permission:
        todos = Todo.objects.filter(user_id=uid)

        if request.method == 'POST':
            # Handle additional file uploads
            files = request.FILES.getlist('additional_files[]')
            for file in files:
                ProposalFile.objects.create(proposal=proposal, file=file)

            pdf_file = request.FILES.get('proposal_pdf')
            if pdf_file:
                proposal.proposal_file.save(f'proposal_{proposal.id}.pdf', pdf_file)
                proposal.save()

            return redirect('freelancer:view_created_proposals')

        return render(request, 'freelancer/proposal_preview.html', {
            'proposal': proposal,
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'client_profile': client_profile,
            'client_register': client_register,
            'userprofile': userprofile
        })

    return render(request, 'freelancer/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'freelancer': freelancer
    })


def generate_fancy_proposal_id(length=4):
    digits = string.digits  # Digits only
    proposal_id = '#'+''.join(random.choices(digits, k=length))
    return proposal_id




@login_required
@nocache
def proposal_detail2(request, prop_id):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    proposal = get_object_or_404(Proposal, id=prop_id)
    project = Project.objects.get(id=proposal.project_id)
    client_profile = ClientProfile.objects.get(user_id=project.user_id)
    client_register = Register.objects.get(user_id=project.user_id)
    userprofile = CustomUser.objects.get(id=project.user_id)

    if profile1.permission:
        todos = Todo.objects.filter(user_id=uid)

        return render(request, 'freelancer/single_proposal.html', {
            'proposal': proposal,
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'client_profile': client_profile,
            'client_register': client_register,
            'userprofile': userprofile
        })

    return render(request, 'freelancer/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'freelancer': freelancer
    })


        
        

@login_required
@nocache
def view_created_proposals(request):
    uid = request.session.get('uid')
    
    if uid is None:
        return redirect('login')

    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        todos = Todo.objects.filter(user_id=uid)
        proposals = Proposal.objects.filter(freelancer=uid).select_related('project')
        
        project_details = []
        for proposal in proposals:
            project = proposal.project
            client_profile = get_object_or_404(ClientProfile, user_id=project.user_id)
            client_register = get_object_or_404(Register, user_id=project.user_id)
            
            try:
                contract = FreelanceContract.objects.get(project=project)
                installments = PaymentInstallment.objects.filter(contract=contract)
            except FreelanceContract.DoesNotExist:
                contract = None
                installments = None
            
            project_details.append({
                'proposal': proposal,
                'project': project,
                'client_profile': client_profile,
                'client_register': client_register,
                'contract': contract,
                'installments': installments
            })

        return render(request, 'freelancer/proposals_created.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'todos': todos,
            'project_details': project_details
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })







@login_required
@nocache
def edit_created_proposal(request, prop_id):
    uid = request.session.get('uid')
    
    if uid is None:
        return redirect('login')

    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    proposal = get_object_or_404(Proposal, id=prop_id)
    project = Project.objects.get(id=proposal.project_id)
    client_profile = ClientProfile.objects.get(user_id=project.user_id)
    client_register = Register.objects.get(user_id=project.user_id)
    userprofile = CustomUser.objects.get(id=project.user_id)
    
    if profile1.permission:
        todos = Todo.objects.filter(user_id=uid)
        
        if request.method == 'POST':
            # Update proposal details
            description = request.POST.get('proposal_description')
            budget = request.POST.get('proposal_budget')
            end_date = request.POST.get('proposal_deadline')

            if description:
                proposal.proposal_details = description
            if budget:
                proposal.budget = budget
            if end_date:
                proposal.deadline = end_date
            
            # Handle additional file uploads
            if 'additional_files[]' in request.FILES:
                files = request.FILES.getlist('additional_files[]')
                for file in files:
                    # Save the new file
                    ProposalFile.objects.create(proposal=proposal, file=file)

            # Save the uploaded PDF file if present
            pdf_file = request.FILES.get('proposal_pdf')
            if pdf_file:
                proposal.proposal_file.save(f'proposal_{proposal.id}.pdf', pdf_file)
            
            proposal.save()
            return redirect('freelancer:view_created_proposals')
        
        return render(request, 'freelancer/edit_proposal_template.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'todos': todos,
            'proposal': proposal,
            'client_profile': client_profile,
            'client_register': client_register,
            'userprofile': userprofile,
            'edit_mode': True
        })
    
    return render(request, 'freelancer/PermissionDenied.html', {
        'profile1': profile1,
        'profile2': profile2,
        'freelancer': freelancer
    })
        
   
   
   
        
@login_required
@nocache
def download_proposal_pdf(request, prop_id):
    uid = request.session.get('uid')
    
    if uid is None:
        return redirect('login')

    proposal = Proposal.objects.get(id=prop_id)
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    
    template_path = 'freelancer/proposal_preview.html'  

    
    template = get_template(template_path)
    context = {
        'proposal': proposal,
        'profile2': profile2,
        'freelancer': freelancer,
        'profile1': profile1,
        'edit_mode': False, 
    }
    html = template.render(context)

    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="proposal.pdf"'

    
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=response)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    return response


      
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
    
    register_info = Register.objects.get(user_id=uid)
    first_name = register_info.first_name
    last_name = register_info.last_name
    name = f"{first_name} {last_name}"
    
    context = {
        'user_name': name
    }
    html_content = render_to_string('freelancer/deactivation.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()
    return redirect('login')




from core.models import CancellationRequest
@login_required
@nocache
def view_repository(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        project = get_object_or_404(Project, id=repository.project_id)
        client_profile = ClientProfile.objects.get(user_id=project.user_id)
        client_register = Register.objects.get(user_id=project.user_id)
        
        if client_profile.client_type == 'Individual':
            client_name = f"{client_register.first_name} {client_register.last_name}"
        else:
            client_name = client_profile.company_name
        
        client_profile_picture = client_register.profile_picture if client_register.profile_picture else None

        shared_files = SharedFile.objects.filter(repository=repository).values(
            'file', 'uploaded_at', 'uploaded_by', 'description'
        )
        shared_urls = SharedURL.objects.filter(repository=repository).values(
            'url', 'shared_at', 'shared_by', 'description'
        )
        proposals = Proposal.objects.filter(project=project,status='Accepted')
        contracts = FreelanceContract.objects.filter(project=project)
        items = []
        
        for file in shared_files:
            items.append({
                'type': 'file',
                'url': file['file'],  # Use 'url' for the file URL
                'path': file['file'].split('/')[-1],  # Extract the file name from the path
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
        notes = SharedNote.objects.filter(repository=repository).order_by('added_at')
        tasks=Task.objects.filter(project=project)
        try:
            cancellation_details = CancellationRequest.objects.get(project=project)
        except CancellationRequest.DoesNotExist:
            cancellation_details = None  # Set to None if no cancellation request exists

        return render(request, 'freelancer/SingleRepository.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'repository': repository,
            'items': items,
             'notes':notes,
            'tasks':tasks,
            'client_name': client_name,
            'client_profile_picture': client_profile_picture,
            'proposals': proposals,
            'contracts': contracts,
            
            'project': project,
            'cancellation_details': cancellation_details,
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })
        


@login_required
@nocache
def add_file(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method == 'POST':
            file = request.FILES['files']
            description = request.POST.get('description')
            newfile = SharedFile(
                file=file,
                repository=repository,
                description=description,
                uploaded_by=request.user
            )
            newfile.save()

            messages.success(request, 'Files added successfully.')
            return redirect('freelancer:view_repository', repo_id=repository.id)
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })

@login_required
@nocache
def add_url(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method == 'POST':
            url = request.POST.get('url')
            description = request.POST.get('description')
            newurl = SharedURL(
                url=url,
                repository=repository,
                description=description,
                shared_by=request.user
            )
            newurl.save()

            messages.success(request, 'URL added successfully.')
            return redirect('freelancer:view_repository', repo_id=repository.id)
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })

@login_required
@nocache
def add_note(request, repo_id):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        repository = get_object_or_404(Repository, id=repo_id)
        if request.method == 'POST':
            file = request.FILES['files']
            description = request.POST.get('description')
            newfile = SharedFile(
                file=file,
                repository=repository,
                description=description,
                uploaded_by=request.user
            )
            newfile.save()

            messages.success(request, 'Files added successfully.')
            return redirect('freelancer:view_repository', repo_id=repository.id)
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })



@login_required
def update_freelancer_signature(request):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.user.id
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        if request.method == 'POST':
            contract_id=request.POST.get('contract')
            contract = get_object_or_404(FreelanceContract, id=contract_id, freelancer=request.user)
            file = request.FILES.get('freelancer_signature')
            if file:
                contract.freelancer_signature = file
                contract.save()

            messages.success(request, 'Signature added successfully.')
            return redirect('freelancer:view_contract', cont_id=contract_id)
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })





@login_required
@nocache
def view_contract(request, cont_id):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission:
        contract = FreelanceContract.objects.filter(id=cont_id).first()
        if contract:
            payment_installments = PaymentInstallment.objects.filter(contract=contract)
            client_profile = contract.project.user.clientprofile  
            client_register = contract.project.user.register  
            project_details = contract.project  

            accepted_proposal = Proposal.objects.filter(project=project_details, status='accepted').first()

            context = {
                'profile1': profile1,
                'profile2': profile2,
                'freelancer': freelancer,
                'detail': {
                    'contract': contract,
                    'project': project_details,
                    'client_profile': client_profile,
                    'client_register': client_register,
                    'proposal': accepted_proposal,
                    'installments': payment_installments,
                }
            }
            return render(request, 'freelancer/ViewContract.html', context)
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })



@csrf_exempt
def upload_pdf(request):
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf')
        contract_id = request.POST.get('contract_id')

        if pdf_file and contract_id:
            try:
                contract = FreelanceContract.objects.get(id=contract_id)
                
                if contract.pdf_version:
                    return JsonResponse({'status': 'exists', 'message': 'File already exists'}, status=400)
                
                contract.pdf_version.save(pdf_file.name, pdf_file)
                contract.save()
                return JsonResponse({'status': 'success'})
            
            except FreelanceContract.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Contract not found'}, status=404)
        
        return JsonResponse({'status': 'error', 'message': 'Invalid file or contract ID'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)



@login_required
@nocache
def submit_user_review(request):
    if request.method == 'POST':
        review_text = request.POST.get('review')
        reviewer_id = request.user.id
        client_id = request.POST.get('client_id')
        project_id = int(request.POST.get('project_id'))
        overall_rating = int(request.POST.get('overall_rating'))
        client_id = int(client_id)
        
        # Debugging prints
        print(f"Review Text: {review_text}")
        print(f"Reviewer ID: {reviewer_id}")
        print(f"Reviewee ID: {client_id}")
        print(f"Project ID: {project_id}")
        print(f"Overall Rating: {overall_rating}S")

        # Fetch the related objects
        try:
            project = get_object_or_404(Project, id=project_id)
            freelancer = get_object_or_404(CustomUser, id=reviewer_id)
            client = get_object_or_404(CustomUser, id=client_id)
        except Exception as e:
            print(f"Error fetching data: {e}")
            return HttpResponse(status=404, content=f"Error: {e}")

        print(f"Project: {project}")
        print(f"Freelancer: {freelancer}")
        print(f"Client: {client}")

        # Create and save the review
        review = Review(
            reviewer=freelancer,
            reviewee=client,
            project=project,
            overall_rating=overall_rating,
            review_text=review_text
        )
        review.save()

        print("Review saved successfully.")

        if project.freelancer and project.freelancer == freelancer:
            project.freelancer_review_given = True
            project.save()
            print(f"Project updated with freelancer review: {project.freelancer_review_given}")
        else:
            print(f"Freelancer ID mismatch. Expected: {project.freelancer.id}, Found: {freelancer.id}")


        return redirect('freelancer:freelancer_view')

    return HttpResponse(status=405, content="Method Not Allowed")












from client.models import ChatRoom 

@login_required
@nocache
def chat_view(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission: 
        
        # Fetch chat rooms associated with the freelancer
        chat_rooms = ChatRoom.objects.filter(participants=freelancer.user_id).prefetch_related('participants')

        # Debugging: Check if chat_rooms are fetched
        print(f"Chat Rooms: {chat_rooms}")  # Debugging line

        # Fetch client details for each chat room
        clients = []
        for chat in chat_rooms:
            # Exclude the freelancer from the participants to get only clients
            for participant in chat.participants.exclude(id=freelancer.user_id):
                client_profile = ClientProfile.objects.get(user=participant)
                client_register = Register.objects.get(user_id=participant.id)
                clients.append({
                    'user': participant,
                    'profile': client_profile,
                    'register': client_register,
                    'chat_room_id': chat.id
                })  # Store user, profile, and register details
        
        # Debugging: Check if clients are being populated
        print(f"Clients: {clients}")  # Debugging line
        
        return render(request, 'freelancer/chat.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'chat_rooms': chat_rooms,
            'clients': clients,  
            # Ensure clients are passed to the template
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
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

        # Fetch messages for the given chat room
        messages = Message.objects.filter(chat_room_id=chat_room_id).order_by('timestamp')

        # Prepare messages for response
        messages_list = []
        for message in messages:
            print(f"Message ID: {message.id}, Content: {message.content}, Image: {message.image}, File: {message.file}")  # Debugging line

            msg_data = {
                'content': message.content if message.content else '',  # Ensure content is not None
                'type': 'sent' if message.sender == request.user else 'received',
                'image': message.image.url if message.image and hasattr(message.image, 'url') else None,  # Check if image exists
                'file': message.file.url if message.file and hasattr(message.file, 'url') else None,    # Check if file exists
            }
            messages_list.append(msg_data)

        print(messages_list)  # Debugging line to check the messages list

        return JsonResponse({'success': True, 'messages': messages_list})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})




from django.core.files.storage import default_storage
from client.models import Message  # Import your Message model

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
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    
    if profile1.permission:
        projects = Project.objects.filter(freelancer=profile1)
        client_ids = projects.values_list('user', flat=True).distinct()
        clients = CustomUser.objects.filter(id__in=client_ids)
        client_registers = Register.objects.filter(user__in=clients)
        if request.method == 'POST':
            complaint_type = request.POST.get('complaint_type')
            subject = request.POST.get('subject')
            complainee_id = request.POST.get('client')  # This may be empty if not applicable
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
                    complainee = CustomUser.objects.get(id=complainee_id)
                    if complainee_id:
                        complaint.complainee = complainee
                    else:
                        messages.error(request, 'Invalid complainee ID.')
                
                complaint.save()
                
                # Notify the complainee about the complaint
                if complaint_type in ['Freelancer', 'Client']:
                    complainee = CustomUser.objects.get(id=complainee_id)
                    if complainee_id:
                        complaint.complainee = complainee
                        Notification.objects.create(
                            user=complainee,
                            message=f"A complaint has been filed against you. Please respond within 30 days.",
                            is_read=False
                        )
                    else:
                        messages.error(request, 'Invalid complainee ID.')
                
                messages.success(request, 'Complaint submitted successfully.')
                return redirect('client:client_view') 
        return render(request, 'freelancer/AddComplaint.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'freelancer_registers': Register.objects.filter(user=profile1),
            'client_registers': client_registers,  # Pass client details to the template
        })
    else:
        return render(request, 'freelance/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })
        
def template_list(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission==True:
        templates = Template.objects.all()  # Fetch all templates from the database
        return render(request, 'freelancer/PortfolioTemplates.html', {'templates': templates,'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
        
    
    
from .utils import extract_text_from_pdf, parse_achievements,process_resume_text, parse_skills,parse_projects,parse_contact,parse_education,parse_experience,parse_internships,calculate_accuracy

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PyPDF2 import PdfReader
import io
from django.template import loader
from django.template import loader
from django.conf import settings
from django.template import loader
from io import BytesIO
from django.conf import settings
import os
from django.core.files.base import ContentFile

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from django.core.files.base import ContentFile

def process_resume(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    user = request.user
    user_details = Register.objects.get(user=user)
    name = f"{user_details.first_name} {user_details.last_name}"
    bio = user_details.bio_description
    profile_picture = user_details.profile_picture

    if not document.resume_file:
        return HttpResponse("Resume file not found", status=404)

    try:
        file_path = document.resume_file.path  # Get the file path
        with open(file_path, 'rb') as pdf_file:
            pdf_stream = BytesIO(pdf_file.read())
            resume_text = extract_text_from_pdf(pdf_stream)
    except Exception as e:
        return HttpResponse(f"Error processing PDF: {e}", status=500)

    # Extract resume information
    extracted_info = process_resume_text(resume_text)

    # Parse sub-details (experience, education, internships, skills, etc.)
    extracted_info['Experience'] = parse_experience(extracted_info.get('Experience', ''))
    extracted_info['Education'] = parse_education(extracted_info.get('Education', ''))
    extracted_info['Internships'] = parse_internships(extracted_info.get('Internships', ''))
    extracted_info['Projects'] = parse_projects(extracted_info.get('Projects', ''))
    extracted_info['Technical'] = parse_skills(extracted_info.get('Technical Skills', ''))
    extracted_info['Personal'] = parse_skills(extracted_info.get('Personal Skills', ''))
    extracted_info['Contact'] = parse_contact(extracted_info.get('Contact', ''))
    extracted_info['Achievements'] = parse_achievements(extracted_info.get('Achievements', ''))

    ground_truth = {
        "Experience": [],  # No experience entries in the extracted info
        "Education": [
            {
                "degree": "• MCA (Integrated) | 2020 - 2025",
                "institution": "Amal Jyothi College of Engineering (Autonomous)",
                "university_board": "A P J Abdul Kalam Technological University",
                "description": "8.79 CGPA"
            },
            {
                "degree": "• Standard XII | 2018 - 2020",
                "institution": "Govt. Higher Secondary School, Edakkunnam",
                "university_board": "Board Of Higher Secondary Examination Kerala, India",
                "description": "84 percentage"
            },
            {
                "degree": "• Standard X (SSLC) | 2018",
                "institution": "Assumption High School, Palambra",
                "university_board": "Board of Public Examination, Kerala, India",
                "description": "97 percentage"
            }
        ],
        "Technical Skills": [
            "MS Office (Word, Excel, Power Point)",
            "HTML",
            "CSS",
            "JavaScript",
            "PHP",
            "Django",
            "Python",
            "C",
            "C++",
            "Java",
            "Laravel",
            "R",
            "SQL",
            "NoSQL"
        ],
        "Personal Skills": [
            "Quick learner",
            "Adaptive",
            "Punctual",
            "Communication Skills",
            "Leadership",
            "Time Management"
        ],
        "Projects": [
            "\u2022 Jingle Joy | Online platform for buying Christmas related products with add to cart\nfunctionality.\nDjango | SQLite | HTML | CSS | jQuery | Bootstrap",
            "Tuneify | Platform for music streaming, liked songs, playlist creation, and\npersonalized genre/language recommendations.\nPHP | MongoDB | HTML | CSS | jQuery | Bootstrap",
            "Quillify | Website for buying journal supplies with add to cart functionality.\nLaravel | MySQL | HTML | CSS | jQuery | Bootstrap",
            "Bakers Delight | Online platform for bakery shop management system with\npayment integration and ordering.\nPHP | MySQL | HTML | CSS | JS | AJAX | jQuery"
        ],
        "Certifications": [
            "\u2022 Full Stack Web Development with Flask | LinkedIn learning | June 2024",
            "\u2022 Django Essentials | LinkedIn learning | May 2024",
            "\u2022 Cloud Computing | NPTEL | October 2023",
            "\u2022 AWS Academy Cloud Foundations | AWS Academy | September 2021"
        ],
        "Achievements": [
            "\u2022\nParticipated in old-school hackathon\n| hosted by Init() IT Association at\nAmal Jyothi College of Engineering |\nFebruary 2024",
            "\u2022\nParticipated in Code girls 2021 | An\nindustrial exposure program for girl\nstudents organized by women cell,\nDepartment\nof\nComputer\nApplications, Amal Jyothi College of\nEngineering | May 2021",
            "\u2022\nManager honor for Semester 1 to 2\nand 5 to 7",
            "\u2022\nPrinciple honor for semester 3 and 4"
        ],
    
        "Internships": [
            {
                "details": "Web Development | 1 month | January 2023\nExposys Data Labs, Bengaluru"
            },
            {
                "details": "App Development in Flutter | 1 month | July 2024\nNezuware, Noida, Uttar Pradesh"
            }
        ],
        "Contact": {
            "email": "varshamariyashaji2002@gmail.com",
            "phone": "+91 8078107428",
            "linkedin": "",
            "address": "Perumpalliyazhathu(H), Koovappally P.O, Kanjirappally, Kerala, India, 686518"
        }
    }

    accuracy = calculate_accuracy(extracted_info, ground_truth)
    print(accuracy)
    context = {
        'resume_data': extracted_info,
        'portfolio': document,
        'name': name,
        'bio': bio,
        'picture': profile_picture,
        'user': user,
        'user_details': user_details,
        'doc_id': document_id,
    }

    selected_template_path = os.path.join(settings.MEDIA_ROOT, document.template.file.name)

    try:
        template = loader.get_template(selected_template_path)
        rendered_html = template.render(context, request)

        html_file_name = f'resume_{document_id}.html'
        html_file_path = os.path.join(settings.MEDIA_ROOT, 'portfolios', html_file_name)
        os.makedirs(os.path.dirname(html_file_path), exist_ok=True)

        with open(html_file_path, 'w', encoding='utf-8') as html_file:
            html_file.write(rendered_html)

        # Set up Selenium with headless Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

        # Load the HTML file in the browser
        driver.get(f'file://{html_file_path}')
        driver.set_window_size(1024, 768)  

        # Capture the screenshot
        img_file_name = f'resume_{document_id}.png'
        img_file_path = os.path.join(settings.MEDIA_ROOT, 'portfolios', img_file_name)
        driver.save_screenshot(img_file_path)
        driver.quit()

        # Save the image to the cover_image field
        with open(img_file_path, 'rb') as img_file:
            document.cover_image.save(img_file_name, ContentFile(img_file.read()))

        document.portfolio_file = f'portfolios/{html_file_name}'
        document.save()

        return HttpResponse(rendered_html, content_type='text/html') 
    except Exception as e:
        return HttpResponse(f"Error loading template: {e}", status=500)



def upload_resume(request):
    if request.method == 'POST':
        if 'resume' in request.FILES and 'template_id' in request.POST:
            resume_file = request.FILES['resume']
            template_id = request.POST['template_id']

            # Ensure the template exists
            try:
                template = Template.objects.get(id=template_id)
            except Template.DoesNotExist:
                return HttpResponse("Template not found", status=404)

            # Save the resume file
            document = Document.objects.create(
                user=request.user,
                resume_file=resume_file,
                template=template
            )

            # Redirect to a new URL to process the resume
            return redirect('freelancer:process_resume', document_id=document.id)

    return redirect("freelancer:template_list")

from django.http import FileResponse, HttpResponse
def download_resume(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Check if the resume HTML file exists
    if document.portfolio_file:
        file_path = os.path.join(settings.MEDIA_ROOT, document.portfolio_file.name)
        if os.path.exists(file_path):
            # Return the file as a response for download
            response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=os.path.basename(file_path))
            return response
        else:
            return HttpResponse("File not found", status=404)
    else:
        return HttpResponse("Resume HTML file not found", status=404)
    
    
    

def my_portfolios(request):
    
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    freelancer=FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        portfolios = Document.objects.filter(user=uid)  # Fetch all documents created by the user
        return render(request,'freelancer/MyPortfolios.html', {'portfolios': portfolios,'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
    else:
        return render(request, 'freelancer/PermissionDenied.html',{'profile1':profile1,'profile2':profile2,'freelancer':freelancer})
    
    

def preview_template(request, template_id):
    template = get_object_or_404(Template, id=template_id)
    
    # Update the path to fetch from media/templates folder
    template_path = os.path.join(settings.MEDIA_ROOT, template.file.name)

    if os.path.exists(template_path):
        # Default context values
        context = {
            'name': 'John Doe',
            'doc_id': None,
            'resume_data': {
                'Technical': ['HTML', 'CSS', 'JavaScript', 'Bootstrap'],
                'Education': [
                    {
                        'degree': 'Bachelor of Science in Computer Science',
                        'institution': 'XYZ University',
                        'university_board': 'XYZ Board',
                        'description': 'Graduated with honors, focusing on web development and software engineering.'
                    },
                    {
                        'degree': 'Certification in Web Development',
                        'institution': 'ABC Academy',
                        'university_board': '',
                        'description': 'Completed a comprehensive web development course.'
                    }
                ],
                'Experience': [
                    {
                        'job_title': 'Frontend Developer',
                        'company_name': 'ABC Corp',
                        'start_date': 'July 2022',
                        'end_date': 'Present',
                        'description': 'Developing and maintaining the front end of the company website.'
                    },
                    {
                        'job_title': 'Intern',
                        'company_name': 'DEF Tech',
                        'start_date': 'Jan 2022',
                        'end_date': 'June 2022',
                        'description': 'Assisted in the development of web applications.'
                    }
                ],
                'Projects': [
                    'Website design for a small business with a focus on user experience.',
                    'E-commerce platform with secure payment integration and responsive design.',
                    'Mobile app development for a social networking platform.'
                ],
                'Contact': {
                    'address': 'New York, USA',
                    'email': 'johndoe@example.com',
                    'phone': '+123 456 7890',
                    'linkedin': 'linkedin.com/in/johndoe'
                },
                 'Achievements': [
                    'Awarded Employee of the Month at ABC Corp for outstanding performance.',
                    'Completed a marathon in under 4 hours.',
                    'Volunteered at a local animal shelter for over 100 hours.'
                ]
            },
            'picture1': 'https://i.postimg.cc/fRyHvvBm/top-view-workspace-with-copy-space-laptop.jpg',
            'bio': "I'm a passionate web developer with experience in building modern, responsive websites and web applications. I have a strong understanding of HTML, CSS, JavaScript, and frameworks like Bootstrap."
        }

        # Render the template using the full path
        return render(request, template_path, context)
    else:
        return HttpResponse("File not found", status=404)
    
    


       
@login_required
def view_complaints(request):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    freelancer = get_object_or_404(FreelancerProfile, user_id=request.user.id)
    
    if profile1.permission:
        complaints = Complaint.objects.filter(user=profile1)
        return render(request, 'freelancer/Complaints.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'complaints': complaints,
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })
        
        
   
@login_required
def view_complaints_recieved(request):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    profile1 = get_object_or_404(CustomUser, id=request.user.id)
    profile2 = get_object_or_404(Register, user_id=request.user.id)
    freelancer = get_object_or_404(FreelancerProfile, user_id=request.user.id)
    
    if profile1.permission:
        complaints = Complaint.objects.filter(complainee=profile1)
        return render(request, 'freelancer/RecievedComplaints.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'complaints': complaints,
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })


def update_solution(request):
    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        solution = request.POST.get('solution')
        
        # Update the complaint's solution
        complaint = Complaint.objects.get(id=complaint_id)
        complaint.resolution = solution
        complaint.resolution_status = 'Pending'  # Set resolution status to Pending
        complaint.save()
        
        # Notify the person who filed the complaint
        Notification.objects.create(
            user=complaint.user,  # Assuming 'user' is the person who filed the complaint
            message=f"Your complaint has been updated. Resolution: {solution}",
            is_read=False
        )
        
        return redirect("freelancer:view_complaints_recieved")
    return redirect("freelancer:view_complaints_recieved")



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
                complaint.status = 'Resolved'
                
                # Notify the user that the complaint is resolved
                Notification.objects.create(
                    user=complaint.complainee,  # Notify the accused
                    message=f"Your complaint has been resolved satisfactorily.",
                    is_read=False
                )
                
            elif satisfaction_status == 'Unsatisfactory':
                complaint.resolution_status = "Unsatisfactory"
                complaint.status = 'Pending'
                
                # Notify the user that the solution is unsatisfactory
                Notification.objects.create(
                    user=complaint.complainee,  # Notify the accused
                    message=f"Your complaint resolution is unsatisfactory.",
                    is_read=False
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
@nocache
def payments(request):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission:
        # Get all refunds for projects where this user is the freelancer
        refunds = RefundPayment.objects.filter(project__freelancer=request.user).select_related('project', 'project__user')
        
        refund_details = []

        for refund in refunds:
            project = refund.project
            client_profile = ClientProfile.objects.get(user=project.user)
            client_register = Register.objects.get(user=project.user)

            if client_profile.client_type == 'Individual':
                client_name = f"{client_register.first_name} {client_register.last_name}"
            else:
                client_name = client_profile.company_name

            refund_details.append({
                'project_name': project.title,
                'client_name': client_name,
                'amount': refund.amount,
                'paid_date': refund.payment_date,
                'status': refund.is_paid,
                'id': refund.id
            })

        return render(request, 'freelancer/dues.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'refund_details': refund_details,
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })
    
    

from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.shortcuts import get_object_or_404
from client.models import FreelanceContract, PaymentInstallment
from datetime import date

@login_required
@nocache
def download_invoice(request, refund_id):
    # Fetch the refund using the refund_id
    refund = get_object_or_404(RefundPayment, id=refund_id)
    
    project = refund.project
    freelancer = project.freelancer
    client = project.user
    today = date.today()

    # Get freelancer name
    freelancer_register = Register.objects.get(user=freelancer)
    freelancer_name = f"{freelancer_register.first_name} {freelancer_register.last_name}"

    # Get client name
    client_profile = ClientProfile.objects.get(user=client)
    if client_profile.client_type == 'Individual':
        client_register = Register.objects.get(user=client)
        client_name = f"{client_register.first_name} {client_register.last_name}"
    else:
        client_name = client_profile.company_name

    context = {
        'project': project,
        'refund_amount': refund.amount,
        'compensation_amount': refund.compensation_amount,
        'total_amount': refund.amount + refund.compensation_amount,
        'today': today,
        'client_name': client_name,
        'freelancer_name': freelancer_name
    }

    return render(request, 'freelancer/InvoiceDownload.html', context)


from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
import logging  # Add this import

logger = logging.getLogger(__name__)

from django.core.files.base import ContentFile
import os

def edit_portfolio(request, portfolio_id):
    portfolio = get_object_or_404(Document, id=portfolio_id, user=request.user)
    
    if request.method == 'POST':
        try:
            new_content = request.POST.get('content')
            
            # Create a new ContentFile with the updated content
            content_file = ContentFile(new_content.encode('utf-8'))
            
            # Get the original filename
            original_filename = os.path.basename(portfolio.portfolio_file.name)
            
            # Save the new content to the portfolio_file field
            portfolio.portfolio_file.save(original_filename, content_file, save=False)
            
            # Save the portfolio object
            portfolio.save()
            
            messages.success(request, 'Portfolio template updated successfully!')
            return redirect('freelancer:my_portfolios')
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {str(e)}")
            messages.error(request, f'Error updating template: {str(e)}')
            return redirect('freelancer:edit_portfolio', portfolio_id=portfolio_id)
    
    # GET request handling
    try:
        content = portfolio.portfolio_file.read().decode('utf-8')
    except Exception as e:
        content = ''
        messages.error(request, f'Error reading template: {str(e)}')
    
    return render(request, 'freelancer/edit_portfolio.html', {
        'portfolio': portfolio,
        'content': content
    })