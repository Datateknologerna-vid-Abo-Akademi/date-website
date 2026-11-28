import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


logger = logging.getLogger('date')


class AuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Other backends (e.g. passkeys) call authenticate() without credentials;
        # email is nullable, so looking up email=None could match many rows.
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(email=username)
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=username)
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
            except User.DoesNotExist:
                return None
