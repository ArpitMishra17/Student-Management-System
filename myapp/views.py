from django.shortcuts import render, redirect,get_object_or_404
from .models import Student, Teacher, NewUsers,Principal,Class_name,Section,Subject
from django.core.paginator import Paginator
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode

def user_login(request):
    if request.method == 'POST':

        
        user_email=request.POST.get('user_email',None)
        user_password=request.POST.get('user_password',None)

        print("user_email" , user_email)
        print("user_password" , user_password)

        user=authenticate(request,email=user_email, password=user_password)


        #print(user.is_staff )

        if user:
            if user.is_staff :

            
                if hasattr(user,'teacher'):
                    login(request, user)
                    return redirect('home')
                elif hasattr(user, 'principal'):
                    login(request,user)
                    return redirect('principal_home') 
            else:
                login(request, user)
                return redirect('student_home')
        else:
            
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    

    return render(request, 'login.html')

@login_required(login_url='user_login')
def home(request):
    teacher = Teacher.objects.get(user__email=request.user.email)
    
    return render(request, 'home.html',{'teacher':teacher})

def register(request):
    if request.method == 'POST':
        st_nm = request.POST.get('student_name' , None)
        st_age=request.POST.get('student_age',None)
        st_email=request.POST.get('student_email',None)
        st_phone=request.POST.get('student_phone',None)
        st_password=""
        for i in range(0,4):
            st_password+=st_nm[i]
        st_password+="@123"

        print("st_password" , st_password)

        user = NewUsers.objects.create(name = st_nm,age=st_age,email=st_email,phone_number=st_phone,password=st_password)

        user.save()

        Student.objects.create(user=user)

        return redirect('home')
        
    else:
        return render(request, 'register.html')


