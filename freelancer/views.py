from datetime import datetime as dt, date as dt_date, timedelta
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

from freelancer.models import FreelancerProfile, Proposal, ProposalFile, Todo,Document,SalaryPayment
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
from django.urls import reverse  # Add this import

from pytrends.request import TrendReq
import pandas as pd
import time

from django.http import JsonResponse
from django.core.mail import EmailMessage  # Add this line
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
import json

import warnings

# Suppress specific FutureWarnings
warnings.simplefilter(action='ignore', category=FutureWarning)
from datetime import datetime as dt, date as dt_date, timedelta

import pandas as pd
import os

# Load the standardized skills DataFrame, skipping bad lines and without a header
try:
    standardized_skills_df = pd.read_csv(
        os.path.join(os.path.dirname(__file__), 'skills.csv'),
        header=None,  # Specify that there is no header
        on_bad_lines='skip'  # This will skip lines with too many fields
    )
    standardized_skills_df.columns = ['skill']  # Assign a column name
except Exception as e:
    print(f"Error reading skills.csv: {e}")

# Now you can access the 'skill' column
standardized_skills = set(standardized_skills_df['skill'].str.strip())  # Store for quick lookup

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

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
    
    # Calculate monthly earnings
    monthly_earnings_data = []

    # Get all paid payment installments for individual projects
    payment_installments = PaymentInstallment.objects.filter(
        status='paid',
        paid_at__isnull=False,
        contract__project__freelancer=logged_user
    )

    print("\n=== Individual Project Earnings ===")
    for installment in payment_installments:
        amount = float(installment.amount)
        paid_date = installment.paid_at.strftime('%Y-%m-%d')
        print(f"Date: {paid_date} | Amount: ${amount:.2f} | Project: {installment.contract.project.title}")
        
        # Convert to datetime if it's a date
        month_date = installment.paid_at
        if isinstance(month_date, dt_date) and not isinstance(month_date, dt):
            month_date = dt.combine(month_date, dt.min.time())
        monthly_earnings_data.append({
            'month': month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            'amount': amount
        })

    # Get all paid salary payments for team projects
    salary_payments = SalaryPayment.objects.filter(
        status='completed',  
        team_member__user=logged_user
    )

    print("\n=== Team Project Earnings ===")
    for salary in salary_payments:
        amount = float(salary.amount_paid)
        date = salary.payment_date.strftime('%Y-%m-%d')
        print(f"Date: {date} | Amount: ${amount:.2f} | Team: {salary.team_member.team.name}")
        # Convert to datetime if it's a date
        month_date = salary.payment_date
        if isinstance(month_date, dt_date) and not isinstance(month_date, dt):
            month_date = dt.combine(month_date, dt.min.time())
        monthly_earnings_data.append({
            'month': month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            'amount': amount
        })

    # Aggregate earnings by month
    earnings_by_month = {}
    for entry in monthly_earnings_data:
        month = entry['month']
        earnings_by_month[month] = earnings_by_month.get(month, 0) + float(entry['amount'])

    print("\n=== Monthly Totals ===")
    for month, total in sorted(earnings_by_month.items()):
        print(f"Month: {month.strftime('%B %Y')} | Total: ${total:.2f}")

    # Sort months and prepare final data
    sorted_months = sorted(earnings_by_month.keys())
    earnings_data = {
        'months': [month.strftime('%B') for month in sorted_months],
        'earnings': [earnings_by_month[month] for month in sorted_months]
    }

    print("\n=== Final Chart Data ===")
    print("Months:", earnings_data['months'])
    print("Earnings:", [f"${amount:.2f}" for amount in earnings_data['earnings']])

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

    # Get freelancer's profile and skills
    try:
        freelancer = FreelancerProfile.objects.get(user_id=uid)
        skills = freelancer.skills.strip('[]').replace("'", "").split(', ') if freelancer.skills else []
        professions = freelancer.professional_title.strip('[]').replace("'", "").split(', ') if freelancer.professional_title else []
        
        # Step 1: Print profession to category mapping
        print("\n=== Step 1: Profession Category Mapping ===")
        profession_category_map = {
            'Web Developer': 'Web Development',
            'Front End Developer': 'Front-End Development',
            'Back End Developer': 'Back-End Development',
            'Full Stack Developer': 'Full-Stack Development',
            'Mobile App Developer': 'Mobile Development',
            'Android Developer': 'Android Development',
            'iOS Developer': 'iOS Development',
            'UI/UX Designer': 'UI/UX Design',
            'Graphic Designer': 'Graphic Design',
            'Logo Designer': 'Logo Design',
            'Poster Designer': 'Poster Design',
            'Software Developer': 'Software Development',
            'Machine Learning Engineer': 'Machine Learning Engineering',
            'Artificial Intelligence Specialist': 'Artificial Intelligence'
        }
        print("Available mappings:", profession_category_map)

        # Step 2: Print relevant categories
        print("\n=== Step 2: Freelancer's Relevant Categories ===")
        print("Freelancer's professions:", professions)
        relevant_categories = [profession_category_map[prof] for prof in professions if prof in profession_category_map]
        print("Mapped categories:", relevant_categories)

        # Step 3: Print submitted proposals
        print("\n=== Step 3: Already Submitted Proposals ===")
        submitted_proposal_project_ids = Proposal.objects.filter(
            freelancer_id=uid
        ).values_list('project_id', flat=True)
        print("Already proposed project IDs:", list(submitted_proposal_project_ids))

        # Step 4: Print available projects
        print("\n=== Step 4: Available Projects ===")
        available_projects = Project.objects.filter(
            Q(freelancer__isnull=True) | Q(team_id__isnull=True),
            project_status='Not Started',
            status='open'
        ).filter(
            Q(category__in=relevant_categories) | 
            Q(required_skills__isnull=False)  # Changed to just check if skills exist
        ).exclude(
            id__in=submitted_proposal_project_ids
        )

        print("Freelancer skills:", skills)
        print("Available projects:")
        filtered_projects = []
        for project in available_projects:
            # Split required skills and convert to lowercase for case-insensitive comparison
            project_skills = [skill.strip().lower() for skill in project.required_skills] if project.required_skills else []
            freelancer_skills = [skill.strip().lower() for skill in skills]
            
            # Check if there's any skill overlap
            matching_skills = set(project_skills) & set(freelancer_skills)
            
            if matching_skills or project.category in relevant_categories:
                filtered_projects.append(project)
                print(f"- {project.title}")
                print(f"  Category: {project.category}")
                print(f"  Required skills: {project.required_skills}")
                print(f"  Matching skills: {matching_skills}")

        # Step 5: Print text documents
        print("\n=== Step 5: Text Documents for Analysis ===")
        project_docs = []
        project_objects = []
        for project in filtered_projects:  # Use filtered_projects instead of available_projects
            project_text = f"{project.title} {project.description} {' '.join(project.required_skills)}".lower()
            print(f"\nProject: {project.title}")
            print(f"Text document: {project_text[:100]}...")  # Print first 100 chars
            project_docs.append(project_text)
            project_objects.append(project)

        recommended_projects = []
        if project_docs:  # Only proceed if there are projects
            # Step 6: Print similarity scores
            print("\n=== Step 6: TF-IDF Analysis ===")
            vectorizer = TfidfVectorizer(stop_words='english')
            freelancer_text = ' '.join(skills).lower()
            print(f"Freelancer document: {freelancer_text}")
            all_docs = [freelancer_text] + project_docs
            
            tfidf_matrix = vectorizer.fit_transform(all_docs)
            cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
            
            print("\nCosine similarities:")
            for project, score in zip(project_objects, cosine_similarities):
                print(f"- {project.title}: {score:.3f}")
            
            # Create list of (project, similarity_score) tuples
            project_scores = list(zip(project_objects, cosine_similarities))
            
            # Sort projects by similarity score
            project_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Step 7: Print final recommendations
            print("\n=== Step 7: Final Recommendations ===")
            for project, score in project_scores[:5]:  # Limit to top 5
                client_profile = ClientProfile.objects.get(user=project.user_id)
                client_register = Register.objects.get(user=project.user_id)
                
                if client_profile.client_type == 'Individual':
                    client_name = f"{client_register.first_name} {client_register.last_name}"
                else:
                    client_name = client_profile.company_name

                # Get client's profile picture
                client_profile_picture = client_register.profile_picture if client_register.profile_picture else None

                # Convert skills to lowercase for case-insensitive comparison
                project_skills = {skill.lower() for skill in project.required_skills}
                freelancer_skills = {skill.lower() for skill in skills}
                
                # Calculate skill matches
                matching_skills = project_skills.intersection(freelancer_skills)
                missing_skills = project_skills - freelancer_skills
                
                if project_skills:
                    match_percentage = len(matching_skills) / len(project_skills) * 100
                else:
                    match_percentage = 0

                # Determine category match
                category_match = project.category in relevant_categories

                # Generate recommendation reasons
                reasons = []
                if matching_skills:
                    reasons.append(f"You have {len(matching_skills)} matching skills: {', '.join(matching_skills)}")
                if category_match:
                    reasons.append(f"Project category ({project.category}) matches your professional expertise")
                if score > 0.3:  # Only include similarity if it's significant
                    reasons.append(f"Project requirements align with your skill set")

                print(f"\nProject: {project.title}")
                print(f"- Skill match: {match_percentage:.1f}%")
                print(f"- Similarity score: {score * 100:.1f}%")
                print(f"- Matching skills: {matching_skills}")
                print(f"- Missing skills: {missing_skills}")

                recommended_projects.append({
                    'project': project,
                    'client_name': client_name,
                    'client_profile_picture': client_profile_picture,  # Add this line
                    'match_percentage': round(match_percentage, 1),
                    'similarity_score': round(score * 100, 1),
                    'matching_skills': list(matching_skills),
                    'missing_skills': list(missing_skills),
                    'reasons': reasons
                })

    except FreelancerProfile.DoesNotExist:
        recommended_projects = []

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
        'recommended_projects': recommended_projects,
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
    'Web Developer','Front End Developer','Back End Developer','Full Stack Developer',
    'Mobile App Developer','Android Developer','iOS Developer','UI/UX Designer','Graphic Designer',
    'Logo Designer','Poster Designer','Machine Learning Engineer','Artificial Intelligence Specialist','Software Developer',
]
    skills = [
    "java", "c++", "python", "eclipse", "visual studio", "html","css", "javascript", "bootstrap", "sass", 
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
        # Only allow marking as completed, ignore attempts to unmark
        if is_completed:
            todo.is_completed = True
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
        'Software Developer': 'Software Development',
        'Machine Learning Engineer': 'Machine Learning Engineering',
        'Artificial Intelligence Specialist': 'Artificial Intelligence'
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
    uid = request.user.id
    
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
        
        # Get owned teams with exactly 5 members
        owned_teams = Team.objects.filter(created_by=profile1)
        complete_teams = []
        
        for team in owned_teams:
            # Count unique users in the team
            member_count = TeamMember.objects.filter(team=team).values('user').distinct().count()
            
            # Only add teams with exactly 5 members
            if member_count == 5:
                complete_teams.append(team)
        
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
            'complete_teams': complete_teams,  # Only teams with exactly 5 members
        }
        return render(request, 'freelancer/SingleProject.html', context)
    else:
        return render(request, 'freelancer/PermissionDenied.html',{
            'profile1':profile1,
            'profile2':profile2,
            'freelancer':freelancer
        })
        
    
    
 
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
def generate_proposal(request, pid):
    
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission == True:
        todos = Todo.objects.filter(user_id=uid)
        project = Project.objects.get(id=pid)
        uid = project.user_id
        client_profile = ClientProfile.objects.get(user_id=uid)
        client_register = Register.objects.get(user_id=uid)
        userprofile = CustomUser.objects.get(id=uid)
        fancy_id = generate_fancy_proposal_id()

        team_id = request.GET.get('team_id')  #
        team_details = None
        
        if team_id:
            team_details = get_object_or_404(Team, id=team_id)
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
                fancy_num=fancy_id,
                team_id=team_details 
            )
            proposal.save()
            return redirect('freelancer:proposal_detail1', prop_id=proposal.id)

        return render(request, 'freelancer/template.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'todos': todos,
            'project': project,
            'client_profile': client_profile,
            'client_register': client_register,
            'userprofile': userprofile,
            'number': fancy_id,
            'team_details': team_details  # Pass team details to the template
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })
         
     
  
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

        team_id = proposal.team_id_id  
        team_details = None
        if team_id:
            team_details = get_object_or_404(Team, id=team_id)  
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
            'userprofile': userprofile,
            'team_details': team_details  # Pass team details to the template
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

        # Get team details if associated with the proposal
        team_id = proposal.team_id_id  
        team_details = None
        if team_id:
            team_details = get_object_or_404(Team, id=team_id)

        return render(request, 'freelancer/single_proposal.html', {
            'proposal': proposal,
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'client_profile': client_profile,
            'client_register': client_register,
            'userprofile': userprofile,
            'team_details': team_details  # Pass team details to the template
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

        # Initialize team_members_data to ensure it is always defined
        team_members_data = []

        if project.freelancer:
            is_project_manager = False  
        else:
            if project.team_id:
                is_project_manager = TeamMember.objects.filter(team_id=project.team_id, user=request.user, role='PROJECT_MANAGER').exists()
                team_members = TeamMember.objects.filter(team=project.team_id).select_related('user')
                for member in team_members:
                    if member.user:
                        team_members_data.append({
                            'username': member.user.username,  # Fetch the username
                            'role': member.role,  # Fetch the role
                            'user_id': member.user.id,  # Pass the user ID
                        })
            else:
                is_project_manager = False 

        
        if client_profile.client_type == 'Individual':
            client_name = f"{client_register.first_name} {client_register.last_name}"
        else:
            client_name = client_profile.company_name
        
        client_profile_picture = client_register.profile_picture if client_register.profile_picture else None
        client_email = client_profile.user.email

        shared_files = SharedFile.objects.filter(repository=repository).values(
            'file', 'uploaded_at', 'uploaded_by', 'description'
        )
        shared_urls = SharedURL.objects.filter(repository=repository).values(
            'url', 'shared_at', 'shared_by', 'description'
        )
        proposals = Proposal.objects.filter(project=project, status='Accepted')
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
        tasks = Task.objects.filter(project=project)
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
            'notes': notes,
            'tasks': tasks,
            'client_name': client_name,
            'client_profile_picture': client_profile_picture,
            'client_email': client_email,
            'proposals': proposals,
            'contracts': contracts,
            'is_project_manager': is_project_manager,
            'project': project,
            'cancellation_details': cancellation_details,
            'team_members': team_members_data,
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
        try:
            project = get_object_or_404(Project, id=project_id)
            freelancer = get_object_or_404(CustomUser, id=reviewer_id)
            client = get_object_or_404(CustomUser, id=client_id)
        except Exception as e:
            return HttpResponse(status=404, content=f"Error: {e}")

      
        review = Review(
            reviewer=freelancer,
            reviewee=client,
            project=project,
            overall_rating=overall_rating,
            review_text=review_text
        )
        review.save()

        if project.freelancer and project.freelancer == freelancer:
            project.freelancer_review_given = True
            project.save()
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
        
        chat_rooms = ChatRoom.objects.filter(participants=freelancer.user_id).prefetch_related('participants')

        clients = []
        group_chats = []  
        for chat in chat_rooms:
            if chat.chat_type == 'private':  
                for participant in chat.participants.all().exclude(id=freelancer.user_id):  
                    try:
                        client_profile = ClientProfile.objects.get(user=participant)
                        client_register = Register.objects.get(user_id=participant.id)
                        clients.append({
                            'user': participant,
                            'profile': client_profile,
                            'register': client_register,
                            'chat_room_id': chat.id
                        })
                    except ClientProfile.DoesNotExist:
                        continue 
            elif chat.chat_type == 'group':  
                members = []
                for participant in chat.participants.all():  
                    members.append({
                        'user': participant,
                        'user_id': participant.id,
                        'name': f"{participant.register.first_name} {participant.register.last_name}",
                        'profile_picture': participant.register.profile_picture.url if participant.register.profile_picture else None
                    })
                group_chats.append({
                    'chat_room_id': chat.id,
                    'chat_name': chat.name,  
                    'chat_type': chat.chat_type,
                    'members': members
                })
                
                clients.append({
                    'chat_room_id': chat.id,
                    'chat_name': chat.name,  
                    'chat_type': chat.chat_type,
                    'members': members
                })

        
        return render(request, 'freelancer/chat.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'chat_rooms': chat_rooms,
            'clients': clients,  
            'group_chats': group_chats,  
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

@login_required
@nocache
def my_teams(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)

    if profile1.permission:
        owned_teams = Team.objects.filter(created_by=request.user)
        
        return render(request, 'freelancer/my_teams.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
            'owned_teams': owned_teams,
        })
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        })

