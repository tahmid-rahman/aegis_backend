from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from .managers import CustomUserManager
from django.utils import timezone

class CustomUser(AbstractUser):
    USER_TYPES = [
        ('user', 'User'),
        ('agent', 'Agent'),
        ('controller', 'Controller'),
        ('admin', 'Admin'),
    ]

    RESPONDER_TYPES = [
        ('police', 'Police'),
        ('ngo', 'NGO'),
        ('medical', 'Medical'),
        ('volunteer', 'Volunteer'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('offline', 'Offline'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    ID_TYPE_CHOICES = [
        ('nid', 'National ID (NID)'),
        ('birth', 'Birth Certificate'),
    ]

    # Remove username and first/last name
    username = None
    first_name = None
    last_name = None

    # Basic user fields
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='user')
    
    # Agent/Responder specific fields
    agent_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    responder_type = models.CharField(max_length=10, choices=RESPONDER_TYPES, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='offline')
    badge_number = models.CharField(max_length=20, blank=True, null=True)
    specialization = models.JSONField(default=list, blank=True)  # Store as list of strings
    rating = models.FloatField(default=0.0)
    total_cases = models.IntegerField(default=0)
    last_active = models.DateTimeField(auto_now=True)
    
    # Location fields
    location = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    
    # Personal information
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    phone = models.CharField(max_length=20, blank=True)
    id_type = models.CharField(max_length=10, choices=ID_TYPE_CHOICES, default='nid')
    id_number = models.CharField(max_length=50, blank=True)
    dob = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    emergency_medical_note = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    last_password_change = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] 

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    @property
    def name(self):
        return self.full_name

    def clean(self):
        if self.user_type == 'agent' and not self.agent_id:
            raise ValidationError({'agent_id': 'Agent ID is required for agent users.'})

        if self.user_type == 'user' and self.agent_id:
            raise ValidationError({'agent_id': 'Agent ID should not be provided for regular users.'})

        if self.user_type == 'agent' and not self.responder_type:
            raise ValidationError({'responder_type': 'Responder type is required for agent users.'})

    def save(self, *args, **kwargs):
        self.clean()

        if self.pk:
            old_user = CustomUser.objects.get(pk=self.pk)
            if self.password != old_user.password:
                self.password_changed_at = timezone.now()

        super().save(*args, **kwargs)


class EmergencyAssignment(models.Model):
    agent = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'agent'})
    emergency_id = models.CharField(max_length=20)
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('assigned', 'Assigned'),
        ('en_route', 'En Route'),
        ('on_scene', 'On Scene'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='assigned')
    
    class Meta:
        db_table = 'emergency_assignments'




class SafetyScore(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='safety_scores'
    )
    score = models.IntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ],
        help_text="Safety score from 0 to 100",
        default=100
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.score}/100"