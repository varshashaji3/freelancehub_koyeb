from freelancer.models import FreelancerProfile
from core.models import CustomUser, Register
from django.shortcuts import get_object_or_404
def freelancer_context(request):
    if request.user.is_authenticated and request.user.role == 'freelancer':
        uid = request.user.id
        profile1 = get_object_or_404(CustomUser, id=uid)
        profile2 = get_object_or_404(Register, user_id=uid)
        
        try:
            freelancer = FreelancerProfile.objects.get(user_id=uid)
        except FreelancerProfile.DoesNotExist:
            freelancer = None  # or handle the case when it doesn't exist
        
        return {
            'profile1': profile1,
            'profile2': profile2,
            'freelancer': freelancer,
        }
    return {}
