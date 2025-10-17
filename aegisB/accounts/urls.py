from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('profile/', views.get_user_profile, name='profile'),
    path('profile/change-password/', views.change_password, name='change-password'),
    path('profile/picture/', views.update_profile_picture, name='update-profile-picture'),
    path('profile/picture/delete/', views.delete_profile_picture, name='delete-profile-picture'),
    path('auth-status/', views.check_auth_status, name='auth-status'),
    path('responders/<int:responder_id>/status/', views.update_responder_status, name='update-responder-status'),
    path('responders/', views.get_responders, name='get-responders'),
]