from django.contrib import messages
from django.shortcuts import redirect
from .models import Team,TeamMember
import uuid

def create_team(request):
    if request.method == 'POST':
        team_name = request.POST.get('team_name')
        try:
            # Generate join code
            while True:
                join_code = str(uuid.uuid4())[:8]
                # Check if this code already exists
                if not Team.objects.filter(join_code=join_code).exists():
                    break
            
            # Create team with the generated join code
            team = Team.objects.create(
                name=team_name,
                created_by=request.user,
                join_code=join_code
            )

            # Add the team creator as a project manager
            TeamMember.objects.create(
                team=team,
                user=request.user,
                role='PROJECT_MANAGER'
            )

            messages.success(request, f'Team "{team_name}" created successfully! Join code: {team.join_code}')
        except Exception as e:
            messages.error(request, f'Failed to create team: {str(e)}')
            
        
    return redirect('freelancer:my_teams')


def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        team_name = request.POST.get('team_name')  # Get the team name from the POST data
        if team_name:  # Validate that the team name is provided
            team.name = team_name  # Update the team name
            team.save()  # Save the changes
            return redirect('freelancer:my_teams')  # Redirect to the team management page
    
    return redirect('freelancer:my_teams')


def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        team.delete()
        return redirect('freelancer:my_teams')  # Redirect to the team management page
    return redirect('freelancer:my_teams')

