from django.contrib.auth.models import User
from django.db import models
from django.utils.timezone import now

class Word(models.Model):
    word = models.CharField(max_length=100, unique=True)
    pronunciation = models.CharField(max_length=100)

    def __str__(self):
        return self.word

class Definition(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    definition = models.TextField()
    part_of_speech = models.CharField(max_length=50)
    usage_example = models.TextField()

    def __str__(self):
        return f"{self.word}: {self.definition}"
    

class Session(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(default=now)
    session_date = models.DateField(auto_now_add=True)
    session_type = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.username} - Session on {self.session_date}"

class Progress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    proficiency_level = models.IntegerField()
    next_review_date = models.DateField()
    last_encounter = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.word}"


