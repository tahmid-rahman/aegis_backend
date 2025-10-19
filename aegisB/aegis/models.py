from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta
from moviepy import VideoFileClip

import uuid
import os

User = get_user_model()


def incident_media_upload_path(instance, filename):
    date_str = timezone.now().strftime('%Y/%m/%d')
    return f'incident_media/{date_str}/{instance.incident.id}/{filename}'

class EmergencyContact(models.Model):
    RELATIONSHIP_CHOICES = [
        ('family', 'Family'),
        ('friend', 'Friend'),
        ('colleague', 'Colleague'),
        ('neighbor', 'Neighbor'),
        ('emergency_service', 'Emergency Service'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_contacts')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default='friend')
    is_emergency_contact = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'phone']
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f"{self.name} ({self.phone}) - {self.user.email}"

    def clean(self):
        # Ensure only one primary contact per user
        if self.is_primary:
            primary_exists = EmergencyContact.objects.filter(
                user=self.user, 
                is_primary=True
            ).exclude(pk=self.pk).exists()
            if primary_exists:
                raise ValidationError('User can only have one primary emergency contact.')
            
# learn 

class ResourceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='📚')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Resource Categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class LearningResource(models.Model):
    RESOURCE_TYPES = [
        ('article', 'Article'),
        ('video', 'Video'),
        ('quiz', 'Quiz'),
        ('guide', 'Guide'),
        ('tutorial', 'Tutorial'),
    ]

    DIFFICULTY_LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    title = models.CharField(max_length=200,blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True,help_text="Markdown-formatted content")
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='beginner')
    duration = models.CharField(blank=True, null=True, max_length=50, help_text="e.g., '5 min read', '10 min video'", )
    icon = models.CharField(max_length=50, default='📄',blank=True, null=True)
    category = models.ForeignKey(ResourceCategory, on_delete=models.SET_NULL, null=True, related_name='resources')
    video_url = models.URLField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to='resource_thumbnails/', blank=True, null=True)
    is_published = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    related_resources = models.ManyToManyField('self', blank=True, symmetrical=False)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

    def clean(self):
        if self.resource_type == 'video' and not self.video_url:
            raise ValidationError('Video resources must have a video URL.')


class ExternalLink(models.Model):
    resource = models.ForeignKey(LearningResource, on_delete=models.CASCADE, related_name='external_links')
    title = models.CharField(max_length=200)
    url = models.URLField()
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return f"{self.title} - {self.resource.title}"


class QuizQuestion(models.Model):
    resource = models.ForeignKey(LearningResource, on_delete=models.CASCADE, related_name='quiz_questions')
    question = models.TextField()
    explanation = models.TextField(help_text="Explanation shown after answering", blank=True, null=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q: {self.question[:50]}..."


class QuizOption(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='options')
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.text[:50]}... ({'✓' if self.is_correct else '✗'})"


class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_progress')
    resource = models.ForeignKey(LearningResource, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    progress_percentage = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    bookmarked = models.BooleanField(default=False)
    time_spent = models.IntegerField(default=0) 

    class Meta:
        unique_together = ['user', 'resource']
        verbose_name_plural = "User Progress"

    def __str__(self):
        return f"{self.user.email} - {self.resource.title}"


class UserQuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    resource = models.ForeignKey(LearningResource, on_delete=models.CASCADE)
    total_questions = models.IntegerField()
    correct_answers = models.IntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)
    answers = models.JSONField()  

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.user.email} - {self.resource.title} ({self.correct_answers}/{self.total_questions})"

    @property
    def score(self):
        return (self.correct_answers / self.total_questions) * 100 if self.total_questions else 0



