from rest_framework import serializers
from .models import Word, Progress,Definition

class DefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Definition
        fields = ['definition', 'part_of_speech', 'usage_example']

class WordSerializer(serializers.ModelSerializer):
    definitions = DefinitionSerializer(many=True, read_only=True, source='definition_set')

    class Meta:
        model = Word
        fields = ['id', 'word', 'pronunciation', 'definitions']
    
class ProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progress
        fields = ['user', 'word', 'proficiency_level', 'next_review_date', 'last_encounter']
