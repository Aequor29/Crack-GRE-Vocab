from django.contrib import admin

# Register your models here.
from .models import Word, Definition, Session, Progress

admin.site.register(Word)
admin.site.register(Definition)
admin.site.register(Session)
admin.site.register(Progress)