from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .knowledge_base import FreelanceHubBot

# Create your views here.

# Initialize the bot
bot = FreelanceHubBot()

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            # Get user input from the request
            user_input = json.loads(request.body).get('message', '')
            
            # Get response from the bot
            response = bot.get_response(user_input)
            
            return JsonResponse({
                'response': response,
                'bot_name': bot.name
            })
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method.'}, status=400)