from django.shortcuts import render, get_object_or_404
from .models import Team 

def manage_team(request, team_id):
    if not request.user.is_authenticated or request.user.role != 'freelancer':
        return redirect('login')

    team = get_object_or_404(Team, id=team_id)
    team_projects = Project.objects.filter(team=team)
    client_details = []
    salary_paid_all_members = False  # Initialize the variable here
    payment_received = False  # Initialize payment_received variable

    for project in team_projects:
        client_profile = ClientProfile.objects.get(user=project.user)
        client_register = None

        if client_profile.client_type == 'Individual':
            client_register = Register.objects.get(user=project.user)
            client_name = f"{client_register.first_name} {client_register.last_name}"
        else:
            client_register = Register.objects.get(user=project.user)
            client_name = client_profile.company_name

        client_details.append({
            'client_name': client_name,
            'client_profile_picture': client_register.profile_picture.url if client_register.profile_picture else None,
            'client_email': client_profile.user.email
        })

        try:
            contract = FreelanceContract.objects.get(project_id=project.id)
            installments = PaymentInstallment.objects.filter(contract=contract)
            payment_received = all(installment.status == 'paid' for installment in installments)

            team_members = TeamMember.objects.filter(team=team)
            salaries_paid = SalaryPayment.objects.filter(
                project_id=project.id,
                status='completed'
            ).values_list('team_member_id', flat=True)

            team_member_ids = team_members.values_list('id', flat=True)
            salary_paid_all_members = len(salaries_paid) == len(team_member_ids)
        except FreelanceContract.DoesNotExist:
            payment_received = False
            salary_paid_all_members = False
    
    team_members = TeamMember.objects.filter(team=team).select_related(
        'user',
        'user__register',
        'user__freelancerprofile'
    )

    # Fetch all available freelancers excluding the current user
    available_freelancers = CustomUser.objects.filter(role='freelancer').exclude(id=request.user.id).select_related('register', 'freelancerprofile')

    # Define required roles
    REQUIRED_ROLES = ['PROJECT_MANAGER', 'DESIGNER', 'FRONTEND_DEV', 'BACKEND_DEV', 'QA_TESTER']

    # Check if all required roles exist and are assigned
    all_roles_assigned = all(
        TeamMember.objects.filter(
            team=team,
            role=role,
            user__isnull=False
        ).exists()
        for role in REQUIRED_ROLES
    )

    # Check if salary percentages are set for all roles
    salary_percentages_set = all(
        TeamMember.objects.filter(
            team=team, 
            role=role,
            salary_percentage__gt=0  # Changed to only check if greater than 0
        ).exists()
        for role in ['PROJECT_MANAGER', 'DESIGNER', 'FRONTEND_DEV', 'BACKEND_DEV', 'QA_TESTER']
    )

    print("Salary percentages check:", salary_percentages_set)  # Debug print
    print("Individual role checks:")  # Debug print
    for role in ['PROJECT_MANAGER', 'DESIGNER', 'FRONTEND_DEV', 'BACKEND_DEV', 'QA_TESTER']:
        has_salary = TeamMember.objects.filter(
            team=team, 
            role=role,
            salary_percentage__gt=0
        ).exists()
        print(f"{role}: {has_salary}")  # Debug print

    # Format team member data
    team_members_data = []
    for member in team_members:
        if member.user:
            profile = getattr(member.user, 'freelancerprofile', None)
            titles = []
            if profile and profile.professional_title:
                titles = profile.professional_title.strip('[]').replace("'", "").split(', ')
            
            team_members_data.append({
                'id': member.user.id,
                'name': f"{member.user.register.first_name} {member.user.register.last_name}",
                'profession': ', '.join(titles) if titles else "No profession listed",
                'role': member.role,
                'join_date': member.joined_at,
                'status': member.is_active,
                'email': member.user.email,
                'profile_picture': member.user.register.profile_picture.url if member.user.register.profile_picture else None,
                'salary_percentage': member.salary_percentage or 0  # Add this line
            })

    # Format available freelancers data with professions
    available_freelancers_data = []
    for freelancer in available_freelancers:
        profile = getattr(freelancer, 'freelancerprofile', None)
        titles = []
        if profile and profile.professional_title:
            titles = profile.professional_title.strip('[]').replace("'", "").split(', ')
        
        available_freelancers_data.append({
            'id': freelancer.id,
            'name': f"{freelancer.register.first_name} {freelancer.register.last_name}",
            'profession': ', '.join(titles) if titles else "No profession listed",
            'email': freelancer.email,
            'profile_picture': freelancer.register.profile_picture.url if freelancer.register.profile_picture else None
        })

    current_percentages = {
        member.role: member.salary_percentage 
        for member in TeamMember.objects.filter(team=team)
    }

    project_details = []
    for project in team_projects:
        repository = Repository.objects.filter(project=project).first()  # Get the repository associated with the project
        repository_id = repository.id if repository else None  # Get repository ID if it exists
        project_details.append({
            'project': project,
            'repository_id': repository_id
        })
    # Fetch invitations sent by the user for this team
    invitations_sent = TeamInvitation.objects.filter(invited_by=request.user, team=team)

    # Prepare invitations data
    invitations_data = []
    for invitation in invitations_sent:
        expired = timezone.now() > invitation.expires_at  # Check if the token has expired
        invitations_data.append({
            'email': invitation.email,
            'role': invitation.role,
            'status': invitation.status,
            'invitation_date': invitation.created_at,  # Assuming you have a created_at field
            'expired': expired,
            'invitation_id': invitation.id  # Pass the expired status
        })

    # Calculate total allocated salary percentage
    total_allocated_percentage = sum(
        member.get('salary_percentage', 0) 
        for member in team_members_data
    )

    context = {
        'team': team,
        'team_members': team_members_data,
        'current_percentages': current_percentages,
        'total_allocated_percentage': total_allocated_percentage,
        'is_manager': TeamMember.objects.filter(
            team=team,
            user=request.user,
            role='PROJECT_MANAGER'
        ).exists(),
        'all_roles_assigned': all_roles_assigned,
        'unassigned_roles': REQUIRED_ROLES,  
        'available_freelancers': available_freelancers_data,  
        'invitations': invitations_data,
        'team_projects': team_projects,  # Include team projects in the context
        'client_details': client_details,
        'project_details': project_details,
        'salary_paid_all_members': salary_paid_all_members,
        'payment_received': payment_received,  # Pass client details to the template
        'salary_percentages_set': salary_percentages_set,
    }

    return render(request, 'freelancer/manage_team.html', context)



