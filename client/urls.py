from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

from client.views import  plans,mark_project_completed,download_invoice,view_invoice,payments,update_complaint_status,update_solution,view_complaints_recieved,view_complaints,add_complaint,send_file,fetch_messages,send_message,chat_view,add_github_link,edit_task, submit_review, update_task_status, verify_payment,payment_success,make_payment, submit_contract,add_task, add_url,add_note,add_file, create_repository,acc_deactivate,lock_proposal, notification_mark_as_read, toggle_project_status,edit_project,delete_event,update_event,add_event,update_proposal_status,freelancer_detail,calendar,AddProfileClient, client_view,account_settings,change_password, project_list, single_project_view,update_profile,change_profile_image,add_new_project,freelancer_list, update_task_progress, view_repository, hire_freelancer, accept_interview, reject_interview, track_hiring, submit_meeting, toggle_hiring_status, manage_event_quizzes, create_event, get_event_details,remove_event,manage_single_event,update_event_settings, send_event_link,create_prize_payment,verify_prize_payment, upload_certificate_template, generate_certificates,client_repositories
def welcome(request):
    return render(request,'welcome.html')
urlpatterns = [
    
    path('client_view/', client_view,name="client_view"),
   
    path('add_profile_client/<int:uid>/', AddProfileClient,name="add_profile_client"),
    path('account_settings/', account_settings, name='account_settings'),
    path('change_password/<int:uid>', change_password, name='change_password'),
    
    path('update_profile/<int:uid>', update_profile, name='update_profile'),
    
    path('change_profile_image/<int:uid>', change_profile_image, name='change_profile_image'),
    
    
    path('freelancer_list/', freelancer_list, name='freelancer_list'),
    path('freelancer_detail/<int:fid>', freelancer_detail, name='freelancer_detail'),
    path('calendar/', calendar, name='calendar'),
    path('add-event/', add_event, name='add_event'),
    
    path('update_event', update_event, name='update_event'),
    path('delete_event/', delete_event, name='delete_event'),
    
    path('add_new_project/', add_new_project, name='add_new_project'),
    path('edit_project/<int:pid>', edit_project, name='edit_project'),
    
    path('toggle_project_status/<int:pid>', toggle_project_status, name='toggle_project_status'),
    path('project_list/', project_list, name='project_list'),
    path('single_project_view/<int:pid>', single_project_view, name='single_project_view'),
    
    path('update_proposal_status/<int:pro_id>', update_proposal_status, name='update_proposal_status'),
    path('lock_proposal/<int:prop_id>', lock_proposal, name='lock_proposal'),
    path('acc_deactivate/', acc_deactivate, name='acc_deactivate'),

    path('notification_mark_as_read/<int:not_id>', notification_mark_as_read, name='notification_mark_as_read'),
    
    
    path('create_repository/', create_repository, name='create_repository'),
    path('view_repository/<int:repo_id>', view_repository, name='view_repository'),
    
    path('add_file/<int:repo_id>', add_file, name='add_file'),
    
    path('add_url/<int:repo_id>', add_url, name='add_url'),
    
    path('add_note/<int:repo_id>', add_note, name='add_note'),
    
    path('add_task/<int:repo_id>', add_task, name='add_task'),
    
    path('update_task_progress/<int:repo_id>', update_task_progress, name='update_task_progress'),
    path('update_task_status/<int:repo_id>/', update_task_status, name='update_task_status'),
    path('edit_task/<int:repo_id>/', edit_task, name='edit_task'),
    path('add_github_link/<int:repo_id>/', add_github_link, name='add_github_link'),
    
    path('submit_contract/<int:pro_id>', submit_contract, name='submit_contract'),
    
    
    
    
    
    path('make_payment/<int:installment_id>/', make_payment, name='make_payment'),
    path('verify_payment/', verify_payment, name='verify_payment'),
    
    path('payment_success/', payment_success, name='payment_success'),
    path('submit_review/', submit_review, name='submit_review'),
    
    
    path('chat_view/', chat_view, name='chat_view'),
    path('send-message/', send_message, name='send_message'),
    path('fetch-messages/', fetch_messages, name='fetch_messages'),
    path('send_file/', send_file, name='send_file'),
    
    
    path('add_complaint/', add_complaint, name='add_complaint'),
    
    path('view_complaints/', view_complaints, name='view_complaints'),
    
    path('view_complaints_recieved/', view_complaints_recieved, name='view_complaints_recieved'),
    
    path('update_solution/', update_solution, name='update_solution'),
      path('update-complaint-status/', update_complaint_status, name='update_complaint_status'),
      
    path('payments/', payments, name='payments'),
    path('view_invoice/<int:contract_id>/', view_invoice, name='view_invoice'),
    path('download_invoice/<int:contract_id>/', download_invoice, name='download_invoice'),
    path('mark_project_completed/', mark_project_completed, name='mark_project_completed'),
    path('hire-freelancer/', hire_freelancer, name='hire_freelancer'),
    path('accept_interview/<int:invitation_id>/', accept_interview, name='accept_interview'),
    path('reject_interview/<int:invitation_id>/', reject_interview, name='reject_interview'),
    path('track_hiring/', track_hiring, name='track_hiring'),
    path('submit_meeting', submit_meeting, name='submit_meeting'),
    path('toggle_hiring_status/', toggle_hiring_status, name='toggle_hiring_status'),
    path('manage_event_quizzes/', manage_event_quizzes, name='manage_event_quizzes'),
    path('create_event/', create_event, name='create_event'),
    path('get_event_details/<int:event_id>/', get_event_details, name='get_event_details'),
    path('remove_event/<int:event_id>/', remove_event, name='remove_event'), 
    path('manage_single_event/<int:event_id>/', manage_single_event, name='manage_single_event'),
    path('update_event_settings/<int:event_id>/', update_event_settings, name='update_event_settings'), 
    path('send-event-link/', send_event_link, name='send_event_link'),
    path('create-prize-payment/', create_prize_payment, name='create_prize_payment'),
    path('verify-prize-payment/', verify_prize_payment, name='verify_prize_payment'),
    path('upload-certificate-template/<int:event_id>/', upload_certificate_template, name='upload_certificate_template'),
    path('generate-certificates/<int:event_id>/', generate_certificates, name='generate_certificates'),
    
    path('repositories/', client_repositories, name='client_repositories'),
    path('plans/', plans, name='plans'),
]
