from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .models import Student, Teacher, NewUsers, Principal, Class_name, Section, Subject


def _generate_default_password(name):
    return (name[:4] if len(name) >= 4 else name) + "@123"


def _is_teacher(user):
    return hasattr(user, 'teacher')


def _is_principal(user):
    return hasattr(user, 'principal')


def _is_student(user):
    return hasattr(user, 'student')


def user_login(request):
    if request.method == 'POST':
        user_email = request.POST.get('user_email', None)
        user_password = request.POST.get('user_password', None)

        user = authenticate(request, email=user_email, password=user_password)

        if user:
            if user.is_staff:
                if _is_teacher(user):
                    login(request, user)
                    return redirect('home')
                elif _is_principal(user):
                    login(request, user)
                    return redirect('principal_home')
                else:
                    return render(request, 'login.html', {'error': 'Invalid credentials'})
            else:
                login(request, user)
                return redirect('student_home')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


def register(request):
    if request.method == 'POST':
        st_nm = request.POST.get('student_name', None)
        st_age = request.POST.get('student_age', None)
        st_email = request.POST.get('student_email', None)
        st_phone = request.POST.get('student_phone', None)

        if not st_nm or len(st_nm.strip()) == 0:
            return render(request, 'register.html', {'error': 'Name is required'})

        st_password = _generate_default_password(st_nm.strip())

        try:
            user = NewUsers.objects.create_user(
                email=st_email,
                password=st_password,
                name=st_nm,
                age=st_age,
                phone_number=st_phone,
            )
            Student.objects.create(user=user)
            return redirect('home')
        except Exception:
            return render(request, 'register.html', {'error': 'Registration failed. Email or phone may already be in use.'})
    else:
        return render(request, 'register.html')


@login_required(login_url='user_login')
def home(request):
    if not _is_teacher(request.user):
        return HttpResponseForbidden("Access denied")
    try:
        teacher = Teacher.objects.get(user__email=request.user.email)
    except Teacher.DoesNotExist:
        return HttpResponseForbidden("Access denied")
    return render(request, 'home.html', {'teacher': teacher})


@login_required(login_url='user_login')
def display_students(request):
    if not _is_teacher(request.user) and not _is_principal(request.user):
        return HttpResponseForbidden("Access denied")
    student = Student.objects.all()
    paginator = Paginator(student, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'display_students.html', {'page_obj': page_obj})