from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
import uuid
from .models import TeamInvitation, Team, TeamMember, Project 
from client.models import FreelanceContract, PaymentInstallment
from django.core.signing import Signer, BadSignature
import secrets

def send_team_invitation(request):
    if request.method == 'POST':
        freelancer_id = request.POST.get('freelancer')
        role = request.POST.get('role')
        team_id = request.POST.get('team_id')
        team = Team.objects.get(id=team_id)

        # Check if the selected freelancer is "other"
        if freelancer_id == "other":
            email = request.POST.get('email')  # Get the email from the input
            if not email:
                messages.error(request, 'Email is required for non-registered members.')
                return redirect('freelancer:manage_team', team_id=team_id)
        else:
            freelancer = get_object_or_404(CustomUser, id=freelancer_id)
            email = freelancer.email

        # Generate a secure token
        token = secrets.token_urlsafe(32)
        signer = Signer()
        signed_token = signer.sign(token)

        # Save invitation to database with the signed token
        invitation = TeamInvitation.objects.create(
            team=team,
            email=email,
            role=role,
            invited_by=request.user,
            token=signed_token,
            expires_at=timezone.now() + timezone.timedelta(days=15)  # Set expiration to 15 days from now
        )

        # Generate invitation link using the secure token
        invite_link = f"http://127.0.0.1:8000/freelancer/join_team/{token}/"
        decline_link = f"http://127.0.0.1:8000/freelancer/decline_invitation/{invitation.id}/"  # Link to decline invitation

        # Send the email
        send_mail(
            subject=f'Invitation to join {team.name}',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=render_to_string('freelancer/team_invitation.html', {
                'team': team,
                'invitation': invitation,
                'invite_link': invite_link,
                'decline_link': decline_link,  # Pass the decline link
                'join_code': team.join_code
            })
        )

        messages.success(request, f'Invitation sent to {email}')
        return redirect('freelancer:manage_team', team_id=team_id)

    return redirect('freelancer:manage_team', team_id=team_id)

