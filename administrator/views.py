from django.shortcuts import render

# Create your views here.
from django.shortcuts import redirect, render

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from client.models import ClientProfile, Complaint
from core.decorators import nocache
from core.models import CustomUser, Notification, Register, SiteReview
from freelancer.models import FreelancerProfile

from django.contrib import messages

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from client.models import Project

from django.db.models import Count

from django.db.models import Avg
from django.db.models.functions import TruncMonth
import json


@login_required
@nocache
def admin_view(request):
    if 'uid' not in request.session and not request.user.is_authenticated:
        return redirect('login_view')
    
    uid = request.user.id
    
    user_count=CustomUser.objects.filter(is_superuser=False).count()
    client_count = CustomUser.objects.filter(role='client').count()
    freelancer_count = CustomUser.objects.filter(role='freelancer').count()

    # Aggregate monthly user counts
    monthly_data = CustomUser.objects.annotate(month=TruncMonth('joined')).values('month').annotate(count=Count('id')).order_by('month')

    months = []
    client_counts = []
    freelancer_counts = []

    for month in monthly_data:
        month_name = month['month'].strftime('%b %Y')
        months.append(month_name)
        client_counts.append(CustomUser.objects.filter(role='client', joined__month=month['month'].month, joined__year=month['month'].year).count())
        freelancer_counts.append(CustomUser.objects.filter(role='freelancer', joined__month=month['month'].month, joined__year=month['month'].year).count())

    posted_count = Project.objects.all().count()
    completed_count = Project.objects.filter(project_status='Completed').count()
    in_progress_count = Project.objects.filter(project_status='In Progress').count()
    total_complaints=Complaint.objects.all().count()
    
    total_reviews = SiteReview.objects.count()  # Count of site reviews

    # Calculate average rating for site reviews
    average_rating = SiteReview.objects.aggregate(Avg('rating'))['rating__avg'] or 0  # Default to 0 if no reviews

    # Get top 5 categories
    top_categories = Project.objects.values('category').annotate(
        count=Count('category')
    ).order_by('-count')[:5]

    category_names = [category['category'] for category in top_categories]
    category_counts = [category['count'] for category in top_categories]

    print("Category Names:", category_names)  # Debug print
    print("Category Counts:", category_counts)  # Debug print

    # Calculate average rating per month
    monthly_ratings = SiteReview.objects.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        average_rating=Avg('rating')
    ).order_by('month')

    monthly_ratings_data = [
        {
            'month': rating['month'].strftime('%B %Y'),
            'average_rating': float(rating['average_rating'])
        }
        for rating in monthly_ratings
    ]

    context = {
        'months': months,
        'client_counts': client_counts,
        'freelancer_counts': freelancer_counts,
        'posted_count': posted_count,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'user_count': user_count,
        'total_complaint': total_complaints,
        'total_reviews': total_reviews,
        'average_rating': average_rating,
        'top_categories': category_names,
        'category_counts': category_counts,
        'monthly_ratings': json.dumps(monthly_ratings_data),  # Add this line
    }

    print("Context:", context)  # Debug print

    return render(request, 'Admin/index.html', context)


@login_required
@nocache
def user_list(request):
    if not request.user.is_authenticated:
        return redirect('login_view')

    
    users = CustomUser.objects.select_related('register').all()
    clients = ClientProfile.objects.select_related('user')
    freelancers = FreelancerProfile.objects.select_related('user')
    
    
    profile = Register.objects.get(user_id=request.user.id)
    
    user_details = [{
        'first_name': user.register.first_name,
        'last_name': user.register.last_name
    } for user in users]
    
    context = {
        'users': users,
        'clients': clients,
        'freelancers': freelancers,
        'profile': profile,
        'user_details': user_details
    }
    
    return render(request, 'Admin/UserView.html', context)



@login_required
@nocache
def toggle_status(request, uid):
    user = CustomUser.objects.get(id=uid)
    
    if user.status == 'inactive':
        user.status = 'active'
        send_activation_email(uid)
    elif user.status == 'active':
        user.status = 'inactive'
        send_deactivation_email(uid)
    
    user.save()
    messages.success(request, 'User Status updated Successfully!!')
    return redirect('administrator:user_list')





@login_required
@nocache
def toggle_permission(request, uid):
    user = CustomUser.objects.get(id=uid)
    if user.permission is False:
        user.permission = True
        send_permission_email(uid)
        Notification.objects.create(
            user=user,
            message="Your permission has been granted."
        )
    elif user.permission is True:
        user.permission = False
        send_permission_denied_email(uid)
        Notification.objects.create(
            user=user,
            message="Your permission has been denied."
        )
    user.save()
    
    messages.success(request, 'User permission updated Successfully!!')
    return redirect('administrator:user_list') 






