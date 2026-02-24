from django.urls import path
from . import views

app_name = 'backoffice'

urlpatterns = [
    # Auth
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Products
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', views.ProductEditView.as_view(), name='product_edit'),

    # Tasks
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('tasks/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/edit/', views.TaskEditView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/save-template/', views.SaveStepsAsTemplateView.as_view(), name='save_steps_as_template'),

    # Step Templates
    path('step-templates/', views.StepTemplateListView.as_view(), name='step_template_list'),
    path('step-templates/<int:pk>/delete/', views.StepTemplateDeleteView.as_view(), name='step_template_delete'),
    path('step-templates/<int:pk>/data/', views.StepTemplateDataView.as_view(), name='step_template_data'),

    # Buybacks
    path('buybacks/', views.BuybackListView.as_view(), name='buyback_list'),
    path('buybacks/<int:pk>/', views.BuybackDetailView.as_view(), name='buyback_detail'),

    # Moderation
    path('moderation/', views.ModerationListView.as_view(), name='moderation_list'),
    path('moderation/<int:pk>/', views.ModerationDetailView.as_view(), name='moderation_detail'),
    path('moderation/buyback/<int:pk>/', views.BuybackModerationDetailView.as_view(), name='moderation_buyback_detail'),

    # Payouts
    path('payouts/', views.PayoutListView.as_view(), name='payout_list'),

    # Users
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
]