@login_required
def join_team(request, token):
    if request.method == 'GET':
        if not token:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid invitation link'
            })
            
        signer = Signer()
        
        try:
            # Correctly filter invitations by status
            invitations = TeamInvitation.objects.filter(status='pending')  # Specify the status here
            invitation = None
            
            for inv in invitations:
                try:
                    # Verify the token signature
                    original_token = signer.unsign(inv.token)
                    if original_token == token:
                        invitation = inv
                        break
                except BadSignature:
                    continue
            
            if not invitation:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid or expired invitation'
                })
                
            # Check if the user exists using the email from the invitation
            email = invitation.email
            
            if not CustomUser.objects.filter(email=email).exists():
                return redirect('register')  
            return render(request, 'freelancer/join_team.html', {
                'team': invitation.team,
                'invitation': invitation
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error verifying invitation: {str(e)}'
            })
            
    elif request.method == 'POST':
        return handle_join_team_post(request)

def handle_join_team_post(request):
    join_code = request.POST.get('join_code')
    team_id = request.POST.get('team_id')
    invitation_id = request.POST.get('invitation_id')
    
    if not all([join_code, team_id, invitation_id]):
        return JsonResponse({
            'status': 'error',
            'message': 'Missing required information'
        })
        
    try:
        team = Team.objects.get(id=team_id)
        invitation = TeamInvitation.objects.get(id=invitation_id, status='pending')
        
        if join_code != team.join_code:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid join code'
            })
        if TeamMember.objects.filter(team=team, user=request.user).exists():
            return JsonResponse({
                'status': 'warning',
                'message': 'You are already a member of this team'
            })
        
        TeamMember.objects.filter(
            team=team,
            role=invitation.role
        ).update(user=request.user,joined_at=timezone.now())  
        
        TeamInvitation.objects.filter(
            team=team,
            role=invitation.role,
            status='pending'
        ).exclude(id=invitation.id).update(status='rejected')  
        
        invitation.status = 'accepted'  
        invitation.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully joined the team',
            'redirect_url': reverse('freelancer:freelancer_view')  
        })
        
    except (Team.DoesNotExist, TeamInvitation.DoesNotExist):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid team or invitation'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error joining team: {str(e)}'
        })

from django.http import JsonResponse
from .models import Team  

def check_team_name(request):
    if request.method == 'GET':
        team_name = request.GET.get('team_name', '')
        exists = Team.objects.filter(name=team_name).exists()
        return JsonResponse({'exists': exists})

from django.utils import timezone
from django.core.mail import send_mail
import secrets

@login_required
def resend_invitation(request, invitation_id):
    if request.method == 'POST':
        invitation = get_object_or_404(TeamInvitation, id=invitation_id)

        new_token = secrets.token_urlsafe(32)
        signer = Signer()
        signed_token = signer.sign(new_token)

        invitation.token = signed_token
        invitation.expires_at = timezone.now() + timedelta(days=15)  # Set expiration to 7 days from now
        invitation.save()

        invite_link = f"http://127.0.0.1:8000/freelancer/join_team/{new_token}/"
        decline_link = f"http://127.0.0.1:8000/freelancer/decline_invitation/{invitation.id}/"  # Link to decline invitation

        # Send the email
        send_mail(
            subject=f'Invitation to join {invitation.team.name}',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=render_to_string('freelancer/team_invitation.html', {
                'team': invitation.team,
                'invitation': invitation,
                'invite_link': invite_link,
                'decline_link': decline_link, 
                'join_code': invitation.team.join_code
            })
        )
 
        messages.success(request, f'Invitation resent to {invitation.email}')
        return redirect('freelancer:manage_team', team_id=invitation.team.id)

    return redirect('freelancer:manage_team', team_id=invitation.team.id)

@login_required
def decline_invitation(request, invitation_id):
    invitation = get_object_or_404(TeamInvitation, id=invitation_id)
    invitation.status = 'rejected'
    invitation.save()
    
    messages.success(request, 'Invitation declined successfully.')
    
    return render(request, 'freelancer/decline_confirmation.html')

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Team, TeamMember

@login_required
def save_team_salaries(request):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method')
        return redirect('freelancer:manage_team')

    try:
        team_id = request.POST.get('team_id')
        team = Team.objects.get(id=team_id)
        
        # Update PROJECT_MANAGER percentage
        pm_percentage = int(request.POST.get('PROJECT_MANAGER', 0))
        TeamMember.objects.filter(
            team=team,
            role='PROJECT_MANAGER'
        ).update(salary_percentage=pm_percentage)

        # Update or create other roles
        other_roles = ['DESIGNER', 'FRONTEND_DEV', 'BACKEND_DEV', 'QA_TESTER']
        for role in other_roles:
            percentage = int(request.POST.get(role, 0))
            TeamMember.objects.update_or_create(
                team=team,
                role=role,
                defaults={
                    'salary_percentage': percentage,
                    'is_active': True  # Using is_active instead of status
                }
            )

        messages.success(request, 'Salary percentages updated successfully')
        
    except Team.DoesNotExist:
        messages.error(request, 'Team not found')
    except ValueError as e:
        messages.error(request, f'Invalid percentage value provided: {str(e)}')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')

    return redirect('freelancer:manage_team', team_id=team_id)


from django.http import Http404
import json  # Import json to parse the request body

def create_chatroom(request):
    if request.method == 'POST':
        data = json.loads(request.body) 
        team_id = data.get('team_id') 
        try:
            team = get_object_or_404(Team, id=team_id)  
           
            existing_chatroom = ChatRoom.objects.filter(name=team.name).first()
            if existing_chatroom:
                return JsonResponse({'status': 'error', 'message': 'Chatroom already exists.', 'chatroom_id': existing_chatroom.id})

            participants = TeamMember.objects.filter(team=team).values_list('user', flat=True)  
            if not participants:
                print("Warning: No participants found for the team.")  

            chat_type = 'group' 
            chatroom = ChatRoom.objects.create(name=team.name, chat_type=chat_type)
            chatroom.participants.set(participants) 
            chatroom.save()

            return JsonResponse({'status': 'success', 'chatroom_id': chatroom.id})

        except Http404:
            return JsonResponse({'status': 'error', 'message': 'Team not found.'}, status=404)

    return JsonResponse({'status': 'error'}, status=400)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from client.models import Task  # Import your Task model

@csrf_exempt  
def assign_task(request):
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        assigned_to = request.POST.get('assigned_to')

        try:
            task = Task.objects.get(id=task_id)  # Fetch the task by ID
            task.assigned_to_id = assigned_to  # Assuming 'assigned_to' is a ForeignKey to User
            task.save()  # Save the changes
            return JsonResponse({'success': True, 'message': 'Task assigned successfully.'})
        except Task.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Task not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)




