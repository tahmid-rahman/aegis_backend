
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import CustomUser
from ..models import (
    EmergencyContact, ResourceCategory, LearningResource, ExternalLink, 
    QuizQuestion, QuizOption, UserProgress, UserQuizAttempt, IncidentReport, 
    IncidentMedia, IncidentUpdate, SafetyCheckSettings, SafetyCheckIn, 
    VideoEvidence, EmergencyAlert, LocationUpdate, MediaCapture, 
    EmergencyResponse, DeactivationAttempt, EmergencyNotification, 
    EmergencyIncidentReport, EmergencyReportEvidence, SafeLocation, 
    SafeRoute, NavigationSession
)

class AegisModelsTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='password123',
            full_name='Test User'
        )

    def test_emergency_contact(self):
        contact = EmergencyContact.objects.create(
            user=self.user,
            name='John Doe',
            phone='1234567890'
        )
        self.assertEqual(str(contact), f'John Doe (1234567890) - {self.user.email}')

    def test_resource_category(self):
        category = ResourceCategory.objects.create(name='Test Category')
        self.assertEqual(str(category), 'Test Category')

    def test_learning_resource(self):
        category = ResourceCategory.objects.create(name='Test Category')
        resource = LearningResource.objects.create(
            title='Test Resource',
            resource_type='article',
            category=category
        )
        self.assertEqual(str(resource), 'Test Resource')

    def test_incident_report(self):
        report = IncidentReport.objects.create(
            user=self.user,
            incident_type='other',
            title='Test Incident',
            description='Test description',
            incident_date=timezone.now()
        )
        self.assertEqual(str(report), 'Other - Test Incident')

    def test_safety_check_settings(self):
        settings = SafetyCheckSettings.objects.create(user=self.user)
        self.assertEqual(str(settings), f'Safety Settings - {self.user.email}')

    def test_emergency_alert(self):
        alert = EmergencyAlert.objects.create(user=self.user)
        self.assertIn('EMG-', alert.alert_id)

    def test_safe_location(self):
        location = SafeLocation.objects.create(
            user=self.user,
            name='Home',
            address='123 Main St'
        )
        self.assertEqual(str(location), f'Home - {self.user.email}')