# report 
class IncidentReport(models.Model):
    INCIDENT_TYPES = [
        ('harassment', 'Harassment'),
        ('robbery', 'Robbery'),
        ('assault', 'Assault'),
        ('stalking', 'Stalking'),
        ('theft', 'Theft'),
        ('vandalism', 'Vandalism'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incident_reports')
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.TextField(blank=True, null=True)
    incident_date = models.DateTimeField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_anonymous = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_incident_type_display()} - {self.title}"

    def clean(self):
        if self.incident_date and self.incident_date > timezone.now():
            raise ValidationError('Incident date cannot be in the future.')

class IncidentMedia(models.Model):
    MEDIA_TYPES = [
        ('photo', 'Photo'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('document', 'Document'),
    ]

    incident = models.ForeignKey(IncidentReport, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    file = models.FileField(upload_to=incident_media_upload_path)
    caption = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_media_type_display()} - {self.incident.title}"

class IncidentUpdate(models.Model):
    incident = models.ForeignKey(IncidentReport, on_delete=models.CASCADE, related_name='updates')
    status = models.CharField(max_length=20, choices=IncidentReport.STATUS_CHOICES)
    message = models.TextField(blank=True,null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Update for {self.incident.title}"
    

# safety check 

class SafetyCheckSettings(models.Model):
    FREQUENCY_CHOICES = [
        (30, '30 minutes'),
        (60, '1 hour'),
        (120, '2 hours'),
        (240, '4 hours'),
        (480, '8 hours'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='safety_check_settings')
    is_enabled = models.BooleanField(default=True)
    check_in_frequency = models.IntegerField(choices=FREQUENCY_CHOICES, default=60)
    notify_emergency_contacts = models.BooleanField(default=True)
    share_location = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Safety Check Settings"

    def __str__(self):
        return f"Safety Settings - {self.user.email}"

class SafetyCheckIn(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('safe', 'Safe'),
        ('missed', 'Missed'),
        ('emergency', 'Emergency'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='safety_check_ins')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    location_lat = models.FloatField(null=True, blank=True)
    location_lng = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"Check-in - {self.user.email} - {self.scheduled_at}"

    def is_overdue(self):
        if self.status != 'pending':
            return False
        return timezone.now() > self.scheduled_at + timedelta(minutes=15)

    def mark_safe(self, location_lat=None, location_lng=None, notes=''):
        self.status = 'safe'
        self.responded_at = timezone.now()
        if location_lat and location_lng:
            self.location_lat = location_lat
            self.location_lng = location_lng
        self.notes = notes
        self.save()

    def mark_missed(self):
        self.status = 'missed'
        self.save()

# class EmergencyAlert(models.Model):
#     ALERT_TYPES = [
#         ('test', 'Test Alert'),
#         ('manual', 'Manual Alert'),
#         ('auto', 'Automatic Alert'),
#     ]

#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_alerts')
#     alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
#     message = models.TextField()
#     location_lat = models.FloatField(null=True, blank=True)
#     location_lng = models.FloatField(null=True, blank=True)
#     sent_to_contacts = models.BooleanField(default=False)
#     sent_to_authorities = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"Alert - {self.user.email} - {self.alert_type}"
    

# silent capture or evedence

class VideoEvidence(models.Model):

    STATUS_CHOICES = [
        ('verified', 'Verified'),
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('rejected', 'Rejected'),
    ]

    EVIDENCE_TYPE = [
        ('harassment', 'Harassment'),
        ('robbery', 'Robbery'),
        ('assault', 'Assault'),
        ('stalking', 'Stalking'),
        ('unknown', 'Unknown'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_evidence')
    title = models.CharField(max_length=255, default='Silently Captured Evidence')
    video_file = models.FileField(upload_to='video_evidence/%Y/%m/%d/')
    location_lat = models.FloatField(null=True, blank=True)
    location_lng = models.FloatField(null=True, blank=True)
    location_address = models.TextField(blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    is_anonymous = models.BooleanField(default=False)
    duration_seconds = models.IntegerField(default=0)
    file_size = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    type = models.CharField(max_length=20, choices=EVIDENCE_TYPE, default='unknown')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-recorded_at']
        verbose_name_plural = "Video Evidence"

    def __str__(self):
        return f"{self.title} - {self.user.email} - {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"

    def clean(self):
        if self.file_size > 100 * 1024 * 1024:  
            raise ValidationError('Video file size cannot exceed 100MB')

    def save(self, *args, **kwargs):
        if self.video_file and not self.file_size:
            try:
                self.file_size = self.video_file.size
            except (ValueError, OSError):
                pass
        
        if self.video_file and (self.duration_seconds == 0 or not self.duration_seconds):
            try:
                
                if hasattr(self.video_file, 'path') and os.path.exists(self.video_file.path):
                    clip = VideoFileClip(self.video_file.path)
                    self.duration_seconds = int(clip.duration)
                    clip.close()
            except Exception as e:
                print(f"Could not get video duration: {e}")

        
        super().save(*args, **kwargs)

    def get_file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"

    def get_duration_display(self):
        if self.duration_seconds < 60:
            return f"{self.duration_seconds}s"
        elif self.duration_seconds < 3600:
            minutes = self.duration_seconds // 60
            seconds = self.duration_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = self.duration_seconds // 3600
            minutes = (self.duration_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def user_can_access(self, user):
        if user.user_type == 'controller':
            return True
        return self.user == user

    def user_can_modify(self, user):
        return self.user == user
    

# emergency alert


def generate_alert_id():
    return f"EMG-{uuid.uuid4().hex[:8].upper()}"

class EmergencyAlert(models.Model):
    ALERT_STATUS = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('resolved', 'Resolved'),
        ('false_alarm', 'False Alarm'),
    ]
    
    ACTIVATION_METHODS = [
        ('button', 'Button Press'),
        ('shake', 'Shake Detection'),
        ('power_press', 'Power Button Press'),
        ('voice', 'Voice Command'),
        ('manual', 'Manual Activation'),
    ]
    
    # Core alert information
    alert_id = models.CharField(max_length=20, unique=True, default=generate_alert_id)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_alerts')
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='active')
    activation_method = models.CharField(max_length=20, choices=ACTIVATION_METHODS, default='button')
    is_silent = models.BooleanField(default=False)
    
    # Location data
    initial_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    initial_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    initial_address = models.TextField(blank=True)
    
    # Timestamps
    # created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    # Emergency details
    severity_level = models.CharField(max_length=20, default='medium', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ])
    emergency_type = models.CharField(max_length=50, blank=True, default='general')
    description = models.TextField(blank=True)
    
    # Security features
    fake_screen_active = models.BooleanField(default=True)
    deactivation_attempts = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-activated_at']
        indexes = [
            models.Index(fields=['status', 'activated_at']),
            models.Index(fields=['user', 'activated_at']),
        ]
    
    def __str__(self):
        return f"{self.alert_id} - {self.user.email} - {self.status}"

class LocationUpdate(models.Model):
    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, related_name='location_updates')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(null=True, blank=True, help_text="GPS accuracy in meters")
    speed = models.FloatField(null=True, blank=True, help_text="Speed in m/s")
    altitude = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(360)])
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['alert', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Location for {self.alert.alert_id} at {self.timestamp}"

def media_upload_path(instance, filename):
    """
    Example: emergency/EMG-ABC12345/filename.jpg
    """
    import os
    ext = filename.split('.')[-1]
    secure_name = f"{instance.alert.alert_id}_{int(timezone.now().timestamp())}.{ext}"
    return os.path.join('emergency', instance.alert.alert_id, secure_name)

class MediaCapture(models.Model):
    MEDIA_TYPES = [
        ('audio', 'Audio Recording'),
        ('photo', 'Photo'),
        ('video', 'Video'),
    ]
    
    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, related_name='media_captures')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    file = models.FileField(upload_to=media_upload_path, blank=False, null=False)
    file_size = models.BigIntegerField(default=0, help_text="Size in bytes")
    duration = models.IntegerField(null=True, blank=True, help_text="For audio/video in seconds")
    captured_at = models.DateTimeField(default=timezone.now)
    
    # Security & metadata
    is_encrypted = models.BooleanField(default=True)
    encryption_key = models.TextField(blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    resolution = models.CharField(max_length=20, blank=True, help_text="e.g., 1920x1080")
    
    class Meta:
        ordering = ['-captured_at']
    
    def __str__(self):
        return f"{self.media_type} for {self.alert.alert_id}"

class EmergencyResponse(models.Model):
    RESPONSE_STATUS = [
        ('notified', 'Notified'),
        ('dispatched', 'Dispatched'),
        ('accepted', 'Accepted'),
        ('en_route', 'En Route'),
        ('on_scene', 'On Scene'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, related_name='responses')
    responder = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'agent'})
    status = models.CharField(max_length=20, choices=RESPONSE_STATUS, default='notified')
    eta_minutes = models.IntegerField(null=True, blank=True, help_text="Estimated arrival time in minutes")
    
    # Timestamps
    notified_at = models.DateTimeField(default=timezone.now)
    accepted_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Response details
    notes = models.TextField(blank=True)
    rating = models.FloatField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['alert', 'responder']
        ordering = ['notified_at']
    
    def __str__(self):
        return f"{self.responder.email} - {self.alert.alert_id} - {self.status}"

class DeactivationAttempt(models.Model):
    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, related_name='deactivatation_attempt_logs')
    attempted_pin = models.CharField(max_length=6)
    is_successful = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(default=timezone.now)
    device_info = models.JSONField(default=dict, blank=True)
    location_at_attempt = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-attempted_at']
    
    def __str__(self):
        status = "Successful" if self.is_successful else "Failed"
        return f"{status} deactivation attempt for {self.alert.alert_id}"

class EmergencyNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('alert_activated', 'Alert Activated'),
        ('responder_assigned', 'Responder Assigned'),
        ('status_update', 'Status Update'),
        ('location_update', 'Location Update'),
        ('media_uploaded', 'Media Uploaded'),
        ('alert_resolved', 'Alert Resolved'),
        ('alert_test', 'Test Alert'),
        ('safety_check', 'Safety Check'),
        ('update_profile', 'Profile Updated'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    by_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200,null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    is_read = models.BooleanField(default=False,null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    # Additional data
    data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} - {self.user.email}"
    



class EmergencyIncidentReport(models.Model):
    INCIDENT_TYPES = [
        ('harassment', 'Harassment'),
        ('robbery', 'Robbery'), 
        ('stalking', 'Stalking'),
        ('assault', 'Assault'),
        ('other', 'Other'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    VICTIM_CONDITIONS = [
        ('safe', 'Safe & Stable'),
        ('injured', 'Minor Injuries'),
        ('serious', 'Serious Injuries'),
        ('traumatized', 'Emotional Trauma'),
        ('unknown', 'Condition Unknown'),
    ]
    
    # Core relationships
    emergency = models.ForeignKey(
        'EmergencyAlert', 
        on_delete=models.CASCADE,
        related_name='emergency_incident_reports'
    )
    agent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='emergency_incident_reports'
    )
    
    # Basic information
    incident_type = models.CharField(
        max_length=20,
        choices=INCIDENT_TYPES,
        default='harassment'
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_LEVELS, 
        default='medium'
    )
    location = models.TextField()
    
    # Victim details
    victim_condition = models.CharField(
        max_length=20,
        choices=VICTIM_CONDITIONS,
        default='unknown'
    )
    victim_gender = models.CharField(max_length=20, blank=True)
    victim_age = models.IntegerField(null=True, blank=True)
    is_anonymous = models.BooleanField(default=False)
    
    # Incident details
    perpetrator_info = models.TextField(null=True, blank=True)
    actions_taken = models.TextField(null=True, blank=True)
    
    # Services involved
    police_involved = models.BooleanField(default=False)
    medical_assistance = models.BooleanField(default=False) 
    ngo_involved = models.BooleanField(default=False)
    
    # Evidence
    evidence_collected = models.BooleanField(default=False)
    additional_notes = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_details = models.TextField(blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
        ],
        default='draft'
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Incident Report - {self.emergency.alert_id}"

class EmergencyReportEvidence(models.Model):
    report = models.ForeignKey(
        EmergencyIncidentReport,
        on_delete=models.CASCADE,
        related_name='emergency_report_evidence'
    )
    file = models.FileField(upload_to='incident_evidence/%Y/%m/%d/')
    file_type = models.CharField(max_length=10)
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Evidence for {self.report.emergency.alert_id}"
    



# safe route


class SafeLocation(models.Model):
    LOCATION_TYPES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('education', 'Education'),
        ('family', 'Family'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='safe_locations')
    name = models.CharField(max_length=100)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='other')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.user.email}"

class SafeRoute(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='safe_routes')
    destination = models.CharField(max_length=255)
    route_data = models.JSONField(default=dict)
    avoided_locations = models.JSONField(default=list)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Route to {self.destination} - {self.user.email}"

class NavigationSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='navigation_sessions')
    route = models.ForeignKey(SafeRoute, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    live_location_updates = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Navigation - {self.user.email} - {self.started_at}"