import csv
import requests
from django.core.management.base import BaseCommand
from vocab_backend.models import Word, Definition
from django.db import transaction

class Command(BaseCommand):
    help = 'Import words from a CSV file'

    def fetch_word_data(self, word):
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def populate_database_from_csv(self, csv_file_path):
        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Check if the word already exists in the database
                word, created = Word.objects.get_or_create(word=row['word'])
                if created:
                    # Only fetch word data from API if the word was newly created
                    print(word)
                    word_data = self.fetch_word_data(row['word'])
                    if word_data:
                        with transaction.atomic():
                            word.pronunciation = word_data[0].get('phonetic', '')
                            word.save()
                            for meaning in word_data[0]['meanings']:
                                for definition in meaning['definitions']:
                                    def_entry = Definition(
                                        word=word,
                                        definition=definition['definition'],
                                        part_of_speech=meaning['partOfSpeech'],
                                        usage_example=definition.get('example', '')
                                    )
                                    def_entry.save()

    def handle(self, *args, **options):
        csv_file_path = './data/GRE_word.csv'
        self.populate_database_from_csv(csv_file_path)

