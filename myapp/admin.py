from django.contrib import admin

# Register your models here.
from .models import Teacher,Student,NewUsers,Class_name,Section,Subject,Period,Principal 

admin.site.register(NewUsers)
admin.site.register(Teacher)
admin.site.register(Student)
admin.site.register(Class_name)
admin.site.register(Section)
admin.site.register(Subject)
admin.site.register(Period)
admin.site.register(Principal)