@login_required
@nocache
def account_settings(request):
    uid=request.user.id
    
    profile1 = CustomUser.objects.get(id=uid)
    profile=Register.objects.get(user_id=uid)
    
    return render(request, 'Admin/profile.html',{'profile1':profile1,'profile':profile})



@login_required
@nocache
def change_password(request, uid):
    if 'uid' not in request.session:
        return redirect('login')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)

    if request.method == 'POST':
        current = request.POST.get('current_password')
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')

        
        if profile1.check_password(current):
            profile1.set_password(new_pass)
            profile1.save()
            
            messages.success(request, 'Your password has been changed successfully!!')
            return redirect('administrator:account_settings')
    
            
        else:
            
            messages.error(request, 'Current password is incorrect!!')
            return redirect('administrator:account_settings')
    

    return render(request, 'Admin/profile.html',{'profile1':profile1,'profile2':profile2})  
    



@login_required
@nocache
def change_profile_image(request,uid):
    if 'uid' not in request.session:
        return redirect('login_view')

    uid = request.session['uid']
    profile1 = CustomUser.objects.get(id=uid)
    profile2=Register.objects.get(user_id=uid)
    if request.method=='POST':
        
        profile_picture = request.FILES.get('profile_picture')
        if profile_picture:
            profile2.profile_picture = profile_picture
            profile2.save()
            messages.success(request,'Your profile picture has been changed successfully!!')
            return redirect('administrator:account_settings')
    return render(request, 'Admin/profile.html',{'profile1':profile1,'profile2':profile2})  



import os
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
















# MAILS




