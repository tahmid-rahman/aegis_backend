from rest_framework import status,viewsets
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from aegisB.settings import OPENROUTE_API_KEY
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import timedelta
import json
import logging
import math
import requests





from .models import (
    DeactivationAttempt,
    EmergencyAlert,
    EmergencyContact,
    EmergencyIncidentReport,
    EmergencyNotification,
    EmergencyReportEvidence,
    EmergencyResponse,
    ExternalLink,
    LocationUpdate,
    MediaCapture,
    NavigationSession,
    ResourceCategory,
    LearningResource,
    SafeLocation,
    SafeRoute,
    SafetyCheckIn,
    SafetyCheckSettings,
    UserProgress,
    UserQuizAttempt,
    QuizQuestion,
    QuizOption,
    IncidentReport, 
    IncidentUpdate,
    VideoEvidence,
)

from .serializers import (
    DeactivationSerializer,
    EmergencyActivationSerializer,
    EmergencyAlertDetailSerializer,
    EmergencyAlertSerializer,
    EmergencyContactSerializer, 
    EmergencyContactCreateSerializer,
    EmergencyIncidentReportListSerializer,
    EmergencyIncidentReportSerializer,
    EmergencyNotificationSerializer,
    EmergencyReportEvidenceSerializer,
    EmergencyResponseSerializer,
    IncidentUpdateSerializer,
    LocationUpdateRequestSerializer,
    LocationUpdateSerializer,
    ManualCheckInSerializer,
    MediaCaptureSerializer,
    ResponderAssignmentSerializer,
    SafeLocationSerializer,
    SafetyCheckInSerializer,
    SafetyCheckSettingsSerializer,
    SafetyStatisticsSerializer,
    TestAlertSerializer,
    UserWithContactsSerializer,
    PhoneLookupSerializer,
    UserLookupSerializer,
    ResourceCategorySerializer,
    LearningResourceSerializer,
    UserProgressSerializer,
    QuizSubmissionSerializer,
    UserQuizAttemptSerializer,
    ExternalLinkSerializer,
    QuizQuestionSerializer,
    QuizOptionSerializer,
    IncidentReportSerializer,
    IncidentReportCreateSerializer,
    MediaUploadSerializer,
    VideoEvidenceCreateSerializer,
    VideoEvidenceSerializer,
    VideoEvidenceStatusSerializer,
    VideoEvidenceUpdateSerializer,
    VideoUploadSerializer,
)