@csrf_exempt  # Use this only if you are not using CSRF tokens in AJAX requests
def pay_team_salaries(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        project_id = data.get('project_id')
        print(project_id)

        # Validate project_id
        if not project_id :
            return JsonResponse({'error': 'Invalid project ID provided.'}, status=400)

        try:
            project = Project.objects.get(id=project_id)  
            team = project.team  
            team_members = TeamMember.objects.filter(team=team)  

            total_percentage = sum(member.salary_percentage for member in team_members)

            if total_percentage > 100:
                return JsonResponse({'error': 'Total salary percentage exceeds 100%'}, status=400)

            for member in team_members:
                salary = (member.salary_percentage / 100) * project.total_including_gst  # Calculate salary based on percentage
                
                SalaryPayment.objects.create(
                    team_member=member,
                    project=project,
                    amount_paid=salary,
                    paid_by=request.user,
                    status='completed'
                )

            return JsonResponse({'success': 'Salaries paid successfully for all team members.'})

        except Project.DoesNotExist:
            return JsonResponse({'error': 'Project not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)



@csrf_exempt  # Use this only if you are not using CSRF tokens in AJAX requests
@login_required
def toggle_open_to_work(request):
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['open', 'close']:
            # Get the user's FreelancerProfile
            freelancer_profile = FreelancerProfile.objects.get(user=request.user)
            # Set the is_open_to_work field based on the status
            freelancer_profile.is_open_to_work = (status == 'open')  # True if 'open', False if 'close'
            freelancer_profile.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

from django.contrib.auth.decorators import login_required
from django.utils import timezone
from client.models import EventAndQuiz, EventRegistration

@login_required
def events_and_quizzes_view(request):
    current_time = timezone.now()
    upcoming_events = EventAndQuiz.objects.filter(
        date__gt=current_time,
        event_status='upcoming'
    ).order_by('date')
    
    past_events = EventAndQuiz.objects.filter(
        Q(event_status='done') | Q(date__gt=current_time)  # OR condition
    ).order_by('date')
    
    # Get both registration IDs and attended status
    registrations = EventRegistration.objects.filter(
        freelancer=request.user
    ).values('event_id', 'attended')
    
    registered_events = {reg['event_id']: reg['attended'] for reg in registrations}
    
    print(registered_events)
    upcoming_events_list = upcoming_events.filter(type='event')
    upcoming_quizzes = upcoming_events.filter(type='quiz')
    past_events_list = past_events.filter(type='event')
    past_quizzes = past_events.filter(type='quiz')

    # Fetch certificates
    user_id = request.user.id
    certificates_path = os.path.join(settings.MEDIA_ROOT, 'certificates', str(user_id))
    certificates = []

    if os.path.exists(certificates_path):
        for filename in os.listdir(certificates_path):
            if filename.endswith('.pdf') or filename.endswith('.jpg') or filename.endswith('.png'):  # Adjust as needed
                certificates.append({
                    'name': filename,
                    'view_url': f'/media/certificates/{user_id}/{filename}',  # URL to view the certificate
                    'download_url': f'/media/certificates/{user_id}/{filename}'  # URL to download the certificate
                })

    context = {
        'upcoming_events': upcoming_events_list,
        'upcoming_quizzes': upcoming_quizzes,
        'past_events': past_events_list,
        'past_quizzes': past_quizzes,
        'registered_events': registered_events,  # Now contains both event_id and attended status
        'active_page': 'events_quizzes',
        'certificates': certificates  # Add certificates to context
    }
    
    return render(request, 'freelancer/events_and_quizzes.html', context)

from django.http import JsonResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
import json

@login_required
def register_event(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():  # Use transaction to ensure data consistency
                data = json.loads(request.body)
                event_id = data.get('event_id')
                
                # Get the event/quiz
                event = EventAndQuiz.objects.select_for_update().get(id=event_id)  
                
                # Increment the registration count
                event.number_of_registrations += 1
                event.save()
                
                # Register the user
                registration = EventRegistration.objects.create(
                    freelancer=request.user,
                    event=event
                )
                
                # Prepare email content
                context = {
                    'user': request.user,
                    'event': event,
                    'registration': registration
                }
                
                # Render email template
                email_html = render_to_string('freelancer/email_registration.html', context)
                
                # Create email message
                email = EmailMessage(
                    subject=f'Registration Confirmation: {event.title}',
                    body=email_html,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[request.user.email]
                )
                email.content_subtype = "html"  # Main content is now HTML
                
                # Attach poster if it exists
                if event.poster:
                    # Get the file name from the poster path
                    file_name = event.poster.name.split('/')[-1]
                    # Attach the poster file
                    email.attach(
                        filename=file_name,
                        content=event.poster.read(),
                        mimetype='application/octet-stream'
                    )
                
                # Send email
                email.send(fail_silently=False)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Registration successful!'
                })
                
        except EventAndQuiz.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Event not found.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })
    
    
from client.models import QuizQuestion  
import json  # Add this import at the top

def quiz_view(request, quiz_id):
    is_registered = EventRegistration.objects.filter(
        freelancer=request.user,
        event=quiz_id  
    ).exists()
    event = get_object_or_404(EventAndQuiz, id=quiz_id)
    is_attended = EventRegistration.objects.filter(
        freelancer=request.user,
        event=quiz_id,
        attended=True
    ).exists()
    duration = event.duration  
    
    # Get questions and convert QuerySet to list of dictionaries
    questions = QuizQuestion.objects.filter(quiz=quiz_id).values(
        'question', 
        'option1', 
        'option2', 
        'option3', 
        'option4',
        'correct_answer',
        'points'
    )
    questions_list = list(questions)
    
    # Serialize the questions list to JSON
    questions_json = json.dumps(questions_list)
    
    return render(request, 'freelancer/quiz.html', {
        'quiz_id': quiz_id,
        'questions': questions_json,  # Send serialized JSON
        'is_registered': is_registered,
        'duration': duration,
        'is_attended': is_attended
    })
    
from client.models import QuizAttempt  # Add this import at the top

@login_required
@csrf_exempt  # Be careful with CSRF exemption in production
def submit_quiz(request, quiz_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score', 0)
            
            # Create quiz attempt record
            quiz = get_object_or_404(EventAndQuiz, id=quiz_id)
            QuizAttempt.objects.create(
                quiz=quiz,
                freelancer=request.user,
                score=score
            )
            
            # Update EventRegistration to mark as attended
            registration = EventRegistration.objects.get(
                freelancer=request.user,
                event=quiz
            )
            registration.attended = True
            registration.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Quiz submitted successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    }, status=400)
    
    
    
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json
from .models import FreelancerProfile

@login_required
@nocache
def analyze_skill_gap(request):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2 = Register.objects.get(user_id=uid)
    freelancer = FreelancerProfile.objects.get(user_id=uid)
    
    if profile1.permission:
        
        context = {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        }
        
        return render(request, 'freelancer/skill_gap_analysis.html', context)
    else:
        return render(request, 'freelancer/PermissionDenied.html', {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer
        })




