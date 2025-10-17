
from django.test import TestCase
from django.core.exceptions import ValidationError
from ..models import CustomUser, EmergencyAssignment

class CustomUserModelTest(TestCase):
    def test_create_user(self):
        user = CustomUser.objects.create_user(
            email='test@example.com',
            password='password123',
            full_name='Test User'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('password123'))
        self.assertEqual(user.full_name, 'Test User')
        self.assertEqual(user.user_type, 'user')

#    def test_create_superuser(self):
#        admin_user = CustomUser.objects.create_superuser(
#            email='admin@example.com',
#            password='password123',
#            full_name='Admin User'
#        )
#        self.assertEqual(admin_user.email, 'admin@example.com')
#        self.assertTrue(admin_user.check_password('password123'))
#        self.assertEqual(admin_user.full_name, 'Admin User')
#        self.assertTrue(admin_user.is_staff)
#        self.assertTrue(admin_user.is_superuser)
#        self.assertEqual(admin_user.user_type, 'admin')

    def test_user_string_representation(self):
        user = CustomUser.objects.create_user(
            email='test@example.com',
            password='password123',
            full_name='Test User'
        )
        self.assertEqual(str(user), 'test@example.com')

    def test_user_name_property(self):
        user = CustomUser.objects.create_user(
            email='test@example.com',
            password='password123',
            full_name='Test User'
        )
        self.assertEqual(user.name, 'Test User')

    def test_agent_requires_agent_id(self):
        with self.assertRaises(ValidationError):
            CustomUser.objects.create_user(
                email='agent@example.com',
                password='password123',
                full_name='Agent User',
                user_type='agent'
            ).clean()

    def test_user_cannot_have_agent_id(self):
        with self.assertRaises(ValidationError):
            CustomUser.objects.create_user(
                email='user@example.com',
                password='password123',
                full_name='Regular User',
                agent_id='AGENT007'
            ).clean()

    def test_agent_requires_responder_type(self):
        with self.assertRaises(ValidationError):
            CustomUser.objects.create_user(
                email='agent@example.com',
                password='password123',
                full_name='Agent User',
                user_type='agent',
                agent_id='AGENT007'
            ).clean()


class EmergencyAssignmentModelTest(TestCase):
    def setUp(self):
        self.agent = CustomUser.objects.create_user(
            email='agent@example.com',
            password='password123',
            full_name='Agent User',
            user_type='agent',
            agent_id='AGENT007',
            responder_type='police'
        )

    def test_create_emergency_assignment(self):
        assignment = EmergencyAssignment.objects.create(
            agent=self.agent,
            emergency_id='EMG-12345'
        )
        self.assertEqual(assignment.agent, self.agent)
        self.assertEqual(assignment.emergency_id, 'EMG-12345')
        self.assertEqual(assignment.status, 'assigned')
        self.assertIsNotNone(assignment.assigned_at)
