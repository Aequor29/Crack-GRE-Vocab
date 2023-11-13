
# Create your models here.
from django.db import models

class User(models.Model):
    # Define user fields
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    passwordHash = models.CharField(max_length=256)
    dateJoined = models.DateTimeField(auto_now_add=True)

class Word(models.Model):
    # Define word fields
    word = models.CharField(max_length=100)
    pronunciation = models.CharField(max_length=100)

class Definition(models.Model):
    # Define definition fields
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    definition = models.TextField()
    partOfSpeech = models.CharField(max_length=50)
    usageExample = models.TextField()

class Progress(models.Model):
    # Define progress fields
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    proficiencyLevel = models.IntegerField(default=0)
    nextReviewDate = models.DateField()
    lastEncounter = models.DateTimeField(auto_now=True)

class Session(models.Model):
    # Define session fields
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    startTime = models.DateTimeField()
    endTime = models.DateTimeField()
    sessionDate = models.DateField()
    sessionType = models.CharField(max_length=50)  # E.g., 'learning' or 'review'
