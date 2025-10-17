
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from accounts.models import CustomUser
from ..models import (
    EmergencyContact, ResourceCategory, LearningResource, IncidentReport, 
    SafetyCheckSettings, EmergencyAlert, VideoEvidence, SafeLocation, 
    SafeRoute, NavigationSession
)
from ..serializers import (
    EmergencyContactSerializer, ResourceCategorySerializer, LearningResourceSerializer, 
    IncidentReportSerializer, SafetyCheckSettingsSerializer, EmergencyAlertSerializer, 
    VideoEvidenceSerializer, SafeLocationSerializer, SafeRouteSerializer, 
    NavigationSessionSerializer
)

class AegisSerializersTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='password123',
            full_name='Test User'
        )
        self.factory = APIRequestFactory()
        self.request = self.factory.get('/')
        self.request.user = self.user

    def test_emergency_contact_serializer(self):
        contact = EmergencyContact.objects.create(
            user=self.user,
            name='John Doe',
            phone='1234567890'
        )
        serializer = EmergencyContactSerializer(instance=contact)
        data = serializer.data
        self.assertEqual(data['name'], 'John Doe')

    def test_resource_category_serializer(self):
        category = ResourceCategory.objects.create(name='Test Category')
        serializer = ResourceCategorySerializer(instance=category)
        data = serializer.data
        self.assertEqual(data['name'], 'Test Category')

    def test_learning_resource_serializer(self):
        category = ResourceCategory.objects.create(name='Test Category')
        resource = LearningResource.objects.create(
            title='Test Resource',
            resource_type='article',
            category=category
        )
        serializer = LearningResourceSerializer(instance=resource, context={'request': self.request})
        data = serializer.data
        self.assertEqual(data['title'], 'Test Resource')

    def test_incident_report_serializer(self):
        incident = IncidentReport.objects.create(
            user=self.user,
            incident_type='other',
            title='Test Incident',
            description='Test description',
            incident_date='2025-10-17T12:00:00Z'
        )
        serializer = IncidentReportSerializer(instance=incident)
        data = serializer.data
        self.assertEqual(data['title'], 'Test Incident')

    def test_safety_check_settings_serializer(self):
        settings = SafetyCheckSettings.objects.create(user=self.user)
        serializer = SafetyCheckSettingsSerializer(instance=settings)
        data = serializer.data
        self.assertTrue('is_enabled' in data)

    def test_emergency_alert_serializer(self):
        alert = EmergencyAlert.objects.create(user=self.user)
        serializer = EmergencyAlertSerializer(instance=alert)
        data = serializer.data
        self.assertIn('EMG-', data['alert_id'])

    def test_video_evidence_serializer(self):
        evidence = VideoEvidence.objects.create(user=self.user)
        serializer = VideoEvidenceSerializer(instance=evidence, context={'request': self.request})
        data = serializer.data
        self.assertTrue('title' in data)

    def test_safe_location_serializer(self):
        location = SafeLocation.objects.create(
            user=self.user,
            name='Home',
            address='123 Main St'
        )
        serializer = SafeLocationSerializer(instance=location, context={'request': self.request})
        data = serializer.data
        self.assertEqual(data['name'], 'Home')

    def test_safe_route_serializer(self):
        route = SafeRoute.objects.create(
            user=self.user,
            destination='Work'
        )
        serializer = SafeRouteSerializer(instance=route, context={'request': self.request})
        data = serializer.data
        self.assertEqual(data['destination'], 'Work')

    def test_navigation_session_serializer(self):
        session = NavigationSession.objects.create(user=self.user)
        serializer = NavigationSessionSerializer(instance=session)
        data = serializer.data
        self.assertTrue('is_active' in data)
