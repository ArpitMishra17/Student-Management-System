from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import FileExtensionValidator

# Create your models here.


class CustomAccountManager(BaseUserManager):

    def create_superuser(self, email ,password, **other_fields):

        other_fields.setdefault('is_staff', True)
        other_fields.setdefault('is_superuser', True)
        other_fields.setdefault('is_active', True)

        if other_fields.get('is_staff') is not True:
            raise ValueError(
                'Superuser must be assigned to is_staff=True.')
        if other_fields.get('is_superuser') is not True:
            raise ValueError(
                'Superuser must be assigned to is_superuser=True.')

        return self.create_user(email,password, **other_fields)

    def create_user(self,email, password, **other_fields):
        if not email:
            raise ValueError('You must provide an email')

        email = self.normalize_email(email)
        user = self.model( email=email,
                        **other_fields)
        user.set_password(password)
        user.is_active = True
        user.save()
        return user
    
class NewUsers(AbstractBaseUser, PermissionsMixin):
    id= models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField(null=True, blank=True)
    phone_number = models.CharField(max_length=13, unique=True, null=True, blank=True)

    # Permissions fields
    is_staff = models.BooleanField(default=False)  
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    

    # Manager
    objects = CustomAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    
    

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith("pbkdf2_"):
            self.set_password(self.password)  # Automatically hash the password
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.email)
    



class Student(models.Model):

    user = models.OneToOneField(NewUsers , on_delete= models.CASCADE, null=True )
    aadhar = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=100, null=True, blank=True)

    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg','jpeg','png'])]
    )

    
    class_name= models.ForeignKey("Class_name", on_delete=models.CASCADE,blank=True,null=True)
    sections = models.ForeignKey("Section", on_delete=models.CASCADE,blank=True,null=True)
    subjects = models.ManyToManyField("Subject", related_name='students', blank=True)
    periods = models.ManyToManyField("Period", related_name='students', blank=True)

    
    def save(self, *args, **kwargs):
        self.user.is_staff = False
        self.user.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.name
    

# Teacher Model
class Teacher(models.Model):
    
    user= models.OneToOneField(NewUsers , on_delete= models.CASCADE, null=True )
    gender = models.CharField(max_length=10, choices=(("Male", "Male"), ("Female", "Female")))
    user_type=models.CharField(max_length=100,default="Teacher")

    
    class_name=models.ManyToManyField("Class_name",related_name='teachers',blank=True)
    sections = models.ManyToManyField("Section", related_name='teachers', blank=True)
    subjects = models.ManyToManyField("Subject", related_name='assigned_teachers', blank=True)
    periods = models.ManyToManyField("Period", related_name='teachers', blank=True)

    def save(self, *args, **kwargs):
        self.user.is_staff = True
        self.user.save()
        super().save(*args, **kwargs)
    def __str__(self):
        return self.user.name

   
class Class_name(models.Model):

    id= models.AutoField(primary_key=True)
    name=models.CharField(max_length=100,unique=True)

    def __str__(self):
        return self.name

class Section(models.Model):

    id= models.AutoField(primary_key=True)
    name=models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.name}"   

class Subject(models.Model):

    id= models.AutoField(primary_key=True)
    name=models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.name}" 

class Period(models.Model):

    id= models.AutoField(primary_key=True)
    class_name=models.ForeignKey(Class_name,on_delete=models.CASCADE,related_name='periods',null=True)
    subject=models.ForeignKey(Subject,on_delete=models.CASCADE, related_name='periods')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='periods')
    
    
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.subject.name} - {self.class_name.name} - {self.section.name} ({self.start_time} - {self.end_time})"


class Principal(models.Model):
    user= models.OneToOneField(NewUsers , on_delete= models.CASCADE, null=True )
    user_type=models.CharField(max_length=100,default="Principal")

    def save(self, *args, **kwargs):
        self.user.is_staff = True
        self.user.save()
        super().save(*args, **kwargs)
    def __str__(self):
        return self.user.name