from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import update_session_auth_hash, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
from .models import CustomUser, SafetyScore
from .serializers import PasswordChangeSerializer, ResponderSerializer, SafetyScoreSerializer, UserSerializer, LoginSerializer, UserProfileSerializer,ProfilePictureSerializer
from . import serializers

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Create token for the new user
        token, created = Token.objects.get_or_create(user=user)

        try:
            safety_score = SafetyScore.objects.create(
                user=user,
            )
        except Exception as e:
            print(f"Error creating safety score: {e}")
        
        print('User registered:', user.email)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key,
            'message': 'User created successfully'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        
        # Get or create token
        token, created = Token.objects.get_or_create(user=user)
        print('User logged in:', user.email)

        return Response({
            'user': UserSerializer(user).data,
            'token': token.key,
            'message': 'Login successful'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_user(request):
    try:
        logout(request)
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except:
        return Response(status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    user = request.user
    
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        print("Received update data:", request.data)
        serializer = UserProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'user': serializer.data,
                'message': 'Profile updated success'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH','POST'])
@permission_classes([IsAuthenticated])
def update_profile_picture(request):

    user = request.user
    serializer = ProfilePictureSerializer(user, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        # Return full user data with updated profile picture
        user_serializer = UserProfileSerializer(user)
        return Response({
            'user': user_serializer.data,
            'message': 'Profile picture updated successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_profile_picture(request):
    """Delete user profile picture"""
    user = request.user
    
    # Delete the profile picture file if it exists
    if user.profile_picture:
        user.profile_picture.delete(save=False)
    
    # Clear the profile picture field
    user.profile_picture = None
    user.save()
    
    serializer = UserProfileSerializer(user)
    return Response({
        'user': serializer.data,
        'message': 'Profile picture removed successfully'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_auth_status(request):
    user = request.user
    return Response({
        'authenticated': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'user_type': user.user_type
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_responders(request):

    responders = CustomUser.objects.filter(user_type='agent').order_by('-last_active')
    
    # Apply filters
    status_filter = request.GET.get('status', 'all')
    type_filter = request.GET.get('type', 'all')
    search_term = request.GET.get('search', '')
    
    if status_filter != 'all':
        responders = responders.filter(status=status_filter)
    
    if type_filter != 'all':
        responders = responders.filter(responder_type=type_filter)
    
    if search_term:
        responders = responders.filter(
            models.Q(full_name__icontains=search_term) |
            models.Q(agent_id__icontains=search_term) |
            models.Q(badge_number__icontains=search_term)
        )
    
    serializer = ResponderSerializer(responders, many=True)
    return Response(serializer.data)

# @api_view(['PATCH'])
# @permission_classes([IsAuthenticated])
# def update_responder_status(request, responder_id):
#     """Update responder status (available, busy, offline)"""
#     try:
#         responder = CustomUser.objects.get(id=responder_id, user_type='agent')
#     except CustomUser.DoesNotExist:
#         return Response({'error': 'Responder not found'}, status=404)
    
#     serializer = ResponderSerializer(responder, data=request.data, partial=True)
#     if serializer.is_valid():
#         serializer.save()
#         return Response({
#             'responder': serializer.data,
#             'message': 'Status updated successfully'
#         })
    
#     return Response(serializer.errors, status=400)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_responder_status(request, responder_id):
    """Update responder status (available, busy, offline) and handle location fields accordingly"""
    try:
        responder = CustomUser.objects.get(id=responder_id, user_type='agent')
    except CustomUser.DoesNotExist:
        return Response({'error': 'Responder not found'}, status=404)

    # Extract status before validation
    new_status = request.data.get('status')

    # Update location if available/busy; otherwise clear them
    if new_status in ['available', 'busy']:
        location_data = {
            'location': request.data.get('location', responder.location),
            'latitude': request.data.get('latitude', responder.latitude),
            'longitude': request.data.get('longitude', responder.longitude),
        }
    else:  # status == 'offline' or anything else invalid
        location_data = {'location': '', 'latitude': None, 'longitude': None}

    # Merge updates into request data
    mutable_data = request.data.copy()
    mutable_data.update(location_data)

    serializer = ResponderSerializer(responder, data=mutable_data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'responder': serializer.data,
            'message': f"Status updated to '{new_status}' successfully"
        })

    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        try:
            user = request.user
            new_password = serializer.validated_data['new_password']
            
            # Set new password without complex validation
            user.set_password(new_password)
            user.password_changed_at = timezone.now()
            user.save()
            
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            
            return Response({
                'message': 'Password changed successfully',
                'detail': 'Your password has been updated. Please use your new password for future logins.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error changing password for user {request.user.email}: {str(e)}")
            return Response(
                {'error': 'An error occurred while changing your password. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# safety score 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_safety_score(request):
    serializer = SafetyScoreSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_safety_scores(request):
    scores = SafetyScore.objects.all()
    serializer = SafetyScoreSerializer(scores, many=True)
    return Response(serializer.data)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def sub_safety_score(request):
    try:
        score_instance = SafetyScore.objects.get(user=request.user)

        # Decrease score by 5
        new_score = max(score_instance.score - 5, 0) 
        score_instance.score = new_score
        score_instance.save()

        serializer = SafetyScoreSerializer(score_instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except SafetyScore.DoesNotExist:
        return Response(
            {"error": "Safety score not found"},
            status=status.HTTP_404_NOT_FOUND
        ) 
    

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def add_safety_score(request):
    try:
        score_instance = SafetyScore.objects.get(user=request.user)

        new_score = min(score_instance.score + 1, 100)  
        score_instance.score = new_score
        score_instance.save()

        serializer = SafetyScoreSerializer(score_instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except SafetyScore.DoesNotExist:
        return Response(
            {"error": "Safety score not found"},
            status=status.HTTP_404_NOT_FOUND
        )




@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_safety_score(request):
    try:
        score = SafetyScore.objects.get(user=request.user)
        score.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except SafetyScore.DoesNotExist:
        return Response(
            {"error": "Safety score not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_safety_score(request):
    try:
        score = SafetyScore.objects.get(user=request.user)
        serializer = SafetyScoreSerializer(score)
        return Response(serializer.data)
    except SafetyScore.DoesNotExist:
        return Response(
            {"error": "Safety score not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    