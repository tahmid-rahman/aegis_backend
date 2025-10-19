from django.contrib import admin
from . import models

admin.site.register(models.CustomUser)
admin.site.register(models.EmergencyAssignment)
admin.site.register(models.SafetyScore)

# Register your models here.
