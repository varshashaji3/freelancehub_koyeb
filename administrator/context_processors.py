from core.models import CustomUser, Register
from django.core.exceptions import ObjectDoesNotExist

def user_profile(request):
    if request.user.is_authenticated:
        try:
            user = CustomUser.objects.get(id=request.user.id)
            profile = Register.objects.get(user_id=request.user.id)
        except ObjectDoesNotExist:
            # If no profile exists, return user but set profile to None
            profile = None
        return {
            'user': user,
            'profile': profile,
        }
    return {}