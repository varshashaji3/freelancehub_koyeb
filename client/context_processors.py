from client.models import ClientProfile, Project, Task
from core.models import CustomUser, Register
import json
from django.db import models

def client_context(request):
    if request.user.is_authenticated and request.user.role == 'client':
        uid = request.user.id
        profile1 = CustomUser.objects.get(id=uid)
        profile2 = Register.objects.get(user_id=uid)
        try:
            client = ClientProfile.objects.get(user_id=uid)
        except ClientProfile.DoesNotExist:
            freelancer = None  
        return {
            'profile1': profile1,
            'profile2': profile2,
            'client': client,
        }
    return {}

def project_completion_status(request):
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'projects_completed': []}
        
    try:
        projects_completed = []
        
        user_projects = Project.objects.filter(
            user=request.user,
            project_status='In Progress'
        ).select_related('user', 'freelancer')
        
        for project in user_projects:
            tasks = Task.objects.filter(project=project)
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status='Completed').count()
            
            if total_tasks > 0 and completed_tasks == total_tasks:
                freelancer_register = Register.objects.filter(user=project.freelancer).first() if project.freelancer else None
                
                project_data = {
                    'id': project.id,
                    'title': project.title,
                    'total_tasks': total_tasks,
                    'budget': float(project.budget),
                    'freelancer_first_name': freelancer_register.first_name if freelancer_register else '',
                    'freelancer_last_name': freelancer_register.last_name if freelancer_register else ''
                }
                projects_completed.append(project_data)
        
        return {'projects_completed': projects_completed}
        
    except Exception as e:
        print(f"Error in project_completion_status: {str(e)}")
        return {'projects_completed': []}