def send_permission_email(uid):
    user = CustomUser.objects.get(id=uid)
    print(uid)
    subject = 'Access Granted: Welcome to FreelanceHub!'
    
    if user.role == 'client':
        client_profile = ClientProfile.objects.get(user_id=uid)
        if client_profile.client_type == 'Individual':
            
            register_info = Register.objects.get(user_id=uid)
            first_name = register_info.first_name
            last_name = register_info.last_name
            name = f"{first_name} {last_name}"
        else:  
            
            company_name = client_profile.company_name
            name = company_name
    else:  
        
        register_info = Register.objects.get(user=uid)
        first_name = register_info.first_name
        last_name = register_info.last_name
        name = f"{first_name} {last_name}"
    
    context = {
        'user_name': name
    }
    html_content = render_to_string('Admin/Permission_done.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()






def send_permission_denied_email(uid):
    user = CustomUser.objects.get(id=uid)
    subject = 'Permission Denied'
    
    if user.role == 'client':
        client_profile = ClientProfile.objects.get(user_id=uid)
        if client_profile.client_type == 'Individual':
            
            register_info = Register.objects.get(user_id=uid)
            first_name = register_info.first_name
            last_name = register_info.last_name
            name = f"{first_name} {last_name}"
        else:  
            
            company_name = client_profile.company_name
            name = company_name
    else:  
        
        register_info = Register.objects.get(user_id=uid)
        first_name = register_info.first_name
        last_name = register_info.last_name
        name = f"{first_name} {last_name}"
    
    
    context = {
        'user_name': name
    }
    html_content = render_to_string('Admin/permission_denied.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()
    
    
    
    
    

def send_deactivation_email(uid):
    subject = 'Account Deactivation Notice'
    user = CustomUser.objects.get(id=uid)
    if user.role == 'client':
        client_profile = ClientProfile.objects.get(user_id=uid)
        if client_profile.client_type == 'Individual':
            
            register_info = Register.objects.get(user_id=uid)
            first_name = register_info.first_name
            last_name = register_info.last_name
            name = f"{first_name} {last_name}"
        else:  
            
            company_name = client_profile.company_name
            name = company_name
    else:  
        
        register_info = Register.objects.get(user_id=uid)
        first_name = register_info.first_name
        last_name = register_info.last_name
        name = f"{first_name} {last_name}"
    
    context = {
        'user_name': name
    }
    html_content = render_to_string('Admin/account_activated.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()




def send_activation_email(uid):
    subject = 'Account Activation Notice'
    user = CustomUser.objects.get(id=uid)
    if user.role == 'client':
        client_profile = ClientProfile.objects.get(user_id=uid)
        if client_profile.client_type == 'Individual':
            
            register_info = Register.objects.get(user_id=uid)
            first_name = register_info.first_name
            last_name = register_info.last_name
            name = f"{first_name} {last_name}"
        else:  
            
            company_name = client_profile.company_name
            name = company_name
    else:  
        
        register_info = Register.objects.get(user_id=uid)
        first_name = register_info.first_name
        last_name = register_info.last_name
        name = f"{first_name} {last_name}"
    
    context = {
        'user_name': name
    }
    html_content = render_to_string('Admin/account_deactivated.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()



@login_required
@nocache
def notification_mark_as_read(request,not_id):
    notification = Notification.objects.get(id=not_id)
    notification.is_read = True
    notification.save()
    next_url = request.GET.get('next', 'administrator:admin_view')
    return redirect(next_url)




from django.core.paginator import Paginator
def reviews(request):
    rating_filter = request.GET.get('rating')
    sort_order = request.GET.get('sort', 'newest')

    reviews_list = SiteReview.objects.all()
    
    if rating_filter:
        reviews_list = reviews_list.filter(rating=rating_filter)
    
    if sort_order == 'rating':
        reviews_list = reviews_list.order_by('-rating')
    else:
        reviews_list = reviews_list.order_by('-created_at')

    context = {
        'reviews': reviews_list,
    }
    
    return render(request, 'Admin/reviews.html', context)



from datetime import datetime
def allusers(request):
    # Fetch all non-admin users
    users_list = CustomUser.objects.filter(is_superuser=False)
    current_year = datetime.now().year
    user_details = []
    for user in users_list:
        # Fetch related information from Register table
        register_info = Register.objects.filter(user=user).first()
        
        # Base user details
        user_data = {
            'email': user.email,
            'username': user.username,
            'role': user.role,
            'status': user.status,
            'joined': user.joined,  # Corrected field name
            'last_login': user.last_login,
            'profile_picture': register_info.profile_picture.url if register_info and register_info.profile_picture else None,
            'phone_number': register_info.phone_number if register_info else None,
        }
        
        # Add first_name and last_name from Register table for freelancers
        if user.role.lower() == 'freelancer':
            # Combine first_name and last_name for freelancers
            user_data['freelancer_name'] = f"{register_info.first_name} {register_info.last_name}" if register_info else None
        
        if user.role.lower() == 'client':
            profile = ClientProfile.objects.filter(user=user).first()
            if profile:
                if profile.client_type == 'Individual':
                    user_data['name'] = f"{register_info.first_name} {register_info.last_name}" if register_info else None
                elif profile.client_type == 'Company':
                    user_data['name'] = profile.company_name if profile.company_name else None
        
        user_details.append(user_data)
    
    # Pagination
    paginator = Paginator(user_details, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'current_year': current_year
    }
    
    return render(request, 'Admin/AllUsers.html', context)




# views.py
from django.http import HttpResponse
from core.models import CustomUser, Register 
from xhtml2pdf import pisa
from io import BytesIO



def complaints(request):
    complaints_list = Complaint.objects.all()
    
    context = {
        'complaints': complaints_list,
    }
    
    return render(request, 'Admin/complaints.html', context)




def projects(request):
    all_projects = Project.objects.all()

    project_data = []

    for project in all_projects:
        # Fetch the client profile related to the project
        client_profile = ClientProfile.objects.get(user=project.user)
        
        # Fetch the register details of the client
        register_profile = Register.objects.get(user=project.user)

        # Determine client info based on client type
        if client_profile.client_type == 'Individual':
            client_info = {
                'name': f"{register_profile.first_name} {register_profile.last_name}",
                'profile_picture': register_profile.profile_picture
            }
        elif client_profile.client_type == 'Company':
            client_info = {
                'name': client_profile.company_name,
                'profile_picture': register_profile.profile_picture
            }

        project_data.append({
            'project': project,
            'client_info': client_info
        })

    context = {
        'projects': project_data,'current_year': datetime.now().year,
    }

    return render(request, 'Admin/Projects.html', context)




from django.shortcuts import render, redirect
from .models import Template

def add_template(request):
    if request.method == 'POST':
        name = request.POST['template_name']
        file = request.FILES['template_file']
        file2 = request.FILES['cover_image']
        Template.objects.create(name=name, file=file,cover_image=file2)
        return redirect('administrator:template_list') 

    return render(request, 'Admin/AddTemplate.html')


def template_list(request):
    templates = Template.objects.all()  # Fetch all templates from the database
    return render(request, 'Admin/Templates.html', {'templates': templates})

@login_required
@nocache
def site_complaints(request):
    site_complaints_list = Complaint.objects.filter(complaint_type='Site Issue')  # Assuming 'Site' is a type of complaint

    context = {
        'complaints': site_complaints_list,
    }
    
    return render(request, 'Admin/site_complaints.html', context)  # Create a corresponding template for this view


def update_solution(request):
    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        solution = request.POST.get('solution')
        
        # Update the complaint's solution
        complaint = Complaint.objects.get(id=complaint_id)
        complaint.resolution = solution
        complaint.resolution_status = 'Pending'  # Set resolution status to Pending
        complaint.save()
        
        return redirect("administrator:site_complaints")
    return redirect("administrator:site_complaints")







