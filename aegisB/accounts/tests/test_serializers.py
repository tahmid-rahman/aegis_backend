
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from ..serializers import (
    UserSerializer, 
    ResponderSerializer, 
    LoginSerializer, 
    UserProfileSerializer, 
    PasswordChangeSerializer
)
from ..models import CustomUser, EmergencyAssignment

class SerializersTest(TestCase):
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'password': 'password123',
            'full_name': 'Test User'
        }
        self.user = CustomUser.objects.create_user(**self.user_data)

        self.agent_data = {
            'email': 'agent@example.com',
            'password': 'password123',
            'full_name': 'Agent User',
            'user_type': 'agent',
            'agent_id': 'AGENT007',
            'responder_type': 'police'
        }
        self.agent = CustomUser.objects.create_user(**self.agent_data)

    def test_user_serializer(self):
        serializer = UserSerializer(instance=self.user)
        data = serializer.data
        self.assertEqual(data['email'], self.user.email)
        self.assertEqual(data['name'], self.user.full_name)

    def test_responder_serializer(self):
        serializer = ResponderSerializer(instance=self.agent)
        data = serializer.data
        self.assertEqual(data['email'], self.agent.email)
        self.assertEqual(data['agent_id'], self.agent.agent_id)

    def test_login_serializer(self):
        data = {
            'email': 'test@example.com',
            'password': 'password123'
        }
        serializer = LoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_user_profile_serializer(self):
        serializer = UserProfileSerializer(instance=self.user)
        data = serializer.data
        self.assertEqual(data['email'], self.user.email)

    def test_password_change_serializer(self):
        factory = APIRequestFactory()
        request = factory.post('/change-password/')
        request.user = self.user

        data = {
            'old_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        serializer = PasswordChangeSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid())
