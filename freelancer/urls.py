from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

from freelancer.views import  update_todo_status,update_complaint_status,update_solution,view_complaints_recieved,view_complaints,preview_template,my_portfolios,download_resume,process_resume,upload_resume,template_list,add_complaint,send_file,fetch_messages,send_message,chat_view,add_url,add_note,add_file, submit_user_review, tasks_list, update_freelancer_signature, upload_pdf, view_contract,view_repository,acc_deactivate, add_new_event, delete_event, edit_created_proposal, notification_mark_as_read, update_event, update_todo, view_created_proposals,proposal_detail1,proposal_detail2,download_proposal_pdf, generate_proposal,delete_todo,proposal_list,add_new_proposal,add_todo, calendar,AddProfileFreelancer, change_profile_image,freelancer_view,account_settings,change_password, single_project_view,update_profile,view_project,client_list,client_detail,todo, payments, download_invoice, edit_portfolio

urlpatterns = [
    path('freelancer_view/', freelancer_view,name="freelancer_view"),
    
    path('add_profile_freelancer/<int:uid>/', AddProfileFreelancer,name="add_profile_freelancer"),
    path('account_settings/', account_settings, name='account_settings'),
    path('change_password/<int:uid>', change_password, name='change_password'),
    path('update_profile/<int:uid>', update_profile, name='update_profile'),
    path('change_profile_image/<int:uid>', change_profile_image, name='change_profile_image'),
    
    
    path('tasks_list/', tasks_list, name='tasks_list'),
    path('client_list/', client_list, name='client_list'),
    path('client_detail/<int:cid>', client_detail, name='client_detail'),
   
    path('calendar/', calendar, name='calendar'),
    path('add_new_event/', add_new_event, name='add_new_event'),
    
    path('update_event', update_event, name='update_event'),
    path('delete_event/', delete_event, name='delete_event'),
    
    path('notification_mark_as_read/<int:not_id>', notification_mark_as_read, name='notification_mark_as_read'),
    path('todo/', todo, name='todo'),
    
    path('add_todo/', add_todo, name='add_todo'),
    path('delete_todo/<int:todo_id>', delete_todo, name='delete_todo'),
    path('update_todo/', update_todo, name='update_todo'),
    
    path('view_project/', view_project, name='view_project'),
    
    path('single_project_view/<int:pid>', single_project_view, name='single_project_view'),
    path('add_new_proposal/<int:pid>', add_new_proposal, name='add_new_proposal'),
    path('proposal_list/', proposal_list, name='proposal_list'),
    
    path('generate_proposal/<int:pid>', generate_proposal, name='generate_proposal'),
    path('view_created_proposals/', view_created_proposals, name='view_created_proposals'),
    
    path('proposal_detail1/<int:prop_id>', proposal_detail1, name='proposal_detail1'),
    path('proposal_detail2/<int:prop_id>', proposal_detail2, name='proposal_detail2'),
    path('edit_created_proposal/<int:prop_id>', edit_created_proposal, name='edit_created_proposal'),
    
    path('download_proposal_pdf/<int:prop_id>', download_proposal_pdf, name='download_proposal_pdf'),
    path('acc_deactivate/', acc_deactivate, name='acc_deactivate'),
    
    
    
     path('view_repository/<int:repo_id>', view_repository, name='view_repository'),
    
    path('add_file/<int:repo_id>', add_file, name='add_file'),
    
    path('add_url/<int:repo_id>', add_url, name='add_url'),
    
    path('add_note/<int:repo_id>', add_note, name='add_note'),
    
    path('update_freelancer_signature/',update_freelancer_signature, name='update_freelancer_signature'),
    
    path('view_contract/<int:cont_id>/',view_contract, name='view_contract'),
    path('upload_pdf/', upload_pdf, name='upload_pdf'),
    
    
    path('submit_user_review/', submit_user_review, name='submit_user_review'),
    
    
    
    path('chat_view/', chat_view, name='chat_view'),
    
    path('send-message/', send_message, name='send_message'),
    path('fetch-messages/', fetch_messages, name='fetch_messages'),
    
    path('send_file/', send_file, name='send_file'),
    
    
    
    path('add_complaint/', add_complaint, name='add_complaint'),
    
    path('update_todo_status/', update_todo_status, name='update_todo_status'),
    
    
   path('template_list/', template_list, name='template_list'),
   path('upload_resume/', upload_resume, name='upload_resume'),
    path('process_resume/<int:document_id>/',process_resume, name='process_resume'),
    path('download_resume/<int:document_id>/', download_resume, name='download_resume'),
    path('my_portfolios/', my_portfolios, name='my_portfolios'),
    path('preview_template/<int:template_id>/', preview_template, name='preview_template'),
    
    path('view_complaints/', view_complaints, name='view_complaints'),
    
    path('view_complaints_recieved/', view_complaints_recieved, name='view_complaints_recieved'),
    
    path('update_solution/', update_solution, name='update_solution'),
     path('update-complaint-status/', update_complaint_status, name='update_complaint_status'),
     path('payments/', payments, name='payments'),
    path('download_invoice/<int:refund_id>/', download_invoice, name='download_invoice'),
    path('edit-portfolio/<int:portfolio_id>/', edit_portfolio, name='edit_portfolio'),
]