def display_students(request):
    # Read filter parameters from the query string.
    q = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '')

    students = Student.objects.all()
    if q:
        students = students.filter(user__name__icontains=q)
    if class_id.isdigit():
        students = students.filter(class_name_id=int(class_id))
    # Stable ordering avoids inconsistent pagination results.
    students = students.order_by('id')

    paginator = Paginator(students, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Build a querystring (without `page`) so pagination links preserve the
    # active filters. Trailing '&' (or empty string) keeps the template simple.
    params = {}
    if q:
        params['q'] = q
    if class_id:
        params['class'] = class_id
    filter_querystring = urlencode(params)
    if filter_querystring:
        filter_querystring += '&'

    context = {
        'page_obj': page_obj,
        'classes': Class_name.objects.all(),
        'q': q,
        'selected_class': class_id,
        'filter_querystring': filter_querystring,
    }
    return render(request, 'display_students.html', context)

def delete_student(request, student_id):
    if request.method == 'POST':  # Only allow POST requests for delete
        try:
            student = get_object_or_404(Student, id=student_id)
            student.user.delete()  # Delete the user associated with the student
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # If the request is not POST, return a JSON error
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

def update_student(request,student_id):
    student=get_object_or_404(Student,id = student_id)
    if request.method == 'POST':
        
        student.user.name = request.POST.get('student_name', student.user.name)
        student.user.age = request.POST.get('student_age', student.user.age)
        student.user.email = request.POST.get('student_email', student.user.email)
        student.user.phone_number = request.POST.get('student_phone', student.user.phone_number)

        student.user.save()  # Save the updated data
        
        return redirect('display_students')
        
        
    else:
        return render(request, 'register.html', {
                'is_update': True,
                'student': student
            })
    
    
def student_home(request):
    student = Student.objects.get(user__email=request.user.email)
    
    return render(request,'student_home.html',{'student':student})

def update_details(request):
    student = Student.objects.get(user__email=request.user.email)
    if request.method=='POST':
        student.aadhar=request.POST.get('student_aadhar',student.aadhar)
        student.address=request.POST.get('student_address',student.address)

        if 'student_profile_picture' in request.FILES:
            student.profile_picture = request.FILES['student_profile_picture']

        student.save()
        return redirect('student_home')
    return render(request,'update_details.html',{'student':student})


from django.http import JsonResponse



def update_student_ajax(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        name = request.POST.get('name')
        age = request.POST.get('age')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        try:
            student = Student.objects.get(id=student_id)
            student.user.name = name
            student.user.age = age
            student.user.email = email
            student.user.phone_number = phone
            student.user.save()

            return JsonResponse({'success': True})

        except Student.DoesNotExist:
            return JsonResponse({'success': False})

    return JsonResponse({'success': False})


def principal_home(request):
    principal=Principal.objects.get(user__email=request.user.email)
    teacher_count = Teacher.objects.count()
    student_count = Student.objects.count()
    class_count = Class_name.objects.count()
    section_count = Section.objects.count()
    subject_count = Subject.objects.count()

    teachers = Teacher.objects.all()
    students = Student.objects.all()
    classes = Class_name.objects.all()
    sections = Section.objects.all()
    subjects = Subject.objects.all()

    return render(request,'principal_home.html',{
        'principal':principal,
        'teacher_count': teacher_count,
        'student_count': student_count,
        'class_count': class_count,
        'section_count': section_count,
        'subject_count': subject_count,
        'teachers': teachers,
        'students': students,
        'classes': classes,
        'sections': sections,
        'subjects': subjects})

def update_principal_student_ajax(request):
    print("update_principal_student_ajax function get called")
    if request.method == 'POST':
        student_id=request.POST.get('student_id')
        name = request.POST.get('name')
        class_name_id=request.POST.get('class_name')
        section_id=request.POST.get('section')
        email=request.POST.get('email')
        phone_number=request.POST.get('phone_number')

        print(request.POST)

        try:
            student=Student.objects.get(id=student_id)
            
            class_name_obj = Class_name.objects.get(id=int(class_name_id))
            section = Section.objects.get(id=int(section_id))
           
            student.user.name = name
            student.class_name= class_name_obj
            student.sections= section
            student.user.email=email
            student.user.phone_number=phone_number
            student.user.save()
            student.save()

            return JsonResponse({'success':True})
        
        except Student.DoesNotExist:
            return JsonResponse({'success':False})
        
    return JsonResponse({'success':False})

def add_principal_student_ajax(request):
    if request.method == 'POST':
        
        st_nm = request.POST.get('name' , None)
        class_name=request.POST.get('class_name',None)
        section=request.POST.get('section',None)
        st_email=request.POST.get('email',None)
        st_phone=request.POST.get('phone_number',None)
        st_password=""
        for i in range(0,4):
            st_password+=st_nm[i]
        st_password+="@123"
        # Here, create the new student and user
        try:
            user = NewUsers.objects.create(
                name=st_nm,
                email=st_email,
                phone_number=st_phone,
                password=st_password,  
            )
            user.save()
            class_name_obj = Class_name.objects.get(id=int(class_name))
            section = Section.objects.get(id=int(section))
            student=Student.objects.create(
                user=user,
                class_name= class_name_obj,
                sections= section
                )
           
            student.save()
            
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})



def delete_class(request, class_id):
    if request.method == 'POST':  # Only allow POST requests for delete
        try:
            class_name = get_object_or_404(Class_name, id=class_id)
            class_name.delete()  # Delete the user associated with the student
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        

def update_principal_class_ajax(request):
    if request.method == 'POST':
        
        
        class_id=request.POST.get('class_name',None)
        
        
        # Here, create the new student and user
        try:

            class_name_obj = Class_name.objects.get(id=int(class_id))
            class_name = Class_name.objects.create(
                name= class_name_obj.name
                
            )
            class_name.save()
            
            
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})



def class_students(request, class_id):
    
    class_instance = get_object_or_404(Class_name, id=class_id)
   
    students = Student.objects.filter(class_name=class_instance)
    teachers = Teacher.objects.filter(class_name=class_instance)
    sections= Section.objects.all()

    context = {
        'class_name': class_instance, 
        'students': students,               
        'teachers': teachers,             
        'sections':sections
    }

    return render(request, 'class_students.html', context)

def section_students(request, class_id, section_id):
   
    class_instance = get_object_or_404(Class_name, id=class_id)
    section_instance = get_object_or_404(Section, id=section_id)
   
    students = Student.objects.filter(class_name=class_instance, sections=section_instance)

    context = {
        'class_name': class_instance,
        'section_name': section_instance.name,
        'students': students,
    }

    return render(request, 'section_students.html', context)