from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('',views.user_login,name='user_login'),
    path('home/', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('display_students/', views.display_students, name='display_students'),
    path('delete_student/<int:student_id>/',views.delete_student,name='delete_student'),
    path('update_student/<int:student_id>/',views.update_student,name='update_student'),
    path('student_home/',views.student_home,name='student_home'),
    path('update_details/',views.update_details,name='update_details'),
    path('update_student_ajax/', views.update_student_ajax, name='update_student_ajax'),
    path('principal_home/',views.principal_home,name='principal_home'),
    path('update_principal_student_ajax/',views.update_principal_student_ajax, name='update_principal_student_ajax'),
    path('add_principal_student_ajax/', views.add_principal_student_ajax, name='add_principal_student_ajax'),
    path('update_principal_class_ajax/',views.update_principal_class_ajax, name='update_principal_class_ajax'),
    path('delete_class/<int:class_id>/',views.delete_class,name='delete_class'),
    path('class_students/<int:class_id>/', views.class_students, name='class_students'),
    path('section_students/<str:class_id>/<str:section_id>/', views.section_students, name='section_students'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)