from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
import os
import pandas as pd
import requests
from .models import FreelancerProfile
from dotenv import load_dotenv
import google.generativeai as genai
import spacy
from bs4 import BeautifulSoup
import re
from fuzzywuzzy import fuzz

# Load spaCy NLP model
nlp = spacy.load('en_core_web_sm')
standardized_skills_df = pd.read_csv(os.path.join(os.path.dirname(__file__), 'skills.csv')) 
standardized_skills = set(standardized_skills_df['skill'].str.lower().str.strip())  # Store for quick lookup


def standardize_skill(skill):
    # Remove numbers, dashes, and extra characters
    skill = re.sub(r'[\d\.\-\(\)\[\]•]', '', skill).strip().lower()

    exact_matches = {
        "javascript": "javascript",
        "js": "javascript",
        "html5": "html",
        "css3": "css",
        "react": "react",
        "react.js": "react",
        "react native": "react native",
        "node.js": "node.js",
        "node": "node.js",
    }
    
    # If exact match found, return the standardized version
    if skill in exact_matches:
        return exact_matches[skill]

    # Tokenize and lemmatize using spaCy
    doc = nlp(skill)
    clean_skill = ' '.join([token.lemma_ for token in doc if not token.is_stop])

    return clean_skill



def clean_and_match_skills(raw_skills):
    """
    Cleans raw skill names and matches them against the standardized skill set from CSV.
    """
    cleaned_skills = []
    
    for skill in raw_skills:
        cleaned_skill = standardize_skill(skill)
        words = cleaned_skill.split()

        matched_skill = next((s for s in standardized_skills if fuzz.partial_ratio(s, cleaned_skill) > 80), None)

        if matched_skill:
            cleaned_skills.append(matched_skill)

    return cleaned_skills


@require_http_methods(["POST"])
def get_skill_analysis(request):
    try:
        data = json.loads(request.body)
        job_role = data.get('job_role')
        
        freelancer = FreelancerProfile.objects.get(user=request.user)
        existing_skills = []
        if freelancer.skills:
            skills_str = freelancer.skills.strip('[]')
            existing_skills = [
                standardize_skill(skill.strip().strip("'").replace('-', ''))
                for skill in skills_str.split(',')
                if skill.strip()
            ]
            
        load_dotenv()
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        professional_check_prompt = f"Is {job_role} a professional job role? yes/no"
        professional_check_response = model.generate_content(professional_check_prompt)
        print(professional_check_response.text)  # For debugging

        # Clean and normalize the response
        is_professional = professional_check_response.text.strip().lower()
        if 'yes' in is_professional:  # More flexible check
            
            fundamental_prompt = f"""I'm interested in a career as a {job_role}. 
            What are the core technical skills I need to develop to be competitive in this field?
            List only 5 main skills, without any description."""
            
            print("Fundamental Prompt:", fundamental_prompt)
            
            try:
                fundamental_response = model.generate_content(fundamental_prompt)
                print("Fundamental Response:", fundamental_response.text)  # Print the response from the AI
                
                raw_fundamental_skills = [skill.strip() for skill in fundamental_response.text.split('\n') if skill.strip()]
                fundamental_skills = clean_and_match_skills(raw_fundamental_skills)

                print("Standardized Fundamental Skills:", fundamental_skills)  # Print standardized skills

                missing_fundamentals = [skill for skill in fundamental_skills if skill not in existing_skills]
                print("Missing Fundamentals:", missing_fundamentals)  # Debugging statement

                # If fundamental skills are missing, recommend courses
                if missing_fundamentals:
                    course_recommendations = []
                    for skill in missing_fundamentals:
                        courses = fetch_classcentral_courses(skill)
                        course_recommendations.extend(courses)

                    return JsonResponse({
                        'success': True,
                        'existing_skills': existing_skills,
                        'fundamental_skills': fundamental_skills,
                        'missing_fundamentals': missing_fundamentals,
                        'needs_fundamentals': True,
                        'course_recommendations': course_recommendations
                    })

                # Get Trending Skills
                current_year = datetime.now().year
                trending_prompt = f"""I'm a {job_role} looking to stay ahead of the curve. 
                What are the most in-demand technical skills, frameworks, and specific technologies for a {job_role} in {current_year}? 
                Focus only on specific tools, libraries, and frameworks. Provide just the names, no descriptions."""

                print("Trending Prompt:", trending_prompt)  # Print the prompt given to the AI
                
                trending_response = model.generate_content(trending_prompt)
                print("Trending Response:", trending_response.text)  # Print the response from the AI
                
                raw_trending_skills = [skill.strip() for skill in trending_response.text.split('\n') if skill.strip()]
                trending_skills = clean_and_match_skills(raw_trending_skills)

                print("Standardized Trending Skills:", trending_skills)  # Print standardized skills

                skill_gaps = [skill for skill in trending_skills if skill not in existing_skills]

                course_recommendations = []
                for skill in skill_gaps:
                    courses = fetch_classcentral_courses(skill)
                    course_recommendations.extend(courses)

                return JsonResponse({
                    'success': True,
                    'existing_skills': existing_skills,
                    'fundamental_skills': fundamental_skills,
                    'trending_skills': trending_skills,
                    'skill_gaps': skill_gaps,
                    'needs_fundamentals': False,
                    'course_recommendations': course_recommendations
                })

            except Exception as e:
                print("Error in fundamental skills generation:", str(e))  # Debugging statement
                return JsonResponse({'success': False, 'message': f'Error generating recommendations: {str(e)}'}, status=500)
        else:
            return JsonResponse({'success': False, 'message': "It is not a professional job role."}, status=400)
    except FreelancerProfile.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Freelancer profile not found'}, status=404)
    except Exception as e:
        print("General error:", str(e))  # Debugging statement
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def fetch_classcentral_courses(skill):
    """
    Fetches top courses from Class Central for a given skill.
    """
    base_url = "https://www.classcentral.com/search?q="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def scrape_courses(url):
        """Helper function to scrape courses from a given URL."""
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        courses = []

        for course_card in soup.find_all("li", class_="bg-white", limit=3):  # Fetch top 3 courses
            try:
                title_elem = course_card.find("h2", class_="text-1")
                if not title_elem:
                    continue
                title = title_elem.text.strip()

                link_elem = course_card.find("a", class_="color-charcoal")
                link = "https://www.classcentral.com" + link_elem["href"] if link_elem else ""

                img_elem = course_card.find("img")
                img_url = img_elem["src"] if img_elem and "src" in img_elem.attrs else ""

                provider_elem = course_card.find("a", class_="color-charcoal")
                provider = provider_elem.text.strip() if provider_elem else "Unknown Provider"

                if title and link:
                    courses.append({
                        "title": title,
                        "platform": provider,
                        "url": link,
                        "image_url": img_url
                    })
            except Exception as e:
                print(f"Error processing course card: {e}")
                continue

        return courses

    courses = scrape_courses(base_url + skill)

    if not courses:
        courses = scrape_courses(base_url + skill + "&level=beginner")

    return courses