@login_required(login_url='user_login')
def delete_student(request, student_id):
    if not _is_principal(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    if request.method == 'POST':
        try:
            student = get_object_or_404(Student, id=student_id)
            student.user.delete()
            return JsonResponse({'success': True})
        except Exception:
            return JsonResponse({'success': False, 'error': 'An error occurred'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required(login_url='user_login')
def update_student(request, student_id):
    if not _is_teacher(request.user):
        return HttpResponseForbidden("Access denied")
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        student.user.name = request.POST.get('student_name', student.user.name)
        student.user.age = request.POST.get('student_age', student.user.age)
        student.user.email = request.POST.get('student_email', student.user.email)
        student.user.phone_number = request.POST.get('student_phone', student.user.phone_number)
        student.user.save()
        return redirect('display_students')
    else:
        return render(request, 'register.html', {
            'is_update': True,
            'student': student
        })


@login_required(login_url='user_login')
def student_home(request):
    if not _is_student(request.user):
        return HttpResponseForbidden("Access denied")
    try:
        student = Student.objects.get(user__email=request.user.email)
    except Student.DoesNotExist:
        return HttpResponseForbidden("Access denied")
    return render(request, 'student_home.html', {'student': student})


@login_required(login_url='user_login')
def update_details(request):
    if not _is_student(request.user):
        return HttpResponseForbidden("Access denied")
    try:
        student = Student.objects.get(user__email=request.user.email)
    except Student.DoesNotExist:
        return HttpResponseForbidden("Access denied")
    if request.method == 'POST':
        student.aadhar = request.POST.get('student_aadhar', student.aadhar)
        student.address = request.POST.get('student_address', student.address)
        if 'student_profile_picture' in request.FILES:
            student.profile_picture = request.FILES['student_profile_picture']
        student.save()
        return redirect('student_home')
    return render(request, 'update_details.html', {'student': student})


@login_required(login_url='user_login')
def update_student_ajax(request):
    if not _is_teacher(request.user) and not _is_principal(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
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


@login_required(login_url='user_login')
def principal_home(request):
    if not _is_principal(request.user):
        return HttpResponseForbidden("Access denied")
    try:
        principal = Principal.objects.get(user__email=request.user.email)
    except Principal.DoesNotExist:
        return HttpResponseForbidden("Access denied")
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

    return render(request, 'principal_home.html', {
        'principal': principal,
        'teacher_count': teacher_count,
        'student_count': student_count,
        'class_count': class_count,
        'section_count': section_count,
        'subject_count': subject_count,
        'teachers': teachers,
        'students': students,
        'classes': classes,
        'sections': sections,
        'subjects': subjects
    })


@login_required(login_url='user_login')
def update_principal_student_ajax(request):
    if not _is_principal(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        name = request.POST.get('name')
        class_name_id = request.POST.get('class_name')
        section_id = request.POST.get('section')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')

        try:
            student = Student.objects.get(id=student_id)
            class_name_obj = Class_name.objects.get(id=int(class_name_id))
            section = Section.objects.get(id=int(section_id))

            student.user.name = name
            student.class_name = class_name_obj
            student.sections = section
            student.user.email = email
            student.user.phone_number = phone_number
            student.user.save()
            student.save()

            return JsonResponse({'success': True})

        except (Student.DoesNotExist, Class_name.DoesNotExist, Section.DoesNotExist):
            return JsonResponse({'success': False})

    return JsonResponse({'success': False})


@login_required(login_url='user_login')
def add_principal_student_ajax(request):
    if not _is_principal(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    if request.method == 'POST':
        st_nm = request.POST.get('name', None)
        class_name = request.POST.get('class_name', None)
        section = request.POST.get('section', None)
        st_email = request.POST.get('email', None)
        st_phone = request.POST.get('phone_number', None)

        if not st_nm or len(st_nm.strip()) == 0:
            return JsonResponse({'success': False, 'error': 'Name is required'})

        st_password = _generate_default_password(st_nm.strip())

        try:
            user = NewUsers.objects.create_user(
                email=st_email,
                password=st_password,
                name=st_nm,
                phone_number=st_phone,
            )
            class_name_obj = Class_name.objects.get(id=int(class_name))
            section_obj = Section.objects.get(id=int(section))
            student = Student.objects.create(
                user=user,
                class_name=class_name_obj,
                sections=section_obj
            )
            student.save()
            return JsonResponse({'success': True})
        except Exception:
            return JsonResponse({'success': False, 'error': 'An error occurred'})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required(login_url='user_login')
def delete_class(request, class_id):
    if not _is_principal(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    if request.method == 'POST':
        try:
            class_name = get_object_or_404(Class_name, id=class_id)
            class_name.delete()
            return JsonResponse({'success': True})
        except Exception:
            return JsonResponse({'success': False, 'error': 'An error occurred'})


@login_required(login_url='user_login')
def update_principal_class_ajax(request):
    if not _is_principal(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    if request.method == 'POST':
        class_id = request.POST.get('class_name', None)
        new_name = request.POST.get('name', None)

        try:
            class_name_obj = Class_name.objects.get(id=int(class_id))
            if new_name:
                class_name_obj.name = new_name
                class_name_obj.save()
            return JsonResponse({'success': True})
        except Class_name.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Class not found'})
        except Exception:
            return JsonResponse({'success': False, 'error': 'An error occurred'})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required(login_url='user_login')
def class_students(request, class_id):
    if not _is_teacher(request.user) and not _is_principal(request.user):
        return HttpResponseForbidden("Access denied")
    class_instance = get_object_or_404(Class_name, id=class_id)
    students = Student.objects.filter(class_name=class_instance)
    teachers = Teacher.objects.filter(class_name=class_instance)
    sections = Section.objects.all()
    context = {
        'class_name': class_instance,
        'students': students,
        'teachers': teachers,
        'sections': sections
    }
    return render(request, 'class_students.html', context)


@login_required(login_url='user_login')
def section_students(request, class_id, section_id):
    if not _is_teacher(request.user) and not _is_principal(request.user):
        return HttpResponseForbidden("Access denied")
    class_instance = get_object_or_404(Class_name, id=class_id)
    section_instance = get_object_or_404(Section, id=section_id)
    students = Student.objects.filter(class_name=class_instance, sections=section_instance)
    context = {
        'class_name': class_instance,
        'section_name': section_instance.name,
        'students': students,
    }
    return render(request, 'section_students.html', context)
