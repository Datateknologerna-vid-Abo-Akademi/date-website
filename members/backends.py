import logging

#import ldap3
import requests
from django.contrib.auth.backends import ModelBackend
from requests.auth import HTTPBasicAuth
from django.contrib.auth import get_user_model
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


        '''
        OLD ABO AND LDAP CODE
        '''

        # if '@' not in username or '@abo.fi' in username:
        #     if '@abo.fi' in username:
        #         username = username.split('@')[0]
        #     r = requests.post('https://oldwww.abo.fi/personal', auth=HTTPBasicAuth(username, password))
        #     logger.debug("Authenticating against oldwww.abo.fi " + str(r.status_code))
        #     if r.status_code == 200:
        #         try:
        #             user = Member.objects.get(username=username)
        #             return user
        #         except Member.DoesNotExist:
        #             logger.debug("User {} not registered".format(username))

            # ldap_server = ldap3.Server("authur.abo.fi", get_info=ldap3.ALL, use_ssl=False)
            # base_dn = "dc=abo,dc=fi"
            # user_dn = "uid="+username+",ou=unixaccounts,ou=accounts,dc=abo,dc=fi"
            # search_filter = "(uid=" + username + ")"
            # try:
            #     ldap_conn = ldap3.Connection(ldap_server, user_dn, password, auto_bind=True)
            #     # if authentication successful, get the full user data
            #     ldap_search = ldap_conn.search(base_dn, search_filter)
            #     if ldap_search:
            #         logger.info(ldap_conn.entries)
            #
            #     # user = Member.objects.get(username=username)
            #     # return user
            # except Exception as e:
            #     logger.debug(e)
            #     logger.debug("Not no no oof oh no")



        return None
