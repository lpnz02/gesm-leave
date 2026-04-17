from django.urls import path
from . import views

urlpatterns = [
    path('', views.Welcome.as_view(), name='welcome'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('verify-email/<uuid:token>/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('pending/', views.PendingView.as_view(), name='pending'),path('approve-user/<int:user_id>/', views.ApproveUserView.as_view(), name='approve_user'),
path('reject-user/<int:user_id>/', views.RejectUserView.as_view(), name='reject_user'),
]

