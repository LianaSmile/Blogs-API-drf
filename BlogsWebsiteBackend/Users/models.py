from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
    Group,
    Permission
)

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import signals
from rest_framework_simplejwt.tokens import RefreshToken
import logging

logger = logging.getLogger('main')


class CustomUserManager(BaseUserManager):
    def create_user(self, first_name, last_name, email, user_name, password, **other_fields):
        if not email:
            raise ValueError(_('Email is required!'))

        email = self.normalize_email(email)
        user = self.model(first_name=first_name, last_name=last_name,
                          email=email, user_name=user_name, **other_fields)

        user.set_password(password)
        user.save()

        return user

    def create_superuser(self, first_name, last_name, email, user_name, password, **other_fields):
        other_fields.setdefault('is_staff', True)
        other_fields.setdefault('is_superuser', True)

        if other_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must be assigned to is_staff=True.'))

        if other_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must be assigned to is_superuser=True.'))

        return self.create_user(first_name, last_name, email, user_name, password, **other_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        MODERATOR = 'MODERATOR', 'Moderator'
        NON_ADMIN = 'NON_ADMIN', 'Non-admin'

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(_('email address'), unique=True)
    user_name = models.CharField(max_length=150, unique=True)
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.NON_ADMIN)
    created_at = models.DateTimeField(auto_now_add=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name="user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="user_set",
        related_query_name="user",
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_name', 'first_name', 'last_name']

    def __str__(self):
        return self.user_name

    def tokens(self):
        refresh = RefreshToken.for_user(self)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }


@receiver(post_save, sender=User)
def status(sender, instance, **kwargs):
    view = Permission.objects.get(name='Can view post')
    add = Permission.objects.get(name='Can add post')
    change = Permission.objects.get(name='Can change post')
    delete = Permission.objects.get(name='Can delete post')
    permissions = [view, add, change, delete]

    if instance.is_superuser:
        instance.role = 'ADMIN'

    if instance.role in ['MODERATOR', 'ADMIN']:
        instance.is_staff = True

        if instance.role == 'ADMIN':
            instance.is_superuser = True

        logger.info('Adding post permissions to a user with a role ADMIN or MODERATOR!')
        for permission in permissions:
            instance.user_permissions.add(permission)
    else:
        instance.is_staff = False
        logger.info('Removing post permissions for a user with a role NON_ADMIN!')
        for permission in permissions:
            instance.user_permissions.remove(permission)

    signals.post_save.disconnect(status, sender=User)
    logger.info('Creating or updating a user!')
    instance.save()
    signals.post_save.connect(status, sender=User)
