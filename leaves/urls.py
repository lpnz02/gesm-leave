from django.urls import path
from . import views

urlpatterns = [
    path('submit/', views.SubmitLeaveView.as_view(), name='submit_leave'),
    path('action/<uuid:token>/', views.LeaveActionView.as_view(), name='leave_action'),
    path('submitted/', views.LeaveSubmittedView.as_view(), name='leave_submitted'),
]