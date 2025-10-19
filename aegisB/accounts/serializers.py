# serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate, password_validation
from .models import CustomUser, EmergencyAssignment, SafetyScore
from datetime import date

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = CustomUser
        fields = ('id', 'name', 'email', 'password', 'user_type', 'agent_id', 
                  'responder_type', 'status', 'badge_number', 'specialization',
                  'rating', 'total_cases', 'location', 'latitude', 'longitude',
                  'gender', 'phone', 'id_type', 'id_number', 'dob', 'blood_group',
                  'address', 'emergency_medical_note', 'last_active')
    
    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_dob(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value
    
    def validate(self, data):
        user_type = data.get('user_type', 'user')
        agent_id = data.get('agent_id')
        responder_type = data.get('responder_type')
        
        if user_type == 'agent':
            if not agent_id:
                raise serializers.ValidationError({"agent_id": "Agent ID is required for agent users."})
            if not responder_type:
                raise serializers.ValidationError({"responder_type": "Responder type is required for agent users."})
        
        if user_type == 'user' and agent_id:
            raise serializers.ValidationError({"agent_id": "Agent ID should not be provided for regular users."})
        
        return data
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

class ResponderSerializer(serializers.ModelSerializer):

    assigned_emergency = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ('id', 'name', 'email', 'agent_id', 'responder_type', 'status',
                  'badge_number', 'phone', 'email', 'location', 'specialization',
                  'rating', 'total_cases', 'last_active', 'assigned_emergency',
                  'latitude', 'longitude', 'profile_picture')
    
    def get_assigned_emergency(self, obj):
        # Get current active emergency assignment
        assignment = EmergencyAssignment.objects.filter(
            agent=obj, 
            status__in=['assigned', 'en_route', 'on_scene']
        ).first()
        return assignment.emergency_id if assignment else None

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    agent_id = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        agent_id = data.get('agent_id')
        
        if not email or not password:
            raise serializers.ValidationError("Must provide both email and password.")
        
        user = authenticate(username=email, password=password)
        
        if not user:
            raise serializers.ValidationError("Unable to log in with provided credentials.")
        
        # Agent-specific checks
        if user.user_type == 'agent':
            if not agent_id:
                raise serializers.ValidationError("Agent ID is required for agent login.")
            if user.agent_id != agent_id:
                raise serializers.ValidationError("Invalid agent ID.")
        
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        
        data['user'] = user
        return data

class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', required=False)
    class Meta:
        model = CustomUser
        fields = ('id', 'name', 'email', 'user_type', 'agent_id', 'responder_type',
                  'status', 'badge_number', 'specialization', 'rating', 'total_cases',
                  'gender', 'phone', 'id_type', 'id_number', 'dob', 'blood_group',
                  'address', 'emergency_medical_note', 'profile_picture', 'location',
                  'latitude', 'longitude', 'last_active')
        read_only_fields = ('email', 'user_type', 'agent_id', 'rating', 'total_cases')

class ProfilePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('profile_picture',)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True, 
        min_length=6, 
        write_only=True
    )
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "The new passwords do not match."})
        
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError(
                {"new_password": "New password cannot be the same as your current password."}
            )
        
        return data
    


class SafetyScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyScore
        fields = '__all__'