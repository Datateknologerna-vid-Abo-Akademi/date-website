from django.contrib.auth.backends import ModelBackend
import ldap

import logging

logger = logging.getLogger('date')


class AuthBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        # if '@' not in username or '@abo.fi' in username:
        #     ldap_server = "ldap://authur.abo.fi"
        #     base_dn = "dc=abo,dc=fi"
        #     user_dn = "uid="+username+",ou=unixaccounts,ou=accounts,dc=abo,dc=fi"
        #     connect = ldap.open(ldap_server)
        #     search_filter = "uid=" + username
        #     try:
        #         # if authentication successful, get the full user data
        #         connect.bind_s(user_dn, password)
        #         result = connect.search_s(base_dn, ldap.SCOPE_SUBTREE, search_filter)
        #         # return all user data results
        #         connect.unbind_s()
        #         logger.info(result)
        #     except ldap.LDAPError:
        #         connect.unbind_s()
        #         logger.debug("Not no no oof oh no")

        user = ModelBackend.authenticate(request, username, password, kwargs)
        return user
