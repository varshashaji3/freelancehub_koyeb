from .models import ChatbotKnowledge
from django.db.models import Q

class FreelanceHubBot:
    def __init__(self):
        self.name = "FreelanceAI"
        # Initialize default responses if database is empty
        self.initialize_knowledge_base()

    def initialize_knowledge_base(self):
        # Only initialize if the database is empty
        if ChatbotKnowledge.objects.count() == 0:
            default_knowledge = {
                "what is your name": "My name is FreelanceAI! I'm here to help you with the freelancing platform.",
                "whats your name": "My name is FreelanceAI! I'm here to help you with the freelancing platform.",
                "what's your name": "My name is FreelanceAI! I'm here to help you with the freelancing platform.",
                "your name": "My name is FreelanceAI! I'm here to help you with the freelancing platform.",
                "who are you": "I'm FreelanceAI, your assistant for the freelancing platform. How can I help you today?",
                "hello": "Hi! I'm FreelanceAI. How can I help you today?",
                "hi": "Hello! I'm FreelanceAI. How can I help you today?",
                "bye": "Goodbye! Feel free to come back if you have more questions.",
                "portfolio": "To create your portfolio:\n1. Go to your Freelancer Dashboard\n2. Select 'Portfolio' from the menu\n3. Click 'Create Portfolio' in the dropdown\n4. Choose your preferred template\n5. Upload your resume in PDF format\n6. Submit to create your portfolio",
                "how to create portfolio": "To create your portfolio:\n1. Go to your Freelancer Dashboard\n2. Select 'Portfolio' from the menu\n3. Click 'Create Portfolio' in the dropdown\n4. Choose your preferred template\n5. Upload your resume in PDF format\n6. Submit to create your portfolio",
                "create portfolio": "To create your portfolio:\n1. Go to your Freelancer Dashboard\n2. Select 'Portfolio' from the menu\n3. Click 'Create Portfolio' in the dropdown\n4. Choose your preferred template\n5. Upload your resume in PDF format\n6. Submit to create your portfolio",
                
                "proposal": "To submit a project proposal:\n1. Find a project you're interested in\n2. Click 'Submit Proposal'\n3. Write a compelling cover letter\n4. Set your bid amount and timeline\n5. Attach relevant portfolio items\n6. Review and submit your proposal",
                "how to submit proposal": "To submit a project proposal:\n1. Find a project you're interested in\n2. Click 'Submit Proposal'\n3. Write a compelling cover letter\n4. Set your bid amount and timeline\n5. Attach relevant portfolio items\n6. Review and submit your proposal",
                "submit proposal": "To submit a project proposal:\n1. Find a project you're interested in\n2. Click 'Submit Proposal'\n3. Write a compelling cover letter\n4. Set your bid amount and timeline\n5. Attach relevant portfolio items\n6. Review and submit your proposal",
                
                "team": "To create and manage teams:\n1. Go to 'Manage Teams' in your dashboard\n2. Click 'Create New Team'\n3. Add team name and description\n4. Invite team members via email\n5. Set member roles and permissions\n6. Start collaborating on projects",
                "create team": "To create and manage teams:\n1. Go to 'Manage Teams' in your dashboard\n2. Click 'Create New Team'\n3. Add team name and description\n4. Invite team members via email\n5. Set member roles and permissions\n6. Start collaborating on projects",
                "how to create team": "To create and manage teams:\n1. Go to ' Manage Teams' in your dashboard\n2. Click 'Create New Team'\n3. Add team name \n4. Invite team members via email\n5. Set member roles and permissions\n6. Start collaborating on projects",
                
                "payment": "To manage your payments:\n1. Go to 'Payment Settings' in your dashboard\n2. Add your preferred payment method\n3. Set up automatic payments if desired\n4. View payment history\n5. Set up invoicing preferences\n6. Monitor pending payments",
                "payment methods": "To manage your payments:\n1. Go to 'Payment Settings' in your dashboard\n2. Add your preferred payment method\n3. Set up automatic payments if desired\n4. View payment history\n5. Set up invoicing preferences\n6. Monitor pending payments",
                "how to get paid": "To manage your payments:\n1. Go to 'Payment Settings' in your dashboard\n2. Add your preferred payment method\n3. Set up automatic payments if desired\n4. View payment history\n5. Set up invoicing preferences\n6. Monitor pending payments",
                
                "project": "To manage your projects:\n1. Access your Project Dashboard\n2. View active and completed projects\n3. Track project milestones\n4. Communicate with clients\n5. Submit deliverables\n6. Monitor project deadlines",
                "manage project": "To manage your projects:\n1. Access your Project Dashboard\n2. View active and completed projects\n3. Track project milestones\n4. Communicate with clients\n5. Submit deliverables\n6. Monitor project deadlines",
                "project management": "To manage your projects:\n1. Access your Project Dashboard\n2. View active and completed projects\n3. Track project milestones\n4. Communicate with clients\n5. Submit deliverables\n6. Monitor project deadlines",
                
                "account": "To manage your account settings:\n1. Go to 'Account Settings'\n2. Update your profile information\n3. Manage notification preferences\n4. Set privacy options\n5. Configure security settings\n6. Update contact information",
                "settings": "To manage your account settings:\n1. Go to 'Account Settings'\n2. Update your profile information\n3. Manage notification preferences\n4. Set privacy options\n5. Configure security settings\n6. Update contact information",
                "account settings": "To manage your account settings:\n1. Go to 'Account Settings'\n2. Update your profile information\n3. Manage notification preferences\n4. Set privacy options\n5. Configure security settings\n6. Update contact information",
            }
            
            # Bulk create the default knowledge
            ChatbotKnowledge.objects.bulk_create([
                ChatbotKnowledge(query=query.lower(), response=response)  # Store queries in lowercase
                for query, response in default_knowledge.items()
            ])

    def get_response(self, user_input):
        # Convert input to lowercase for better matching
        user_input = user_input.lower().strip()
        
        try:
            # First try exact match
            response = ChatbotKnowledge.objects.filter(
                query__iexact=user_input
            ).first()
            
            if response:
                return response.response
            
            # If no exact match, try partial match using OR conditions
            words = user_input.split()
            q_objects = Q()
            for word in words:
                q_objects |= Q(query__icontains=word)
            
            response = ChatbotKnowledge.objects.filter(q_objects).first()
            
            if response:
                return response.response
            
            # Default response if no match found
            return "I'm not sure about that."
            
        except Exception as e:
            print(f"Error retrieving response: {e}")
            return "I'm having trouble accessing my knowledge base. Please try again later." 