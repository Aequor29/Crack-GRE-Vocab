from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Word, Progress, Session, Definition
from django.utils import timezone
from .serializers import WordSerializer, ProgressSerializer
from rest_framework import status
from datetime import timedelta

class SessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        user = request.user
        session_type = request.data.get('session_type')

        new_session = Session.objects.create(
            user=user,
            start_time=timezone.now(),
            end_time=timezone.now(),  # Initially set to None, can be updated later
            session_type=session_type
        )
        return Response({'session_id': new_session.id}, status=status.HTTP_201_CREATED)
    
class NewWordsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        # Get the IDs of words that the user has already encountered
        encountered_word_ids = Progress.objects.filter(user=user).values_list('word_id', flat=True)
        # Fetch words that the user has not encountered
        new_words = Word.objects.exclude(id__in=encountered_word_ids)[:10]  # Adjust the number as needed
        serializer = WordSerializer(new_words, many=True)
        return Response(serializer.data)

class WordResponseView(APIView):
    permission_classes = [IsAuthenticated]

    
    def post(self, request, format=None):
        user = request.user
        word_id = request.data.get('word_id')
        response = request.data.get('response')  # 'remember' or 'forget'
        session_id = request.data.get('session_id')  # assuming session ID is sent in the request

        try:
            word = Word.objects.get(id=word_id)
            session = Session.objects.get(id=session_id)
        except (Word.DoesNotExist, Session.DoesNotExist):
            return Response({'error': 'Invalid word or session.'}, status=status.HTTP_400_BAD_REQUEST)

        # Logic to update or create a UserProgress instance
        progress, created = Progress.objects.get_or_create(
            user=user, 
            word=word,
            defaults={'last_encounter': session, 'proficiency_level': 0, 'next_review_date': timezone.now().date()}
        )

        if response == 'remember':
            # Increase proficiency level
            progress.proficiency_level += 1
            # Calculate next review date based on the new proficiency level
            progress.next_review_date = timezone.now().date() + timedelta(days=2 ** progress.proficiency_level)
        elif response == 'forget':
            # Reset or decrease proficiency level
            progress.proficiency_level = 0  # or max(progress.proficiency_level - 1, 0)
            # Set next review date to tomorrow
            progress.next_review_date = timezone.now().date() + timedelta(days=1)

        progress.last_encounter = session
        progress.save()

        return Response(status=status.HTTP_200_OK)
    

class ReviewWordsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        # Fetch words where the next review date is today or has passed
        due_for_review = Progress.objects.filter(
            user=user, 
            next_review_date__lte=timezone.now().date()
        ).values_list('word_id', flat=True)

        review_words = Word.objects.filter(id__in=due_for_review)
        serializer = WordSerializer(review_words, many=True)
        return Response(serializer.data)
    
class UpdateProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, format=None):
        user = request.user
        word_id = request.data.get('word_id')
        response = request.data.get('response')  # Expect 'remember' or 'forget'
        session_id = request.data.get('session_id')

        try:
            word = Word.objects.get(id=word_id)
            session = Session.objects.get(id=session_id)
            progress = Progress.objects.get(user=user, word=word)
        except (Word.DoesNotExist, Session.DoesNotExist, Progress.DoesNotExist):
            return Response({'error': 'Invalid word, session, or progress.'}, status=status.HTTP_404_NOT_FOUND)

        if response == 'remember':
            # Update logic for 'remember' response
            # E.g., increase proficiency level, calculate next review date
            progress.proficiency_level += 1  # Example increment
            progress.next_review_date = calculate_next_review_date(progress.proficiency_level)  # Implement this function
        elif response == 'forget':
            # Update logic for 'forget' response
            # E.g., reset proficiency level, set next review date for sooner
            progress.proficiency_level = 0  # Reset proficiency level
            progress.next_review_date = timezone.now().date()  # Example: set for immediate review
        else:
            return Response({'error': 'Invalid response type.'}, status=status.HTTP_400_BAD_REQUEST)

        progress.last_encounter = session
        progress.save()

        return Response({'message': 'Progress updated successfully'}, status=status.HTTP_200_OK)

def calculate_next_review_date(proficiency_level):
    # Implement your logic to calculate the next review date based on the proficiency level
    # This is where you'd implement the spaced repetition logic (e.g., SM2 algorithm)
    # For simplicity, this example just adds a number of days based on the proficiency level
    return timezone.now().date() + timezone.timedelta(days=proficiency_level)


class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, format=None):
        user = request.user
        progress_data = Progress.objects.filter(user=user)
        # Logic to compile and return progress data
        progress_serializer = ProgressSerializer(progress_data, many=True)
        return Response(progress_serializer.data)
    
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        user_data = {
            'username': user.username,
            'email': user.email
        }
        return Response(user_data)

