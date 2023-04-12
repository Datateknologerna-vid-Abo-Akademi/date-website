import logging

from django.contrib.auth import get_user_model
# import ldap3
from django.contrib.auth.backends import ModelBackend

# from members.models import Member

User = get_user_model()


logger = logging.getLogger('date')


class AuthBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=username)
                if user.check_password(password):
                    return user
            except User.DoesNotExist:
                return None