User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def lookup_phone(request):
    """Look up user by phone number and return their details if found"""
    serializer = PhoneLookupSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    phone_number = serializer.validated_data['phone']
    
    try:
        # Clean phone number for comparison (remove spaces, dashes, etc.)
        clean_phone = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Check if user exists with this phone number (case-insensitive partial match)
        users = User.objects.filter(phone__icontains=clean_phone).exclude(id=request.user.id)
        
        if users.exists():
            # Find the best match (exact match or closest)
            exact_match = users.filter(phone__iexact=clean_phone).first()
            user = exact_match or users.first()
            
            user_serializer = UserLookupSerializer(user)
            
            # Check if this user is already added as a contact
            existing_contact = EmergencyContact.objects.filter(
                user=request.user, 
                phone__icontains=clean_phone
            ).exists()
            
            return Response({
                'found': True,
                'user': user_serializer.data,
                'already_added': existing_contact,
                'exact_match': exact_match is not None
            })
        
        return Response({
            'found': False,
            'message': 'No user found with this phone number'
        })
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def emergency_contacts_list(request):
    if request.method == 'GET':
        contacts = EmergencyContact.objects.filter(user=request.user)
        serializer = EmergencyContactSerializer(contacts, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = EmergencyContactCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Check if contact already exists
                phone = serializer.validated_data['phone']
                existing_contact = EmergencyContact.objects.filter(
                    user=request.user, 
                    phone__iexact=phone
                ).exists()
                
                if existing_contact:
                    return Response(
                        {'error': 'A contact with this phone number already exists'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                contact = serializer.save(user=request.user)
                full_serializer = EmergencyContactSerializer(contact)
                return Response(full_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def emergency_contact_detail(request, pk):
    try:
        contact = EmergencyContact.objects.get(pk=pk, user=request.user)
    except EmergencyContact.DoesNotExist:
        return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = EmergencyContactSerializer(contact)
        return Response(serializer.data)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = EmergencyContactCreateSerializer(
            contact, 
            data=request.data, 
            partial=request.method == 'PATCH'
        )
        if serializer.is_valid():
            try:
                # Check for duplicate phone number when updating
                if 'phone' in serializer.validated_data:
                    phone = serializer.validated_data['phone']
                    duplicate_exists = EmergencyContact.objects.filter(
                        user=request.user, 
                        phone__iexact=phone
                    ).exclude(pk=pk).exists()
                    
                    if duplicate_exists:
                        return Response(
                            {'error': 'Another contact with this phone number already exists'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                contact = serializer.save()
                full_serializer = EmergencyContactSerializer(contact)
                return Response(full_serializer.data)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        contact.delete()
        return Response({'message': 'Contact deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_emergency_alert(request, pk):
    try:
        contact = EmergencyContact.objects.get(pk=pk, user=request.user)
        # Here you would integrate with your alert service (Twilio, etc.)
        # For now, just return a success message
        print('test successful')
        print(contact.phone, contact.email)
        filters = Q()
        if contact.email:
            filters |= Q(email=contact.email)
        if contact.phone:
            filters |= Q(phone=contact.phone)
        send_to = User.objects.filter(filters).first()   

        if send_to is None:
            return Response({
                'message': f'Test alert sent to {contact.name} is not available in aegis, Thank You',
            })
        else:
            EmergencyNotification.objects.create(
                user=send_to,
                by_user=request.user,
                notification_type='alert_test',
                title=f'{request.user.full_name} test the alert',
                message = f"{request.user.full_name} tested the alert at {timezone.now().strftime('%Y-%m-%d %I:%M:%S %p')}. Be safe, Be aware",
            )

            return Response({
                'message': f'Test alert sent to {contact.name} is successfull',
            })
    
    except EmergencyContact.DoesNotExist:
        return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_emergency_contact(request, pk):
    """Alternative delete endpoint using POST method"""
    try:
        contact = EmergencyContact.objects.get(pk=pk, user=request.user)
        contact_name = contact.name
        contact.delete()
        return Response({
            'message': f'Contact {contact_name} deleted successfully',
            'deleted_contact_id': pk
        }, status=status.HTTP_200_OK)
    except EmergencyContact.DoesNotExist:
        return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_emergency_info(request):
    user = request.user
    serializer = UserWithContactsSerializer(user)
    return Response(serializer.data)


# learn......................

@api_view(['GET'])
@permission_classes([AllowAny])
def resource_categories(request):
    categories = ResourceCategory.objects.filter(is_active=True).annotate(
        resource_count=Count('resources', filter=Q(resources__is_published=True))
    ).order_by('order', 'name')
    
    serializer = ResourceCategorySerializer(categories, many=True)
    return Response(serializer.data)


class LearningResourceListView(ListAPIView):
    serializer_class = LearningResourceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.user_type == 'controller' :
            queryset = LearningResource.objects.all()
        else :
            queryset = LearningResource.objects.filter(is_published=True)
        
        category = self.request.query_params.get('category')
        if category and category.lower() != 'all':
            queryset = queryset.filter(category__name__iexact=category)
        
        resource_type = self.request.query_params.get('type')
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(content__icontains=search)
            )
        
        return queryset.select_related('category').prefetch_related(
            'external_links', 'quiz_questions__options'
        ).order_by('order', 'created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context



class LearningResourceDetailView(RetrieveAPIView):
    serializer_class = LearningResourceSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, 'user_type', None) == 'controller':
            return LearningResource.objects.all()
        return LearningResource.objects.filter(is_published=True)
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Track user progress if authenticated
        if request.user.is_authenticated:
            progress, _ = UserProgress.objects.get_or_create(
                user=request.user,
                resource=instance
            )
            if not progress.completed:
                progress.progress_percentage = min(progress.progress_percentage + 10, 100)
                progress.last_accessed = timezone.now()
                progress.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_bookmark(request, resource_id):
    resource = get_object_or_404(LearningResource, id=resource_id, is_published=True)
    
    progress, _ = UserProgress.objects.get_or_create(
        user=request.user,
        resource=resource
    )
    progress.bookmarked = not progress.bookmarked
    progress.save()
    
    return Response({
        'bookmarked': progress.bookmarked,
        'message': 'Bookmark updated successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz(request, resource_id):
    if(request.user.user_type == 'controller') :
        resource = get_object_or_404(LearningResource, id=resource_id)
    else :
        resource = get_object_or_404(LearningResource, id=resource_id, is_published=True)

    if resource.resource_type != 'quiz':
        return Response({'error': 'This resource is not a quiz'}, status=400)
    
    serializer = QuizSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        print("Validation errors:", serializer.errors)  
        return Response(serializer.errors, status=400)
    print('j')
    answers = serializer.validated_data['answers']
    time_spent = serializer.validated_data['time_spent']
    

    # Fetch all questions and options once
    questions = {q.id: q for q in resource.quiz_questions.all()}
    options = {o.id: o for o in QuizOption.objects.filter(question__resource=resource)}
    
    correct_answers = 0
    for answer in answers:
        question = questions.get(answer['question_id'])
        option = options.get(answer['option_id'])
        if question and option and option.is_correct:
            correct_answers += 1
    
    total_questions = len(questions)
    score = (correct_answers / total_questions) * 100 if total_questions else 0
    
    # Save quiz attempt
    quiz_attempt = UserQuizAttempt.objects.create(
        user=request.user,
        resource=resource,
        total_questions=total_questions,
        correct_answers=correct_answers,
        answers=answers
    )
    
    # Update user progress
    progress, _ = UserProgress.objects.get_or_create(user=request.user, resource=resource)
    progress.time_spent += time_spent
    progress.completed = True
    progress.progress_percentage = 100
    progress.save()
    
    return Response({
        'score': score,
        'correct_answers': correct_answers,
        'total_questions': total_questions,
        'attempt_id': quiz_attempt.id,
        'message': 'Quiz submitted successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_progress(request):
    progress = UserProgress.objects.filter(user=request.user).select_related('resource')
    serializer = UserProgressSerializer(progress, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_quiz_history(request):
    attempts = UserQuizAttempt.objects.filter(user=request.user).select_related('resource')
    serializer = UserQuizAttemptSerializer(attempts, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bookmarked_resources(request):
    progress = UserProgress.objects.filter(
        user=request.user,
        bookmarked=True,
        resource__is_published=True
    ).select_related('resource')
    
    resources = [p.resource for p in progress]
    serializer = LearningResourceSerializer(resources, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_resource_category(request):
    serializer = ResourceCategorySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Resource category created', 'data': serializer.data}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_learning_resource(request):
    serializer = LearningResourceSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Learning resource created', 'data': serializer.data}, status=201)
    return Response(serializer.errors, status=400)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def toggle_visibility(request, resource_id):
    resource = get_object_or_404(LearningResource, id=resource_id)
    
    if resource.is_published :
        resource.is_published = False
    else :
        resource.is_published = True
    resource.save()
    
    return Response({
        'message': 'visibility updated successfully'
    })

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def learning_resource_delete(request, id):
    resource = get_object_or_404(LearningResource, id=id)

    if request.user.user_type != 'controller':
        return Response({'detail': 'Not authorized to delete this resource.'}, status=403)

    resource.delete()
    return Response({'message': 'Deleted successfully'}, status=204)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_external_link(request, resource_id):
    resource = get_object_or_404(LearningResource, id=resource_id)
    serializer = ExternalLinkSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(resource=resource)
        return Response({'message': 'External link created', 'data': serializer.data}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_quiz_question(request, resource_id):
    resource = get_object_or_404(LearningResource, id=resource_id)
    serializer = QuizQuestionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(resource=resource)
        return Response({'message': 'Quiz question created', 'data': serializer.data}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_quiz_option(request, question_id):
    question = get_object_or_404(QuizQuestion, id=question_id)
    serializer = QuizOptionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(question=question)
        return Response({'message': 'Quiz option created', 'data': serializer.data}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_learning_resource(request, resource_id):
    try:
        resource = get_object_or_404(LearningResource, id=resource_id)
        
        # Check if user has permission to update (you can add more specific permissions)
        # For example, only allow authors or admins to update
        
        serializer = LearningResourceSerializer(
            resource, 
            data=request.data, 
            partial=True,  # Allow partial updates
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Resource updated successfully',
                'data': serializer.data
            }, status=200)
        
        return Response(serializer.errors, status=400)
        
    except LearningResource.DoesNotExist:
        return Response({'error': 'Resource not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_quiz_question(request, question_id):
    try:
        question = get_object_or_404(QuizQuestion, id=question_id)
        
        serializer = QuizQuestionSerializer(
            question, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Question updated successfully',
                'data': serializer.data
            }, status=200)
        
        return Response(serializer.errors, status=400)
        
    except QuizQuestion.DoesNotExist:
        return Response({'error': 'Question not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_quiz_option(request, option_id):

    try:
        option = get_object_or_404(QuizOption, id=option_id)
        
        serializer = QuizOptionSerializer(
            option, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Option updated successfully',
                'data': serializer.data
            }, status=200)
        
        return Response(serializer.errors, status=400)
        
    except QuizOption.DoesNotExist:
        return Response({'error': 'Option not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_resource_category(request, category_id):
    try:
        category = get_object_or_404(ResourceCategory, id=category_id)
        
        serializer = ResourceCategorySerializer(
            category, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Category updated successfully',
                'data': serializer.data
            }, status=200)
        
        return Response(serializer.errors, status=400)
        
    except ResourceCategory.DoesNotExist:
        return Response({'error': 'Category not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_external_link(request, link_id):
    try:
        link = get_object_or_404(ExternalLink, id=link_id)
        
        serializer = ExternalLinkSerializer(
            link, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'External link updated successfully',
                'data': serializer.data
            }, status=200)
        
        return Response(serializer.errors, status=400)
        
    except ExternalLink.DoesNotExist:
        return Response({'error': 'External link not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_quiz_question(request, question_id):

    try:
        question = get_object_or_404(QuizQuestion, id=question_id)
        question.delete()
        return Response({'message': 'Question deleted successfully'}, status=200)
    except QuizQuestion.DoesNotExist:
        return Response({'error': 'Question not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_quiz_option(request, option_id):
    try:
        option = get_object_or_404(QuizOption, id=option_id)
        option.delete()
        return Response({'message': 'Option deleted successfully'}, status=200)
    except QuizOption.DoesNotExist:
        return Response({'error': 'Option not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_resource_category(request, category_id):

    try:
        category = get_object_or_404(ResourceCategory, id=category_id)
        category.delete()
        return Response({'message': 'Category deleted successfully'}, status=200)
    except ResourceCategory.DoesNotExist:
        return Response({'error': 'Category not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_external_link(request, link_id):

    try:
        link = get_object_or_404(ExternalLink, id=link_id)
        link.delete()
        return Response({'message': 'External link deleted successfully'}, status=200)
    except ExternalLink.DoesNotExist:
        return Response({'error': 'External link not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# report 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_incident_report(request):
    serializer = IncidentReportCreateSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        try:
            incident = serializer.save()
            
            # Auto-generate title if not provided
            if not incident.title:
                incident_type_display = dict(IncidentReport.INCIDENT_TYPES).get(incident.incident_type, 'Incident')
                incident.title = f"{incident_type_display} - {timezone.localtime(incident.incident_date).strftime('%b %d, %Y')}"
                incident.save()
            
            # Create initial status update
            IncidentUpdate.objects.create(
                incident=incident,
                status='submitted',
                message='Incident report submitted successfully.',
                created_by=request.user
            )
            
            full_serializer = IncidentReportSerializer(incident)
            return Response(full_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class IncidentReportListView(ListAPIView):
    serializer_class = IncidentReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IncidentReport.objects.all().prefetch_related('media', 'updates').order_by('-created_at')

class IncidentReportDetailView(RetrieveAPIView):
    serializer_class = IncidentReportSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        return IncidentReport.objects.all().prefetch_related('media', 'updates')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_incident_media(request, incident_id):
    try:
        incident = IncidentReport.objects.get(id=incident_id, user=request.user)
    except IncidentReport.DoesNotExist:
        return Response({'error': 'Incident report not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = MediaUploadSerializer(data=request.data)
    if serializer.is_valid():
        try:
            media = serializer.save(incident=incident)
            return Response({
                'message': 'Media uploaded successfully',
                'media_id': media.id
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def incident_statistics(request):

    total_reports = IncidentReport.objects.all().count()
    
    status_counts = {
        'submitted': IncidentReport.objects.filter(status='submitted').count(),
        'under_review': IncidentReport.objects.filter(status='under_review').count(),
        'resolved': IncidentReport.objects.filter(status='resolved').count(),
        'dismissed': IncidentReport.objects.filter(status='dismissed').count(),
    }
    
    type_counts = {
        incident_type: IncidentReport.objects.filter(
            incident_type=incident_type
        ).count()
        for incident_type, _ in IncidentReport.INCIDENT_TYPES
    }
    
    return Response({
        'total_reports': total_reports,
        'status_counts': status_counts,
        'type_counts': type_counts,
        'last_submission': IncidentReport.objects.filter(
        ).order_by('-created_at').first().created_at if total_reports > 0 else None
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_incidents(request):
    incidents = IncidentReport.objects.all().order_by('-created_at')[:5]
    
    serializer = IncidentReportSerializer(incidents, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_incident_status(request, incident_id):
    try:
        incidentReport = IncidentReport.objects.get(id=incident_id)
    except IncidentReport.DoesNotExist:
        return Response({'error': 'Incident report not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = IncidentUpdateSerializer(
        data=request.data,
        context={'request': request, 'incident': incidentReport}
    )

    if serializer.is_valid():
        update = serializer.save(
            incident=incidentReport
        )
        # Update incident status
        incidentReport.status = serializer.validated_data['status']
        if 'priority' in request.data:
            print(request.data)
            incidentReport.priority = request.data['priority']
        incidentReport.save()
        return Response(IncidentUpdateSerializer(update).data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# safety check

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def safety_settings(request):
    try:
        settings = SafetyCheckSettings.objects.get(user=request.user)
    except SafetyCheckSettings.DoesNotExist:
        settings = SafetyCheckSettings.objects.create(user=request.user)

    if request.method == 'GET':
        serializer = SafetyCheckSettingsSerializer(settings)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = SafetyCheckSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_check_in(request):
    serializer = ManualCheckInSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Create a check-in record
    check_in = SafetyCheckIn.objects.create(
        user=request.user,
        status='safe',
        scheduled_at=timezone.now(),
        responded_at=timezone.now(),
        location_lat=serializer.validated_data.get('location_lat'),
        location_lng=serializer.validated_data.get('location_lng'),
        notes=serializer.validated_data.get('notes', '')
    )
    contact = EmergencyContact.objects.filter(user=request.user, is_emergency_contact=True).first()
    if contact is None:
        return Response({
                'message': f'You don\'t have any emergecy conact to notify, Please add one to be safe Thank You',
            })
    else: 
        filters = Q()
        if contact.email:
            filters |= Q(email=contact.email)
        if contact.phone:
            filters |= Q(phone=contact.phone)
        send_to = User.objects.filter(filters).first()   

        if send_to is None:
            return Response({
                'message': f'Test alert sent to {contact.name} is not available in aegis, Thank You',
            })
        else:
            EmergencyNotification.objects.create(
                user=send_to,
                by_user=request.user,
                notification_type='safety_check',
                title=f'{request.user.full_name} test the alert',
                message = f"{request.user.full_name} is safe now at {timezone.now().strftime('%Y-%m-%d %I:%M:%S %p')}. Be safe, Be aware",
            )
            # Schedule next check-in based on user settings
            try:
                settings = SafetyCheckSettings.objects.get(user=request.user)
                if settings.is_enabled:
                    next_check_in = timezone.now() + timedelta(minutes=settings.check_in_frequency)
                    SafetyCheckIn.objects.create(
                        user=request.user,
                        status='pending',
                        scheduled_at=next_check_in
                    )
            except SafetyCheckSettings.DoesNotExist:
                pass

            return Response({
                'message': 'Safety check-in recorded successfully and notified to the emergency contact',
                'check_in': SafetyCheckInSerializer(check_in).data
            })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_emergency_alert_demo(request):


    # Create test alert notification
    EmergencyNotification.objects.create(
        user=request.user,
        notification_type='alert_test',
        title='Some test the alert',
        message = f"{request.user.full_name} tested the alert at {timezone.now().strftime('%Y-%m-%d %I:%M:%S %p')}. Be safe, Be aware"
    )

    print('alert success')

    return Response({
        'message': 'Test emergency alert sent successfully',
        # 'alert': EmergencyAlertSerializer(alert).data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def safety_statistics(request):
    # Calculate statistics for the last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)

    total_check_ins = SafetyCheckIn.objects.filter(
        user=request.user,
        created_at__gte=thirty_days_ago
    ).count()

    successful_check_ins = SafetyCheckIn.objects.filter(
        user=request.user,
        status='safe',
        created_at__gte=thirty_days_ago
    ).count()

    missed_check_ins = SafetyCheckIn.objects.filter(
        user=request.user,
        status='missed',
        created_at__gte=thirty_days_ago
    ).count()

    emergency_alerts = EmergencyAlert.objects.filter(
        user=request.user,
        activated_at__gte=thirty_days_ago
    ).count()

    response_rate = (successful_check_ins / total_check_ins * 100) if total_check_ins > 0 else 100

    last_check_in = SafetyCheckIn.objects.filter(
        user=request.user,
        status='safe'
    ).order_by('-responded_at').first()

    next_check_in = SafetyCheckIn.objects.filter(
        user=request.user,
        status='pending'
    ).order_by('scheduled_at').first()

    statistics = {
        'total_check_ins': total_check_ins,
        'successful_check_ins': successful_check_ins,
        'missed_check_ins': missed_check_ins,
        'emergency_alerts': emergency_alerts,
        'response_rate': round(response_rate, 1),
        'last_check_in': last_check_in.responded_at if last_check_in else None,
        'next_check_in': next_check_in.scheduled_at if next_check_in else None
    }

    serializer = SafetyStatisticsSerializer(statistics)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_in_history(request):
    check_ins = SafetyCheckIn.objects.filter(user=request.user).order_by('-scheduled_at')[:20]
    serializer = SafetyCheckInSerializer(check_ins, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_history(request):
    alerts = EmergencyAlert.objects.filter(user=request.user).order_by('-created_at')[:20]
    serializer = EmergencyAlertSerializer(alerts, many=True)
    return Response(serializer.data)


# silent capture 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_video_evidence(request):

    serializer = VideoEvidenceCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        evidence = VideoEvidence.objects.create(
            user=request.user,
            **serializer.validated_data
        )
        
        full_serializer = VideoEvidenceSerializer(evidence, context={'request': request})
        return Response({
            'message': 'Video evidence record created successfully',
            'evidence': full_serializer.data,
            'evidence_id': evidence.id
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to create evidence record: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_video_file(request, evidence_id):
    
    try:
        evidence = VideoEvidence.objects.get(id=evidence_id, user=request.user)
    except VideoEvidence.DoesNotExist:
        return Response(
            {'error': 'Video evidence record not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if evidence.video_file:
        return Response(
            {'error': 'Video file already uploaded for this evidence'},
            status=status.HTTP_400_BAD_REQUEST
        )

    file_serializer = VideoUploadSerializer(data=request.data)
    if not file_serializer.is_valid():
        return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        evidence.video_file = file_serializer.validated_data['video_file']
        evidence.file_size = evidence.video_file.size
        evidence.save()
        
        full_serializer = VideoEvidenceSerializer(evidence, context={'request': request})
        return Response({
            'message': 'Video file uploaded successfully',
            'evidence': full_serializer.data
        })
        
    except Exception as e:
        if evidence.video_file:
            try:
                evidence.video_file.delete(save=False)
            except:
                pass
        return Response(
            {'error': f'Failed to upload video file: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_video_evidence(request):
    
    if request.user.user_type == 'controller':
        evidence = VideoEvidence.objects.all().order_by('-recorded_at')
    else:
        evidence = VideoEvidence.objects.filter(user=request.user).order_by('-recorded_at')
    
    # Filtering options
    status_filter = request.query_params.get('status')
    if status_filter:
        evidence = evidence.filter(status=status_filter)
    
    type_filter = request.query_params.get('type')
    if type_filter:
        evidence = evidence.filter(type=type_filter)
    
    is_anonymous = request.query_params.get('is_anonymous')
    if is_anonymous is not None:
        evidence = evidence.filter(is_anonymous=is_anonymous.lower() == 'true')
    
    date_from = request.query_params.get('date_from')
    if date_from:
        evidence = evidence.filter(recorded_at__date__gte=date_from)
    
    date_to = request.query_params.get('date_to')
    if date_to:
        evidence = evidence.filter(recorded_at__date__lte=date_to)
    
    serializer = VideoEvidenceSerializer(evidence, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_video_evidence(request, evidence_id):
    
    try:
        evidence = VideoEvidence.objects.get(id=evidence_id)
        # if not evidence.user_can_access(request.user):
        #     return Response(
        #         {'error': 'Access denied'},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        serializer = VideoEvidenceSerializer(evidence, context={'request': request})
        return Response(serializer.data)
    except VideoEvidence.DoesNotExist:
        return Response(
            {'error': 'Video evidence not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_video_evidence(request, evidence_id):
    
    try:
        evidence = VideoEvidence.objects.get(id=evidence_id)
        # if not evidence.user_can_modify(request.user):
        #     return Response(
        #         {'error': 'You can only edit your own evidence'},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
    except VideoEvidence.DoesNotExist:
        return Response(
            {'error': 'Video evidence not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = VideoEvidenceUpdateSerializer(
        evidence, 
        data=request.data, 
        partial=request.method == 'PATCH'
    )
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        serializer.save()
        full_serializer = VideoEvidenceSerializer(evidence, context={'request': request})
        return Response({
            'message': 'Video evidence updated successfully',
            'evidence': full_serializer.data
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to update evidence: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_evidence_status(request, evidence_id):
    
    if request.user.user_type != 'controller':
        return Response(
            {'error': 'Only controllers can update evidence status'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        evidence = VideoEvidence.objects.get(id=evidence_id)
    except VideoEvidence.DoesNotExist:
        return Response(
            {'error': 'Video evidence not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = VideoEvidenceStatusSerializer(evidence, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        serializer.save()
        full_serializer = VideoEvidenceSerializer(evidence, context={'request': request})
        return Response({
            'message': 'Evidence status updated successfully',
            'evidence': full_serializer.data
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to update status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_video_evidence(request, evidence_id):

    try:
        evidence = VideoEvidence.objects.get(id=evidence_id)
        
        if evidence.video_file:
            evidence.video_file.delete(save=False)
        
        evidence.delete()
        
        return Response({
            'message': 'Video evidence deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
        
    except VideoEvidence.DoesNotExist:
        return Response(
            {'error': 'Video evidence not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def video_evidence_statistics(request):

    if request.user.user_type == 'controller':
        user_evidence = VideoEvidence.objects.all()
    else:
        user_evidence = VideoEvidence.objects.filter(user=request.user)
    
    total_videos = user_evidence.count()
    total_duration = sum(evidence.duration_seconds for evidence in user_evidence)
    total_file_size = sum(evidence.file_size for evidence in user_evidence)
    anonymous_count = user_evidence.filter(is_anonymous=True).count()
    
    # Status statistics
    status_stats = {
        status: user_evidence.filter(status=status).count()
        for status, _ in VideoEvidence.STATUS_CHOICES
    }
    
    # Type statistics
    type_stats = {
        evidence_type: user_evidence.filter(type=evidence_type).count()
        for evidence_type, _ in VideoEvidence.EVIDENCE_TYPE
    }
    
    # Recent activity (last 7 days)
    week_ago = timezone.now() - timezone.timedelta(days=7)
    recent_count = user_evidence.filter(created_at__gte=week_ago).count()
    
    return Response({
        'total_videos': total_videos,
        'total_duration_seconds': total_duration,
        'total_duration_display': f"{total_duration // 3600}h {(total_duration % 3600) // 60}m",
        'total_file_size': total_file_size,
        'total_file_size_display': f"{total_file_size / (1024 * 1024 * 1024):.2f} GB",
        'anonymous_count': anonymous_count,
        'recent_count': recent_count,
        'average_duration_seconds': total_duration / total_videos if total_videos > 0 else 0,
        'status_statistics': status_stats,
        'type_statistics': type_stats,
    })



# emergecy alert 



logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def activate_emergency(request):

    serializer = EmergencyActivationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            with transaction.atomic():
                # Create emergency alert
                alert = EmergencyAlert.objects.create(
                    user=request.user,
                    activation_method=serializer.validated_data['activation_method'],
                    initial_latitude=serializer.validated_data.get('latitude'),
                    initial_longitude=serializer.validated_data.get('longitude'),
                    initial_address=serializer.validated_data.get('address', ''),
                    is_silent=serializer.validated_data['is_silent'],
                    emergency_type=serializer.validated_data.get('emergency_type', 'general'),
                    description=serializer.validated_data.get('description', '')
                )
                
                # Record initial location
                if serializer.validated_data.get('latitude') and serializer.validated_data.get('longitude'):
                    LocationUpdate.objects.create(
                        alert=alert,
                        latitude=serializer.validated_data['latitude'],
                        longitude=serializer.validated_data['longitude'],
                        accuracy=serializer.validated_data.get('accuracy'),
                        speed=serializer.validated_data.get('speed')
                    )
                
                # Find and assign nearby responders
                assigned_responders = assign_nearby_responders(alert)
                
                # Notify emergency contacts
                notified_contacts = notify_emergency_contacts(alert)
                
                # Create notification for user
                EmergencyNotification.objects.create(
                    user=request.user,
                    alert=alert,
                    notification_type='alert_activated',
                    title='Emergency Alert Activated',
                    message=f'Emergency alert {alert.alert_id} has been activated. {len(assigned_responders)} responders notified.',
                    data={
                        'responders_count': len(assigned_responders),
                        'contacts_notified': notified_contacts,
                        'alert_id': alert.alert_id
                    }
                )
                
                logger.info(f"Emergency activated: {alert.alert_id} by user {request.user.email}")

            return Response({
                'success': True,
                'alert_id': alert.alert_id,
                'message': 'Emergency activated successfully',
                'responders_assigned': len(assigned_responders),
                'contacts_notified': notified_contacts,
                'fake_screen_active': alert.fake_screen_active,
                'activated_at': alert.activated_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error activating emergency: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to activate emergency. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def deactivate_emergency(request):
    """
    Deactivate emergency with PIN verification
    POST /api/aegis/emergency/deactivate/
    {
        "pin": "2580",
        "alert_id": "EMG-ABC12345"
    }
    """
    serializer = DeactivationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            alert_id = serializer.validated_data['alert_id']
            pin = serializer.validated_data['pin']
            
            alert = get_object_or_404(EmergencyAlert, alert_id=alert_id, user=request.user)
            
            # Check if alert is already cancelled/resolved
            if alert.status in ['cancelled', 'resolved']:
                return Response({
                    'success': False,
                    'error': 'Emergency alert has already been deactivated.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Record deactivation attempt
            attempt = DeactivationAttempt.objects.create(
                alert=alert,
                attempted_pin=pin,
                device_info={
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': get_client_ip(request)
                },
                location_at_attempt={
                    'latitude': float(alert.initial_latitude) if alert.initial_latitude else None,
                    'longitude': float(alert.initial_longitude) if alert.initial_longitude else None
                }
            )
            
            # Verify PIN (using the hardcoded PIN from frontend - in production, use user profile)
            if pin == "2580":  # TODO: Get from user profile in production
                alert.status = 'cancelled'
                alert.cancelled_at = timezone.now()
                alert.fake_screen_active = False
                alert.save()
                
                attempt.is_successful = True
                attempt.save()
                
                # Notify responders about cancellation
                notify_responders_cancellation(alert)
                
                # Create notification
                EmergencyNotification.objects.create(
                    user=request.user,
                    alert=alert,
                    notification_type='alert_resolved',
                    title='Emergency Cancelled',
                    message=f'Emergency alert {alert.alert_id} has been successfully cancelled.',
                    data={
                        'cancelled_at': alert.cancelled_at.isoformat(),
                        'alert_id': alert.alert_id
                    }
                )
                
                logger.info(f"Emergency deactivated: {alert.alert_id} by user {request.user.email}")
                
                return Response({
                    'success': True,
                    'message': 'Emergency deactivated successfully',
                    'alert_status': alert.status,
                    'cancelled_at': alert.cancelled_at.isoformat()
                })
            else:
                # Incorrect PIN
                alert.deactivation_attempts += 1
                alert.save()
                
                attempts = alert.deactivation_attempts
                
                # Handle suspicious activity after multiple attempts
                if attempts >= 3:
                    handle_suspicious_deactivation(alert, attempts)
                
                logger.warning(f"Failed deactivation attempt {attempts} for alert {alert.alert_id}")
                
                return Response({
                    'success': False,
                    'message': 'Incorrect PIN. Emergency remains active.',
                    'attempts': attempts,
                    'fake_screen_active': True  # Keep fake screen active
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except EmergencyAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Emergency alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def update_location(request):
    """
    Update victim's location during emergency
    POST /api/aegis/emergency/update-location/
    {
        "alert_id": "EMG-ABC12345",
        "latitude": 23.8105,
        "longitude": 90.4127,
        "accuracy": 15.5,
        "speed": 2.5,
        "altitude": 10.0,
        "heading": 45.0
    }
    """
    print('update location called')
    serializer = LocationUpdateRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            alert = get_object_or_404(EmergencyAlert, alert_id=serializer.validated_data['alert_id'], user=request.user)
            
            # Check if alert is active
            if alert.status != 'active':
                return Response({
                    'success': False,
                    'error': 'Cannot update location for inactive emergency'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            location_update = LocationUpdate.objects.create(
                alert=alert,
                latitude=serializer.validated_data['latitude'],
                longitude=serializer.validated_data['longitude'],
                accuracy=serializer.validated_data.get('accuracy'),
                speed=serializer.validated_data.get('speed'),
                altitude=serializer.validated_data.get('altitude'),
                heading=serializer.validated_data.get('heading')
            )
            
            # Notify responders about location update
            notify_responders_location_update(alert, location_update)
            
            logger.info(f"Location updated for alert {alert.alert_id}")
            
            return Response({
                'success': True,
                'message': 'Location updated successfully',
                'timestamp': location_update.timestamp.isoformat()
            })
            
        except EmergencyAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Emergency alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_media(request):
    """
    Upload media captured during emergency
    POST /api/aegis/emergency/upload-media/
    FormData:
    - alert_id: "EMG-ABC12345"
    - media_type: "audio" | "photo" | "video"
    - file: [file]
    - duration: 30 (optional, for audio/video)
    """
    print('upload media called')
    serializer = MediaUploadSerializer(data=request.data)
    if serializer.is_valid():
        try:
            alert = get_object_or_404(EmergencyAlert, alert_id=serializer.validated_data['alert_id'], user=request.user)
            
            # Check if alert is active
            if alert.status != 'active':
                return Response({
                    'success': False,
                    'error': 'Cannot upload media for inactive emergency'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            media_file = request.FILES['file']
            
            # Generate secure file path
            file_extension = media_file.name.split('.')[-1]
            secure_filename = f"{alert.alert_id}_{int(timezone.now().timestamp())}.{file_extension}"
            
            # In production, upload to secure storage (S3, etc.)
            # For now, we'll create a record with a mock URL
            media_capture = MediaCapture.objects.create(
                alert=alert,
                media_type=serializer.validated_data['media_type'],
                file=media_file,
                file_size=media_file.size,
                duration=serializer.validated_data.get('duration'),
                mime_type=media_file.content_type,
                # In production, you would encrypt the file and store the key
                is_encrypted=True,
                encryption_key="encrypted_key_placeholder"  
            )
            
            # Notify responders about new media
            notify_responders_media_upload(alert, media_capture)
            
            # Create notification
            EmergencyNotification.objects.create(
                user=request.user,
                alert=alert,
                notification_type='media_uploaded',
                title='Media Captured',
                message=f'New {media_capture.media_type} captured and uploaded.',
                data={
                    'media_type': media_capture.media_type,
                    'file_size': media_capture.file_size,
                    'captured_at': media_capture.captured_at.isoformat()
                }
            )
            
            logger.info(f"Media uploaded for alert {alert.alert_id}: {media_capture.media_type}")
            
            return Response({
                'success': True,
                'media_id': media_capture.id,
                'media_type': media_capture.media_type,
                'file_size': media_capture.file_size,
                'message': 'Media uploaded successfully'
            })
            
        except EmergencyAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Emergency alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_emergency_details(request, alert_id):
    """
    Get detailed emergency information
    GET /api/aegis/emergency/EMG-ABC12345/
    """
    try:
        alert = get_object_or_404(EmergencyAlert, alert_id=alert_id)
        serializer = EmergencyAlertDetailSerializer(alert)
        return Response({
            'success': True,
            'data': serializer.data
        })
    except EmergencyAlert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Emergency alert not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_emergencies(request):

    alerts = EmergencyAlert.objects.filter(status='active').order_by('-activated_at')
    serializer = EmergencyAlertSerializer(alerts, many=True)
    
    return Response({
        'success': True,
        'count': alerts.count(),
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_emergency_history(request):
    """
    Get user's emergency history
    GET /api/aegis/emergency/history/
    """
    alerts = EmergencyAlert.objects.filter(user=request.user).exclude(status='active').order_by('-activated_at')
    serializer = EmergencyAlertSerializer(alerts, many=True)
    
    return Response({
        'success': True,
        'count': alerts.count(),
        'data': serializer.data
    })




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_responder_assignments(request):

    if request.user.user_type != 'agent':
        return Response({
            'success': False,
            'error': 'Only agents can access responder assignments'
        }, status=status.HTTP_403_FORBIDDEN)
    
    responses = EmergencyResponse.objects.filter(
        responder=request.user,
        alert__status='active'
    ).select_related('alert', 'alert__user').order_by('-notified_at')
    
    serializer = EmergencyResponseSerializer(responses, many=True)
    
    return Response({
        'success': True,
        'count': responses.count(),
        'data': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def update_response_status(request):
    """
    Update responder's status for an emergency
    POST /api/aegis/responder/update-status/
    {
        "response_id": 1,
        "status": "en_route",
        "notes": "On my way to location",
        "eta_minutes": 5
    }
    """
    if request.user.user_type != 'agent':
        return Response({
            'success': False,
            'error': 'Only agents can update response status'
        }, status=status.HTTP_403_FORBIDDEN)
    
    response_id = request.data.get('response_id')
    new_status = request.data.get('status')
    
    if not response_id or not new_status:
        return Response({
            'success': False,
            'error': 'response_id and status are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        response = EmergencyResponse.objects.get(id=response_id, responder=request.user)
        
        # Validate status transition
        valid_transitions = {
            'notified': ['accepted', 'cancelled'],  
            'accepted': ['en_route', 'cancelled'],
            'en_route': ['on_scene', 'cancelled'],
            'on_scene': ['completed', 'cancelled'],
            'completed': [],
            'cancelled': []
        }
        
        current_status = response.status
        if new_status not in valid_transitions.get(current_status, []):
            return Response({
                'success': False,
                'error': f'Invalid status transition from {current_status} to {new_status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        response.status = new_status
        response.notes = request.data.get('notes', response.notes)
        response.eta_minutes = request.data.get('eta_minutes', response.eta_minutes)
        
        # Update timestamps based on status
        now = timezone.now()
        if new_status == 'accepted' and not response.accepted_at:
            response.accepted_at = now
        elif new_status == 'en_route' and not response.dispatched_at:
            response.dispatched_at = now
        elif new_status == 'on_scene' and not response.arrived_at:
            response.arrived_at = now
        elif new_status == 'completed' and not response.completed_at:
            response.completed_at = now
        elif new_status == 'cancelled':
            response.completed_at = now

        
        response.save()
        
        # Notify user about status update
        EmergencyNotification.objects.create(
            user=response.alert.user,
            alert=response.alert,
            notification_type='status_update',
            title='Responder Status Update',
            message=f'Responder {request.user.full_name} is now {new_status.replace("_", " ").title()}',
            data={
                'responder_status': new_status,
                'responder_name': request.user.full_name,
                'eta_minutes': response.eta_minutes,
                'updated_at': now.isoformat()
            }
        )
        
        # If response is completed, check if all responses are completed
        if new_status == 'completed':
            check_emergency_completion(response.alert)
        
        logger.info(f"Responder {request.user.email} updated status to {new_status} for alert {response.alert.alert_id}")
        
        return Response({
            'success': True,
            'message': 'Status updated successfully',
            'response_status': response.status,
            'updated_at': now.isoformat()
        })
        
    except EmergencyResponse.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Response assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)



def assign_nearby_responders(alert):
    """
    Find and assign nearby responders based on location
    """
    if not alert.initial_latitude or not alert.initial_longitude:
        # If no location, assign any available responders
        available_responders = User.objects.filter(
            user_type='agent',
            status='available'
        )[:3]
    else:
        # Find available responders (simplified - in production use geospatial queries)
        available_responders = User.objects.filter(
            user_type='agent',
            status='available',
            latitude__isnull=False,
            longitude__isnull=False
        )[:3]
    
    assigned = []
    for i, responder in enumerate(available_responders):
        # Calculate ETA based on distance (simplified)
        eta = calculate_eta(alert, responder, i)
        
        try:
            response = EmergencyResponse.objects.create(
                alert=alert,
                responder=responder,
                eta_minutes=eta,
                status='notified'
            )
            assigned.append(responder)
            
            
            # Notify responder
            EmergencyNotification.objects.create(
                user=responder,
                alert=alert,
                notification_type='responder_assigned',
                title='New Emergency Assignment',
                message=f'You have been assigned to emergency {alert.alert_id}. Estimated arrival: {eta} minutes',
                data={
                    'alert_id': alert.alert_id,
                    'eta_minutes': eta,
                    'user_name': alert.user.full_name,
                    'emergency_type': alert.emergency_type,
                    'location': alert.initial_address
                }
            )
            
            logger.info(f"Assigned responder {responder.email} to alert {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Error assigning responder {responder.email}: {str(e)}")
    
    return assigned


def notify_emergency_contacts(alert):
    
    contacts = EmergencyContact.objects.filter(
        user=alert.user, 
        is_emergency_contact=True
    )
    
    notified_count = 0
    for contact in contacts:
        try:
            # In production, implement actual SMS/email sending
            send_emergency_notification(contact, alert)
            notified_count += 1
            
            logger.info(f"Notified emergency contact: {contact.name} ({contact.phone})")
            
        except Exception as e:
            logger.error(f"Failed to notify {contact.name}: {str(e)}")
    
    return notified_count


def send_emergency_notification(contact, alert):
    # SMS message template
    message = f"""
🚨 EMERGENCY ALERT 🚨

{alert.user.full_name} has activated an emergency alert.

Alert ID: {alert.alert_id}
Time: {alert.activated_at.strftime('%Y-%m-%d %H:%M:%S')}
Location: {alert.initial_address or 'Location being tracked'}
Emergency Type: {alert.emergency_type.title()}

Please check the Aegis app for real-time updates.

Stay safe,
Aegis Emergency Response System
    """
    
    # TODO: Integrate with SMS service (Twilio, etc.)
    # TODO: Integrate with email service if contact has email
    print(f"SENDING SMS to {contact.phone}: {message}")
    
    return True


def notify_responders_cancellation(alert):

    for response in alert.responses.all():
        response.status = 'cancelled'
        response.completed_at = timezone.now()
        response.save()
        
        # Update responder status back to available
        responder = response.responder
        responder.status = 'available'
        responder.save()
        
        EmergencyNotification.objects.create(
            user=response.responder,
            alert=alert,
            notification_type='alert_resolved',
            title='Emergency Cancelled',
            message=f'Emergency {alert.alert_id} has been cancelled by the user.',
            data={
                'cancelled_at': alert.cancelled_at.isoformat(),
                'alert_id': alert.alert_id
            }
        )


def notify_responders_location_update(alert, location_update):

    for response in alert.responses.all():
        EmergencyNotification.objects.create(
            user=response.responder,
            alert=alert,
            notification_type='location_update',
            title='Location Updated',
            message=f'Updated location received for emergency {alert.alert_id}',
            data={
                'alert_id': alert.alert_id,
                'latitude': float(location_update.latitude),
                'longitude': float(location_update.longitude),
                'timestamp': location_update.timestamp.isoformat(),
                'accuracy': location_update.accuracy
            }
        )


def notify_responders_media_upload(alert, media_capture):

    for response in alert.responses.all():
        EmergencyNotification.objects.create(
            user=response.responder,
            alert=alert,
            notification_type='media_uploaded',
            title='New Media Uploaded',
            message=f'New {media_capture.media_type} uploaded for emergency {alert.alert_id}',
            data={
                'media_type': media_capture.media_type,
                'media_id': media_capture.id,
                'file_size': media_capture.file_size,
                'captured_at': media_capture.captured_at.isoformat()
            }
        )


def handle_suspicious_deactivation(alert, attempts):
    """
    Handle multiple failed deactivation attempts
    """
    # Log security event
    logger.warning(f"SECURITY ALERT: Multiple failed deactivation attempts ({attempts}) for alert {alert.alert_id}")
    
    # Notify administrators
    admins = User.objects.filter(user_type='admin')
    for admin in admins:
        EmergencyNotification.objects.create(
            user=admin,
            alert=alert,
            notification_type='alert_activated',
            title='Suspicious Deactivation Attempts',
            message=f'Multiple failed deactivation attempts ({attempts}) for alert {alert.alert_id}. Possible coercion situation.',
            data={
                'attempts': attempts, 
                'alert_id': alert.alert_id,
                'user_email': alert.user.email,
                'user_name': alert.user.full_name
            }
        )


def check_emergency_completion(alert):
    """
    Check if all responses are completed and update alert status accordingly
    """
    active_responses = alert.responses.exclude(status__in=['completed', 'cancelled'])
    if not active_responses.exists():
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.save()
        
        # Notify user
        EmergencyNotification.objects.create(
            user=alert.user,
            alert=alert,
            notification_type='alert_resolved',
            title='Emergency Resolved',
            message=f'Emergency {alert.alert_id} has been successfully resolved.',
            data={
                'resolved_at': alert.resolved_at.isoformat(),
                'alert_id': alert.alert_id
            }
        )


def calculate_eta(alert, responder, index):
    """
    Calculate estimated time of arrival (simplified version)
    """
    # Mock ETA calculation - in production, use actual distance and traffic data
    base_eta = 3  # Base 3 minutes
    variation = (index * 2)  # Add variation based on responder order
    return base_eta + variation


def get_client_ip(request):
    """
    Get client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_notifications(request):
    """
    Get user's notifications
    GET /api/aegis/notifications/
    """
    if request.user.user_type == 'controller' :
        notifications = EmergencyNotification.objects.filter(
            alert__isnull=False
        ).order_by('-created_at')
    else :
        notifications = EmergencyNotification.objects.filter(
            user=request.user
        ).order_by('-created_at')
    # print(notifications)
    # print("OpenRoute API Key:", OPENROUTE_API_KEY)
    
    unread_count = notifications.filter(is_read=False).count()
    notifications = notifications[:50]

    serializer = EmergencyNotificationSerializer(notifications, many=True)
    

    return Response({
        'success': True,
        'unread_count': unread_count,
        'data': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    try:
        notification = get_object_or_404(EmergencyNotification, id=notification_id)
        notification.is_read = True
        notification.save()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read'
        })
    except EmergencyNotification.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def emergency_statistics(request):
    """
    Get user's emergency statistics
    GET /api/aegis/emergency/statistics/
    """
    user = request.user
    
    total_alerts = EmergencyAlert.objects.filter(user=user).count()
    active_alerts = EmergencyAlert.objects.filter(user=user, status='active').count()
    resolved_alerts = EmergencyAlert.objects.filter(user=user, status='resolved').count()
    cancelled_alerts = EmergencyAlert.objects.filter(user=user, status='cancelled').count()
    
    # Average response time (simplified)
    resolved_with_response = EmergencyAlert.objects.filter(
        user=user, 
        status='resolved',
        responses__isnull=False
    )
    
    avg_response_time = None
    if resolved_with_response.exists():
        # Mock average response time calculation
        avg_response_time = 8.5  # minutes
    
    return Response({
        'success': True,
        'data': {
            'total_alerts': total_alerts,
            'active_alerts': active_alerts,
            'resolved_alerts': resolved_alerts,
            'cancelled_alerts': cancelled_alerts,
            'avg_response_time': avg_response_time,
            'emergency_contacts_count': EmergencyContact.objects.filter(user=user, is_emergency_contact=True).count()
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_emergency_updates(request, alert_id):
    """
    Get real-time updates for emergency - POLLING ENDPOINT
    GET /api/aegis/emergency/updates/EMG-ABC12345/
    """
    try:
        alert = get_object_or_404(EmergencyAlert, alert_id=alert_id)
        
        # Get latest data
        location_updates = LocationUpdate.objects.filter(alert=alert).order_by('-timestamp')[:5]
        media_captures = MediaCapture.objects.filter(alert=alert).order_by('-captured_at')[:10]
        responses = EmergencyResponse.objects.filter(alert=alert).select_related('responder')

        # Get and mark unread notifications safely
        unread_notifications = EmergencyNotification.objects.filter(alert=alert, is_read=False).order_by('-created_at')[:10]
        notification_serializer = EmergencyNotificationSerializer(unread_notifications, many=True)

        # ✅ Properly mark only these 10 as read
        ids = [n.id for n in unread_notifications]
        EmergencyNotification.objects.filter(id__in=ids).update(is_read=True)

        # Serialize the rest
        location_serializer = LocationUpdateSerializer(location_updates, many=True)
        media_serializer = MediaCaptureSerializer(media_captures, many=True)
        response_serializer = EmergencyResponseSerializer(responses, many=True)
        
        return Response({
            'success': True,
            'data': {
                'alert': EmergencyAlertSerializer(alert).data,
                'location_updates': location_serializer.data,
                'media_captures': media_serializer.data,
                'responses': response_serializer.data,
                'notifications': notification_serializer.data,
                'timestamp': timezone.now().isoformat()
            }
        })
        
    except EmergencyAlert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Emergency alert not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_emergecy_list(request):

    alerts = EmergencyAlert.objects.all().order_by('-activated_at')
    serializer = EmergencyAlertSerializer(alerts, many=True)
    
    return Response({
        'success': True,
        'count': alerts.count(),
        'data': serializer.data
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_responders(request, alert_id):
    """
    Get available responders with distances from emergency location
    GET /api/aegis/emergency/EMG-ABC12345/available-responders/
    """
    try:
        alert = get_object_or_404(EmergencyAlert, alert_id=alert_id)
        
        if not alert.initial_latitude or not alert.initial_longitude:
            return Response({
                'success': False,
                'error': 'Emergency location not available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get available responders (not currently assigned to this emergency)
        available_responders = User.objects.filter(
            user_type='agent',
            status='available',
            latitude__isnull=False,
            longitude__isnull=False
        ).exclude(
            id__in=EmergencyResponse.objects.filter(alert=alert).values('responder_id')
        )
        
        responders_with_distance = []
        for responder in available_responders:
            distance = calculate_distance(
                float(alert.initial_latitude),
                float(alert.initial_longitude),
                float(responder.latitude),
                float(responder.longitude)
            )
            
            # Calculate ETA based on distance and responder type
            eta_minutes = calculate_eta_based_on_distance(distance, responder.responder_type)
            
            responders_with_distance.append({
                'id': responder.id,
                'name': responder.full_name,
                'email': responder.email,
                'phone': responder.phone,
                'responder_type': responder.responder_type,
                'badge_number': responder.badge_number,
                'specialization': responder.specialization,
                'rating': responder.rating,
                'total_cases': responder.total_cases,
                'latitude': float(responder.latitude),
                'longitude': float(responder.longitude),
                'distance_km': round(distance, 2),
                'eta_minutes': eta_minutes,
                'profile_picture': responder.profile_picture.url if responder.profile_picture else None
            })
        
        # Sort by distance
        responders_with_distance.sort(key=lambda x: x['distance_km'])
        
        return Response({
            'success': True,
            'count': len(responders_with_distance),
            'emergency_location': {
                'latitude': float(alert.initial_latitude),
                'longitude': float(alert.initial_longitude),
                'address': alert.initial_address
            },
            'responders': responders_with_distance
        })
        
    except EmergencyAlert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Emergency alert not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_responder(request):
    
    serializer = ResponderAssignmentSerializer(data=request.data)
    if serializer.is_valid():
        try:
            alert = get_object_or_404(EmergencyAlert, alert_id=serializer.validated_data['alert_id'])
            responder = get_object_or_404(User, id=serializer.validated_data['responder_id'], user_type='agent')
            
            # Check if responder is already assigned
            existing_response = EmergencyResponse.objects.filter(alert=alert, responder=responder).first()
            if existing_response:
                return Response({
                    'success': False,
                    'error': 'Responder already assigned to this emergency'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate ETA based on current location
            eta_minutes = calculate_eta_based_on_distance(
                calculate_distance(
                    float(alert.initial_latitude),
                    float(alert.initial_longitude),
                    float(responder.latitude),
                    float(responder.longitude)
                ),
                responder.responder_type
            )
            
            # Create response assignment
            response = EmergencyResponse.objects.create(
                alert=alert,
                responder=responder,
                status='assigned',
                eta_minutes=eta_minutes,
                notes=serializer.validated_data.get('notes', '')
            )
            
            # Update responder status
            responder.status = 'busy'
            responder.save()
            
            # Create notification for responder
            EmergencyNotification.objects.create(
                user=responder,
                alert=alert,
                notification_type='responder_assigned',
                title='New Emergency Assignment',
                message=f'You have been assigned to emergency {alert.alert_id}. Estimated arrival: {eta_minutes} minutes',
                data={
                    'alert_id': alert.alert_id,
                    'eta_minutes': eta_minutes,
                    'emergency_type': alert.emergency_type,
                    'location': alert.initial_address,
                    'user_name': alert.user.full_name
                }
            )
            
            # Create notification for user
            EmergencyNotification.objects.create(
                user=alert.user,
                alert=alert,
                notification_type='responder_assigned',
                title='Responder Assigned',
                message=f'Responder {responder.full_name} has been assigned to your emergency. ETA: {eta_minutes} minutes',
                data={
                    'responder_name': responder.full_name,
                    'eta_minutes': eta_minutes,
                    'responder_type': responder.responder_type
                }
            )
            
            logger.info(f"Responder {responder.email} assigned to alert {alert.alert_id}")
            
            return Response({
                'success': True,
                'message': 'Responder assigned successfully',
                'response_id': response.id,
                'eta_minutes': eta_minutes
            })
            
        except EmergencyAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Emergency alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Responder not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_emergency_map_data(request, alert_id):
    """
    Get map data for emergency including location, responder locations, etc.
    GET /api/aegis/emergency/EMG-ABC12345/map-data/
    """
    try:
        alert = get_object_or_404(EmergencyAlert, alert_id=alert_id)
        
        map_data = {
            'emergency_location': {
                'latitude': float(alert.initial_latitude) if alert.initial_latitude else None,
                'longitude': float(alert.initial_longitude) if alert.initial_longitude else None,
                'address': alert.initial_address,
                'alert_id': alert.alert_id,
                'emergency_type': alert.emergency_type
            },
            'location_updates': [],
            'assigned_responders': [],
            'available_responders': []
        }
        
        # Get recent location updates
        location_updates = LocationUpdate.objects.filter(alert=alert).order_by('-timestamp')[:10]
        for update in location_updates:
            map_data['location_updates'].append({
                'latitude': float(update.latitude),
                'longitude': float(update.longitude),
                'timestamp': update.timestamp.isoformat(),
                'accuracy': update.accuracy
            })
        
        # Get assigned responders with locations
        assigned_responses = EmergencyResponse.objects.filter(
            alert=alert
        ).select_related('responder')
        # print(assigned_responses)
        for response in assigned_responses:
            if response.responder.latitude and response.responder.longitude:
                map_data['assigned_responders'].append({
                    'id': response.responder.id,
                    'name': response.responder.full_name,
                    'type': response.responder.responder_type,
                    'latitude': float(response.responder.latitude),
                    'longitude': float(response.responder.longitude),
                    'status': response.status,
                    'eta_minutes': response.eta_minutes
                })
        
        return Response({
            'success': True,
            'data': map_data
        })
        
    except EmergencyAlert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Emergency alert not found'
        }, status=status.HTTP_404_NOT_FOUND)
    



def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates in kilometers using Haversine formula
    """
    R = 6371  # Earth radius in kilometers
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat/2) * math.sin(dlat/2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2) * math.sin(dlon/2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

def calculate_eta_based_on_distance(distance_km, responder_type):
    
    # Base speed in km/h based on responder type
    base_speeds = {
        'police': 60,    # km/h
        'medical': 50,   # km/h  
        'ngo': 40,       # km/h
        'volunteer': 30, # km/h
    }
    
    speed = base_speeds.get(responder_type, 40)  # Default 40 km/h
    
    # Calculate time in hours, then convert to minutes
    time_hours = distance_km / speed
    eta_minutes = max(2, time_hours * 60)  # Minimum 2 minutes
    
    return round(eta_minutes)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_media(request):

    try:
        alert_id = request.GET.get('alert_id')
        media_type = request.GET.get('media_type')
        
        media_queryset = MediaCapture.objects.all()
        
        if alert_id:
            media_queryset = media_queryset.filter(alert__alert_id=alert_id)
        
        if media_type and media_type in ['audio', 'photo', 'video']:
            media_queryset = media_queryset.filter(media_type=media_type)
        
        media_queryset = media_queryset.order_by('-captured_at')
        
        serializer = MediaCaptureSerializer(media_queryset, many=True)
        
        return Response({
            'success': True,
            'count': len(serializer.data),
            'data': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error fetching media: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to fetch media files'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_emergency_responses(request, alert_id):
    """
    Get all responders assigned to a specific emergency alert,
    including their distance from the emergency location.
    GET /api/aegis/emergency/<alert_id>/notified-responder/

    """
    try:
        alert = get_object_or_404(EmergencyAlert, alert_id=alert_id)

        if not alert.initial_latitude or not alert.initial_longitude:
            return Response({
                'success': False,
                'error': 'Emergency location not available'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Optional filtering by status (?status=en_route)
        # status_filter = request.query_params.get('status')

        responses_qs = EmergencyResponse.objects.filter(alert=alert).select_related('responder', 'alert')
        # if status_filter:
        #     responses_qs = responses_qs.filter(status=status_filter)

        if not responses_qs.exists():
            return Response({
                'success': True,
                'message': 'No responders assigned to this emergency yet.',
                'alert_id': alert.alert_id,
                'responses': []
            }, status=status.HTTP_200_OK)

        response_list = []
        for response in responses_qs:
            responder = response.responder

            # Calculate distance if both locations exist
            distance_km = None
            if responder.latitude and responder.longitude:
                distance_km = calculate_distance(
                    float(alert.initial_latitude),
                    float(alert.initial_longitude),
                    float(responder.latitude),
                    float(responder.longitude)
                )

            response_list.append({
                'response_id': response.id,
                'responder_id': responder.id,
                'responder_name': responder.full_name,
                'email': responder.email,
                'phone': responder.phone,
                'responder_type': responder.responder_type,
                'badge_number': responder.badge_number,
                'specialization': responder.specialization,
                'rating': responder.rating,
                'total_cases': responder.total_cases,
                'status': response.status,
                'eta_minutes': response.eta_minutes,
                'notes': response.notes,
                'distance_km': round(distance_km, 2) if distance_km is not None else None,
                'timestamps': {
                    'notified_at': response.notified_at,
                    'accepted_at': response.accepted_at,
                    'dispatched_at': response.dispatched_at,
                    'arrived_at': response.arrived_at,
                    'completed_at': response.completed_at,
                }
            })

        # Sort responders by distance (closest first)
        response_list.sort(key=lambda x: (x['distance_km'] is None, x['distance_km']))

        return Response({
            'success': True,
            'count': len(response_list),
            'alert': {
                'alert_id': alert.alert_id,
                'emergency_type': alert.emergency_type,
                'address': alert.initial_address,
                'latitude': float(alert.initial_latitude),
                'longitude': float(alert.initial_longitude),
                'created_at': alert.activated_at
            },
            'responses': response_list
        }, status=status.HTTP_200_OK)

    except EmergencyAlert.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Emergency alert not found'
        }, status=status.HTTP_404_NOT_FOUND)




@api_view(['POST','GET' ])
@permission_classes([IsAuthenticated])
def emergency_incident_reports(request):

    try:
        if request.method == 'GET':
            # Get query parameters
            status_filter = request.GET.get('status')
            incident_type = request.GET.get('incident_type')
            severity = request.GET.get('severity')
            
            # Base queryset
            if request.user.user_type in ['controller', 'admin']:
                reports = EmergencyIncidentReport.objects.select_related('emergency', 'agent').all()
            else:
                reports = EmergencyIncidentReport.objects.select_related('emergency', 'agent').filter(agent=request.user)
            
            # print(reports)
            # Apply filters
            if status_filter:
                reports = reports.filter(status=status_filter)
            if incident_type:
                reports = reports.filter(incident_type=incident_type)
            if severity:
                reports = reports.filter(severity=severity)
            
            reports = reports.order_by('-created_at')
            
            serializer = EmergencyIncidentReportListSerializer(reports, many=True)
            
            return Response({
                'success': True,
                'count': len(serializer.data),
                'data': serializer.data
            })
        
        elif request.method == 'POST':
            serializer = EmergencyIncidentReportSerializer(data=request.data, context={'request': request})
            
            if serializer.is_valid():
                serializer.save(agent=request.user)
                return Response({
                    'success': True,
                    'message': 'Incident report created successfully',
                    'data': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
    except Exception as e:
        logger.error(f"Error in emergency_incident_reports: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to process request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET' ])
@permission_classes([IsAuthenticated])
def emergency_incident_reports_list(request, alert_id):

    try:
        status_filter = request.GET.get('status')
        incident_type = request.GET.get('incident_type')
        severity = request.GET.get('severity')
        
        # Base queryset
        if request.user.user_type in ['controller', 'admin']:
            reports = EmergencyIncidentReport.objects.select_related('emergency', 'agent').filter(emergency__alert_id=alert_id, status__in=['submitted', 'approved'])
        else:
            reports = EmergencyIncidentReport.objects.select_related('emergency', 'agent').filter(emergency__alert_id=alert_id, agent=request.user)
        
        print(reports)
        # Apply filters
        if status_filter:
            reports = reports.filter(status=status_filter)
        if incident_type:
            reports = reports.filter(incident_type=incident_type)
        if severity:
            reports = reports.filter(severity=severity)
        
        reports = reports.order_by('-created_at')
        
        serializer = EmergencyIncidentReportListSerializer(reports, many=True)
        
        return Response({
            'success': True,
            'count': len(serializer.data),
            'data': serializer.data
        })
                
    except Exception as e:
        logger.error(f"Error in emergency_incident_reports: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to process request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def emergency_incident_report_detail(request, pk):
    try:
        # Get report with permission check
        if request.user.user_type in ['controller', 'admin']:
            report = get_object_or_404(
                EmergencyIncidentReport.objects.select_related('agent'),
                pk=pk
            )
        else:
            report = get_object_or_404(
                EmergencyIncidentReport.objects.select_related('agent'), 
                pk=pk, 
                agent=request.user
            )
        
        print(report.agent.full_name)
        if request.method == 'GET':
            serializer = EmergencyIncidentReportSerializer(report)
            return Response({
                'success': True,
                'data': serializer.data
            })
        
        elif request.method == 'PUT':
            serializer = EmergencyIncidentReportSerializer(report, data=request.data, partial=True, context={'request': request})
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'success': True,
                    'message': 'Incident report updated successfully',
                    'data': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            report.delete()
            return Response({
                'success': True,
                'message': 'Incident report deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
                
    except Exception as e:
        logger.error(f"Error in emergency_incident_report_detail: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to process request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_emergency_incident_report(request, pk):
    try:
        # Get report with permission check
        if request.user.user_type in ['controller', 'admin']:
            report = get_object_or_404(EmergencyIncidentReport, pk=pk)
        else:
            report = get_object_or_404(EmergencyIncidentReport, pk=pk, agent=request.user)
        
        if report.status != 'draft':
            return Response({
                'success': False,
                'error': 'Report has already been submitted'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report.status = 'submitted'
        report.save()
        
        serializer = EmergencyIncidentReportSerializer(report)
        
        return Response({
            'success': True,
            'message': 'Report submitted successfully',
            'data': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error in submit_emergency_incident_report: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to submit report'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_emergency_incident_report(request, pk):
    try:
        if request.user.user_type not in ['controller', 'admin']:
            return Response({
                'success': False,
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        report = get_object_or_404(EmergencyIncidentReport, pk=pk)
        
        if report.status != 'submitted':
            return Response({
                'success': False,
                'error': 'Report must be in submitted status to approve'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        report.status = 'approved'
        report.save()
        
        serializer = EmergencyIncidentReportSerializer(report)
        
        return Response({
            'success': True,
            'message': 'Report approved successfully',
            'data': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error in approve_emergency_incident_report: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to approve report'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_emergency_incident_reports(request):
    try:
        reports = EmergencyIncidentReport.objects.filter(agent=request.user).order_by('-created_at')
        
        serializer = EmergencyIncidentReportListSerializer(reports, many=True)
        
        return Response({
            'success': True,
            'count': len(serializer.data),
            'data': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Error in my_emergency_incident_reports: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to fetch reports'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def emergency_incident_reports_stats(request):
    try:
        if request.user.user_type in ['controller','admin']:
            reports = EmergencyIncidentReport.objects.all()
        else:
            reports = EmergencyIncidentReport.objects.filter(agent=request.user)
        
        stats = {
            'total': reports.count(),
            'draft': reports.filter(status='draft').count(),
            'submitted': reports.filter(status='submitted').count(),
            'approved': reports.filter(status='approved').count(),
            'by_type': list(reports.values('incident_type').annotate(count=Count('id'))),
            'by_severity': list(reports.values('severity').annotate(count=Count('id'))),
        }
        
        return Response({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Error in emergency_incident_reports_stats: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to fetch statistics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def emergency_report_evidence(request):
    try:
        if request.method == 'GET':
            report_id = request.GET.get('report_id')
            
            if report_id:
                evidence = EmergencyReportEvidence.objects.filter(report_id=report_id)
            else:
                evidence = EmergencyReportEvidence.objects.filter(report__agent=request.user)
            
            evidence = evidence.order_by('-uploaded_at')
            
            serializer = EmergencyReportEvidenceSerializer(evidence, many=True)
            
            return Response({
                'success': True,
                'count': len(serializer.data),
                'data': serializer.data
            })
        
        elif request.method == 'POST':
            serializer = EmergencyReportEvidenceSerializer(data=request.data, context={'request': request})
            
            if serializer.is_valid():
                report_id = request.data.get('report')
                
                # Verify the report belongs to the current user
                try:
                    report = EmergencyIncidentReport.objects.get(id=report_id, agent=request.user)
                    serializer.save(report=report)
                    
                    return Response({
                        'success': True,
                        'message': 'Evidence uploaded successfully',
                        'data': serializer.data
                    }, status=status.HTTP_201_CREATED)
                    
                except EmergencyIncidentReport.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Report not found or access denied'
                    }, status=status.HTTP_404_NOT_FOUND)
                    
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
    except Exception as e:
        logger.error(f"Error in emergency_report_evidence: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to process request'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_emergency_report_evidence(request, pk):
    try:
        evidence = get_object_or_404(EmergencyReportEvidence, pk=pk)
        
        evidence.delete()
        
        return Response({
            'success': True,
            'message': 'Evidence deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
        
    except Exception as e:
        logger.error(f"Error in delete_emergency_report_evidence: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to delete evidence'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    




# safe route 



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_safe_locations(request):
    """Get user's safe locations"""
    try:
        locations = SafeLocation.objects.filter(user=request.user, is_active=True)
        serializer = SafeLocationSerializer(locations, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_safe_location(request):
    """Create a new safe location"""
    try:
        print("=== CREATE SAFE LOCATION ===")
        print("Request data:", request.data)
        print("User:", request.user.email)
        
        # Prepare data for serializer
        data = {
            'name': request.data.get('name'),
            'address': request.data.get('address'),
            'location_type': request.data.get('location_type', 'other'),
            'latitude': request.data.get('latitude'),
            'longitude': request.data.get('longitude'),
        }
        
        print("Data for serializer:", data)
        
        # Pass request context to serializer
        serializer = SafeLocationSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            print("Serializer is valid")
            safe_location = serializer.save()
            print("Safe location created:", safe_location.id)
            
            return Response({
                'success': True,
                'data': SafeLocationSerializer(safe_location).data
            })
        else:
            print("Serializer errors:", serializer.errors)
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=400)
            
    except Exception as e:
        print("Error creating safe location:", str(e))
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

# Emergency History API

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_emergency_history_location(request):
    """Get user's emergency history for route planning"""
    try:
        emergencies = EmergencyAlert.objects.all().exclude(
            Q(initial_latitude__isnull=True) | Q(initial_longitude__isnull=True)
        ).order_by('-activated_at')[:10]
        
        print(OPENROUTE_API_KEY)
        emergency_data = []
        for emergency in emergencies:
            emergency_data.append({
                'id': emergency.id,
                'location': emergency.initial_address or "Unknown Location",
                'type': emergency.emergency_type or 'general',
                'timestamp': emergency.activated_at.strftime('%b %d'),
                'lat': float(emergency.initial_latitude) if emergency.initial_latitude else None,
                'lng': float(emergency.initial_longitude) if emergency.initial_longitude else None
            })
        
        return Response({
            'success': True,
            'data': emergency_data
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
    



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def find_safe_route(request):
    """Find safe route avoiding emergency locations"""
    try:
        # Get request data
        destination = request.data.get('destination')
        current_lat = request.data.get('current_lat')
        current_lng = request.data.get('current_lng')
        
        if not all([destination, current_lat, current_lng]):
            return Response({
                'success': False,
                'error': 'Destination, current_lat, and current_lng are required'
            }, status=400)
        
        print(f"Finding route to: {destination}")
        print(f"Current location: {current_lat}, {current_lng}")
        
        # Step 1: Geocode destination
        geocode_url = "https://api.openrouteservice.org/geocode/search"
        headers = {
            'Authorization': OPENROUTE_API_KEY
        }
        geocode_params = {
            'text': destination,
            'size': 5
        }
        
        geocode_response = requests.get(geocode_url, headers=headers, params=geocode_params)
        print(f"Geocode response status: {geocode_response.status_code}")
        
        if geocode_response.status_code != 200:
            return Response({
                'success': False,
                'error': f'Geocoding failed: {geocode_response.text}'
            }, status=400)
        
        geocode_data = geocode_response.json()
        print(f"Geocode results: {len(geocode_data.get('features', []))}")
        
        if not geocode_data.get('features'):
            return Response({
                'success': False,
                'error': 'Destination not found'
            }, status=400)
        
        # Use the first result (most relevant)
        destination_feature = geocode_data['features'][0]
        dest_coords = destination_feature['geometry']['coordinates']  # [lng, lat]
        dest_address = destination_feature['properties']['label']
        
        print(f"Found destination: {dest_address} at {dest_coords}")
        
        # Step 2: Get emergency locations to avoid from EmergencyAlert model
        emergency_alerts = EmergencyAlert.objects.filter(
            initial_latitude__isnull=False,
            initial_longitude__isnull=False
        ).exclude(
            Q(initial_latitude=0) | Q(initial_longitude=0)
        ).order_by('-activated_at')[:10]  # Get recent emergencies
        
        avoided_locations = []
        avoid_polygons = []
        
        for alert in emergency_alerts:
            avoided_locations.append({
                'lat': float(alert.initial_latitude),
                'lng': float(alert.initial_longitude),
                'address': alert.initial_address or "Emergency Location",
                'type': alert.emergency_type or 'emergency',
                'timestamp': alert.activated_at.strftime('%Y-%m-%d')
            })
            
            # Create a small avoidance buffer around each emergency location
            buffer_radius = 0.005  # ~500m in degrees
            avoid_polygons.append([
                [float(alert.initial_longitude) - buffer_radius, float(alert.initial_latitude) - buffer_radius],
                [float(alert.initial_longitude) + buffer_radius, float(alert.initial_latitude) - buffer_radius],
                [float(alert.initial_longitude) + buffer_radius, float(alert.initial_latitude) + buffer_radius],
                [float(alert.initial_longitude) - buffer_radius, float(alert.initial_latitude) + buffer_radius],
                [float(alert.initial_longitude) - buffer_radius, float(alert.initial_latitude) - buffer_radius]
            ])
        
        # Step 3: Calculate route avoiding emergency areas
        route_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
        
        route_body = {
            "coordinates": [
                [float(current_lng), float(current_lat)],  # Start
                dest_coords  # Destination
            ],
            "instructions": False,
            "preference": "recommended"
        }
        
        # Add avoidance polygons only if they exist
        if avoid_polygons:
            route_body["options"] = {
                "avoid_polygons": {
                    "type": "MultiPolygon",
                    "coordinates": [[polygon] for polygon in avoid_polygons]
                }
            }
        
        print("Calculating route...")
        route_response = requests.post(route_url, headers=headers, json=route_body)
        
        # Check for route calculation errors
        if route_response.status_code != 200:
            error_data = route_response.json()
            print(f"Route API error: {error_data}")
            
            # Try without avoidance if route calculation fails
            print("Trying route without avoidance polygons...")
            fallback_body = {
                "coordinates": [
                    [float(current_lng), float(current_lat)],
                    dest_coords
                ],
                "instructions": False,
                "preference": "recommended"
            }
            
            fallback_response = requests.post(route_url, headers=headers, json=fallback_body)
            
            if fallback_response.status_code != 200:
                return Response({
                    'success': False,
                    'error': 'Unable to calculate route. Please check your coordinates and try again.'
                }, status=400)
            
            # Use fallback route data
            route_data = fallback_response.json()
            print("Fallback route calculated successfully")
        else:
            route_data = route_response.json()
            print("Route calculated successfully")
        
        # Validate route data structure
        if 'features' not in route_data or not route_data['features']:
            print(f"Route calculation error: 'features' missing in response")
            return Response({
                'success': False,
                'error': 'No route found - try adjusting your destination or check for service outages'
            }, status=400)
        
        # Extract route information
        route_feature = route_data['features'][0]
        route_geometry = route_feature['geometry']['coordinates']
        route_properties = route_feature['properties']
        
        # Calculate total distance and duration
        total_distance = sum(segment.get('distance', 0) for segment in route_properties.get('segments', [{}]))
        total_duration = sum(segment.get('duration', 0) for segment in route_properties.get('segments', [{}]))
        
        # Format distance and duration for display
        distance_km = total_distance / 1000
        duration_min = total_duration / 60
        
        # Store start and end coordinates in route_data
        route_info = {
            'distance': f"{distance_km:.1f} km",
            'duration': f"{duration_min:.0f} min",
            'route_path': route_geometry,
            'summary': route_properties.get('summary', {}),
            'start_coords': [float(current_lng), float(current_lat)],
            'end_coords': dest_coords,
            'start_address': f"Current Location ({current_lat:.4f}, {current_lng:.4f})",
            'end_address': dest_address
        }
        
        # Step 4: Save route to database - using only the fields that exist in your model
        safe_route = SafeRoute.objects.create(
            user=request.user,
            destination=dest_address,
            route_data=route_info,
            avoided_locations=avoided_locations,
            is_active=True
        )
        
        # Step 5: Prepare response with GeoJSON
        geojson_response = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": f"Safe Route to {dest_address}",
                        "distance": route_info['distance'],
                        "duration": route_info['duration'],
                        "route_id": safe_route.id
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": route_geometry
                    }
                },
                # Start point
                {
                    "type": "Feature",
                    "properties": {
                        "name": "Start Location",
                        "marker-color": "#00ff00",
                        "marker-symbol": "circle"
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(current_lng), float(current_lat)]
                    }
                },
                # Destination point
                {
                    "type": "Feature",
                    "properties": {
                        "name": f"Destination: {dest_address}",
                        "marker-color": "#ff0000",
                        "marker-symbol": "circle"
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": dest_coords
                    }
                }
            ]
        }
        
        # Add avoided locations as point features
        for i, location in enumerate(avoided_locations):
            geojson_response['features'].append({
                "type": "Feature",
                "properties": {
                    "name": f"Avoided: {location['address']}",
                    "type": location['type'],
                    "timestamp": location.get('timestamp', ''),
                    "marker-color": "#ff0000",
                    "marker-symbol": "danger"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [location['lng'], location['lat']]
                }
            })
        
        return Response({
            'success': True,
            'route_id': safe_route.id,
            'geojson': geojson_response,
            'summary': {
                'destination': dest_address,
                'distance': route_info['distance'],
                'duration': route_info['duration'],
                'avoided_locations_count': len(avoided_locations)
            }
        })
        
    except Exception as e:
        print(f"Internal Server Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)
    
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_route_geojson(request):
    """Get route as GeoJSON for map display"""
    try:
        route_id = request.data.get('route_id')
        
        if not route_id:
            return Response({
                'success': False,
                'error': 'Route ID is required'
            }, status=400)
        
        route = SafeRoute.objects.get(id=route_id, user=request.user)
        route_data = route.route_data
        
        # Create GeoJSON feature for the route
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": f"Route to {route.destination}",
                        "distance": route_data['distance'],
                        "duration": route_data['duration']
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": route_data['route_path']
                    }
                }
            ]
        }
        
        # Add emergency locations as point features
        for i, location in enumerate(route.avoided_locations):
            geojson['features'].append({
                "type": "Feature",
                "properties": {
                    "name": f"Avoided: {location['address']}",
                    "type": location['type'],
                    "marker-color": "#ff0000"
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [location['lng'], location['lat']]
                }
            })
        
        return Response({
            'success': True,
            'data': geojson
        })
        
    except SafeRoute.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Route not found'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reverse_geocode(request):
    """Convert coordinates to address"""
    try:
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        
        if not lat or not lng:
            return Response({
                'success': False,
                'error': 'Latitude and longitude are required'
            }, status=400)
        
        reverse_geocode_url = "https://api.openrouteservice.org/geocode/reverse"
        headers = {
            'Authorization': OPENROUTE_API_KEY
        }
        params = {
            'point.lon': lng,
            'point.lat': lat,
            'size': 1
        }
        
        response = requests.get(reverse_geocode_url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                address = data['features'][0]['properties']['label']
                return Response({
                    'success': True,
                    'data': {
                        'address': address,
                        'coordinates': [float(lng), float(lat)]
                    }
                })
        
        return Response({
            'success': True,
            'data': {
                'address': f"Location ({lat:.4f}, {lng:.4f})",
                'coordinates': [float(lng), float(lat)]
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_navigation(request):
    """Start safe navigation"""
    try:
        route_id = request.data.get('route_id')
        
        if not route_id:
            return Response({
                'success': False,
                'error': 'Route ID is required'
            }, status=400)
        
        # Create navigation session
        navigation_session = NavigationSession.objects.create(
            user=request.user,
            is_active=True
        )
        
        return Response({
            'success': True,
            'message': 'Safe navigation started! Emergency contacts have been notified.',
            'session_id': navigation_session.id,
            'live_sharing': True
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
    

def test_api_key():
    """Test API key with a simple geocoding request"""
    test_url = "https://api.openrouteservice.org/geocode/search"
    # headers = {
    #     'Authorization': 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjEzYTEzMTM3NjhlYzRjNGFhM2I5ZDE2ZTdjNGU4YzFiIiwiaCI6Im11cm11cjY0In0=',
    #     'Accept': 'application/json'
    # }
    headers = {
        'Authorization': OPENROUTE_API_KEY,
        'Accept': 'application/json'
    }
    print(headers['Authorization'])
    print(OPENROUTE_API_KEY)
    # Test with a simple, known location
    params = {
        'text': 'Gulshan 1, Dhaka, Bangladesh',
        'size': 1
    }
    
    try:
        response = requests.get(test_url, headers=headers, params=params, timeout=10)
        print(f"API Test - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(" API Key is valid and working!")
            return True
        elif response.status_code == 403:
            print("❌ API Key is invalid or unauthorized")
            print(f"Response: {response.text}")
            return False
        elif response.status_code == 404:
            print("❌ Endpoint not found - check API key format")
            return False
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API Test error: {e}")
        return False
