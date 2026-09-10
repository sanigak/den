from django.urls import path, register_converter
from .converters import RecordIdConverter

register_converter(RecordIdConverter, "record")
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),

    # Household projects
    path('projects/', views.household_projects, name='household_projects'),
    path('projects/<record:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<record:project_id>/comments/', views.project_add_comment, name='project_add_comment'),
    path('projects/<record:project_id>/edit/', views.household_projects, name='project_edit'),
    path('projects/<record:project_id>/completion/', views.project_set_completion, name='project_set_completion'),
    path('projects/<record:project_id>/delete/', views.project_delete, name='project_delete'),

    # Shopping List
    path('shopping/', views.shopping_list, name='shopping_list'),
    path('shopping/delete/<record:item_id>/', views.shopping_delete, name='shopping_delete'),
    path('shopping/download/', views.shopping_download, name='shopping_download'),
    path('shopping/clear/', views.shopping_clear, name='shopping_clear'),
    path('shopping/download-and-clear/', views.shopping_download_and_clear, name='shopping_download_and_clear'),
    path('shopping/smart-export/', views.shopping_smart_export, name='shopping_smart_export'),

    # Recipes
    path('recipes/', views.recipe_list, name='recipe_list'),
    path('recipes/add/', views.recipe_create, name='recipe_create'),
    path('recipes/<record:recipe_id>/edit/', views.recipe_edit, name='recipe_edit'),
    path('recipes/<record:recipe_id>/delete/', views.recipe_delete, name='recipe_delete'),

    # Meal Planner
    path('planner/', views.meal_calendar, name='meal_calendar'),
    path('planner/regenerate/', views.meal_regenerate, name='meal_regenerate'),
    path('planner/swap/', views.meal_swap, name='meal_swap'),
    path('planner/skip/', views.meal_skip, name='meal_skip'),
    path('planner/add-to-shopping/', views.meal_add_to_shopping, name='meal_add_to_shopping'),
]
