from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('adjust-balance/', views.AdjustBalanceView.as_view(), name='adjust_balance'),
    path('create-admin/', views.CreateAdminUserView.as_view(), name='create_admin_user'),
    path('delete-account/', views.DeleteOwnAccountView.as_view(), name='delete_account'),
    path('calendar/', views.CalendarView.as_view(), name='calendar'),
    path('promote-user/<int:user_id>/', views.PromoteUserView.as_view(), name='promote_user'),
    path('delete-user/<int:user_id>/', views.DeleteUserView.as_view(), name='delete_user'),
    path('delete-leave/<int:leave_id>/', views.DeleteLeaveView.as_view(), name='delete_leave'),
    path('export-leaves/', views.ExportLeavesView.as_view(), name='export_leaves'),
    path('user/<int:user_id>/', views.UserDetailView.as_view(), name='user_detail'),
    path('edit-user/<int:user_id>/', views.EditUserView.as_view(), name='edit_user'),
    path('reset-balances/', views.ResetBalancesView.as_view(), name='reset_balances'),
    path('approve-leave/<int:leave_id>/', views.ApproveLeaveDashboardView.as_view(), name='approve_leave'),
    path('reject-leave/<int:leave_id>/', views.RejectLeaveDashboardView.as_view(), name='reject_leave'),
    path('archives/', views.ArchivesView.as_view(), name='archives'),
    path('download-pdf/<int:leave_id>/', views.DownloadPDFView.as_view(), name='download_pdf'),
    path('delete-archives/', views.DeleteArchivesView.as_view(), name='delete_archives'),
]
