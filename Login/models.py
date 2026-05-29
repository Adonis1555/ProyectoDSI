from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager, PermissionsMixin

class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class Usuario(AbstractUser):
    ROL_CHOICES=[
        ('directora', 'Directora'),
        ('maestro', 'Maestro'),
        ('responsable', 'Responsable'),
    ]
    username = None

    email= models.EmailField(unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    rol        = models.CharField(max_length=20, choices=ROL_CHOICES)
    activo     = models.BooleanField(default=True)
    fecha_creacion      = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS=['nombre','apellido','rol']

    def es_directora(self): 
        return self.rol=="directora"
    def es_maestro(self): 
        return self.rol == "maestro"
    def es_responsable(self): 
        return self.rol== "responsable"




# Create your models here.
