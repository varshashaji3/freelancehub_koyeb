from django.db import models

class ChatbotKnowledge(models.Model):
    query = models.CharField(max_length=255, unique=True)
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.query
