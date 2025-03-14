from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

from administrator.views import update_solution,site_complaints,preview_template,template_list,add_template,admin_view, allusers, complaints,projects, reviews,notification_mark_as_read,user_list,toggle_status,toggle_permission,change_profile_image,account_settings,change_password, events, approve_event, reject_event

app_name = 'administrator'

urlpatterns = [
    
   path('admin_view/', admin_view,name="admin_view"),
   path('user_list/',user_list,name="user_list"),
   path('toggle_status/<int:uid>',toggle_status,name="toggle_status"),
   
   path('toggle_permission/<int:uid>',toggle_permission,name="toggle_permission"),
   path('change_profile_image/<int:uid>', change_profile_image, name='change_profile_image'),
   path('account_settings/', account_settings, name='account_settings'),
   path('change_password/<int:uid>', change_password, name='change_password'),
   path('notification_mark_as_read/<int:not_id>', notification_mark_as_read, name='notification_mark_as_read'),
   path('reviews/', reviews, name='reviews'),
   path('allusers/', allusers,name="allusers"),
  
   path('complaints/', complaints,name="complaints"),
    path('site_complaints/', site_complaints, name='site_complaints'), 

   path('projects/', projects,name="projects"),
  path('add_template/', add_template, name='add_template'),
   path('template_list/', template_list, name='template_list'),
   
    path('preview_template/<int:template_id>/', preview_template, name='preview_template'),
    
    path('update_solution/', update_solution, name='update_solution'),
    path('events/', events, name='events'),
    path('approve_event/<int:event_id>/', approve_event, name='approve_event'),
    path('reject_event/<int:event_id>/', reject_event, name='reject_event'),
]