# Refactored FreelanceHub API with Performance and NLP Improvements

# import json
# import os
# import requests
# from bs4 import BeautifulSoup
# from django.http import JsonResponse
# from django.views.decorators.http import require_http_methods
# from django.core.cache import cache
# from concurrent.futures import ThreadPoolExecutor
# from django.db.models import F
# from fuzzywuzzy import fuzz
# import spacy
# import google.generativeai as genai
# from dotenv import load_dotenv
# from .models import FreelancerProfile
# import re


# nlp = spacy.load('en_core_web_sm')

# def standardize_skill(skill):
#     doc = nlp(skill)
#     clean_skill = re.sub(r'[^a-zA-Z0-9\s]', '', ' '.join([token.lemma_ for token in doc if not token.is_stop]))
#     return clean_skill.lower().strip()

# def scrape_courses(skill):
#     base_url = f"https://www.classcentral.com/search?q={skill}"
#     response = requests.get(base_url, headers={"User-Agent": "Mozilla/5.0"})
#     if response.status_code != 200:
#         return []
#     soup = BeautifulSoup(response.text, "html.parser")
#     courses = []
#     for card in soup.find_all("li", class_="bg-white", limit=3):
#         title = card.find("h2", class_="text-1")
#         link = card.find("a", class_="color-charcoal")
#         if title and link:
#             courses.append({"title": title.text.strip(), "url": "https://www.classcentral.com" + link["href"]})
#     return courses

# def fetch_courses_concurrently(skills):
#     with ThreadPoolExecutor() as executor:
#         results = list(executor.map(scrape_courses, skills))
#     return [course for sublist in results for course in sublist]

# @require_http_methods(["POST"])
# def get_skill_analysis(request):
#     try:
#         data = json.loads(request.body)
#         print("Received data:", data)  # Debugging statement
#         job_role = data.get('job_role')
#         print("Job role:", job_role)  # Debugging statement
        
#         freelancer = FreelancerProfile.objects.get(user=request.user)
#         existing_skills = [
#             skill.strip().strip("'").lower().replace('-', '')
#             for skill in freelancer.skills.strip('[]').split(',') if skill.strip()
#         ] if freelancer.skills else []
#         print("Existing skills:", existing_skills)  # Debugging statement

#         load_dotenv()
#         genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
#         model = genai.GenerativeModel('gemini-pro')

#         fundamental_response = model.generate_content(f"I'm interested in a career as a {job_role}. List 2 core technical skills needed (names only).")
#         fundamental_skills = [standardize_skill(skill) for skill in fundamental_response.text.split('\n') if skill.strip()]
#         print("Fundamental skills:", fundamental_skills)  # Debugging statement
        
#         # Clean up fundamental skills by removing numeric prefixes
#         cleaned_fundamental_skills = [skill.split(' ', 1)[-1].strip() for skill in fundamental_skills]
#         print("Cleaned fundamental skills:", cleaned_fundamental_skills)  # Debugging statement

#         missing_fundamentals = []
#         for skill in cleaned_fundamental_skills:
#             is_missing = not any(fuzz.partial_ratio(skill, es) > 80 for es in existing_skills)
#             print(f"Checking if '{skill}' is missing: {is_missing}")  # Debugging statement
#             if is_missing:
#                 missing_fundamentals.append(skill)

#         print("Missing fundamentals:", missing_fundamentals)  # Debugging statement
        
#         if missing_fundamentals:
#             fundamental_courses = fetch_courses_concurrently(missing_fundamentals)
#             return JsonResponse({
#                 'success': True,
#                 'needs_fundamentals': True,
#                 'fundamental_skills': cleaned_fundamental_skills,
#                 'missing_fundamentals': missing_fundamentals,
#                 'course_recommendations': fundamental_courses
#             })

#         trending_response = model.generate_content(f"What are the most in-demand technologies for {job_role} in 2025? Provide a plain list of names only.")
#         trending_skills = [standardize_skill(skill) for skill in trending_response.text.split('\n') if skill.strip()]
#         print("Trending skills:", trending_skills)  # Debugging statement

#         skill_gaps = []
#         for skill in trending_skills:
#             is_gap = not any(fuzz.ratio(skill, es) > 80 for es in existing_skills)
#             print(f"Checking if '{skill}' is a skill gap: {is_gap}")  # Debugging statement
#             if is_gap:
#                 skill_gaps.append(skill)

#         print("Skill gaps:", skill_gaps)  # Debugging statement

#         trending_courses = fetch_courses_concurrently(skill_gaps)
#         return JsonResponse({
#             'success': True,
#             'needs_fundamentals': False,
#             'trending_skills': trending_skills,
#             'skill_gaps': skill_gaps,
#             'course_recommendations': trending_courses
#         })
#     except Exception as e:
#         print("Error occurred:", str(e))  # Debugging statement
#         return JsonResponse({'success': False, 'message': str(e)}, status=500)


def freelancer_repositories(request):
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
            team_members = TeamMember.objects.filter(team_id=project.team_id)
            member_profiles = [{'user_id': member.user.id, 'profile_picture': member.user.register.profile_picture.url if member.user.register.profile_picture else None} for member in team_members]
            
            client_profile_picture = project.user.register.profile_picture.url if project.user.register.profile_picture else None
            
            # Determine if the user is part of a team
            if team_members.filter(user=request.user).exists():
                repository_data.append({
                    'repository': repo,
                    'repository_id': repo.id,
                    'project_title': project.title,
                    'project_category': getattr(project, 'category', 'N/A'),  # Using getattr for safer access
                    'members': member_profiles,
                    'client_profile_picture': client_profile_picture
                })
            else:
                current_freelancer_picture = request.user.register.profile_picture.url if request.user.register.profile_picture else None
                repository_data.append({
                    'repository': repo,
                    'repository_id': repo.id,
                    'project_title': project.title,
                    'project_category': getattr(project, 'category', 'N/A'),  # Using getattr for safer access
                    'members': [{'user_id': request.user.id, 'profile_picture': current_freelancer_picture}],
                    'client_profile_picture': client_profile_picture
                })

        is_project_manager = TeamMember.objects.filter(user=request.user, role='PROJECT_MANAGER').exists()
        
    else:
        repository_data = []
        is_project_manager = False
        
    return render(request, 'freelancer/Repositories.html', {
        'repositories': repository_data,
        'is_project_manager': is_project_manager
    })

from core.models import SubscriptionPlan,UserSubscription
@login_required
def plans(request):
    plans = SubscriptionPlan.objects.all()
    
    for plan in plans:
        plan.features_list = plan.features.split(',')  # Split the features by comma

    return render(request, 'freelancer/plans.html', {'plans': plans})
