from django.utils.translation import gettext_lazy as _
from jet.dashboard import modules
from jet.dashboard.dashboard import Dashboard, AppIndexDashboard

# For more info on Jet dashboard modules: https://django-jet-reboot.readthedocs.io/en/latest/dashboard_modules.html
# We might want to customize this more!
#
# Furhtermore, there is the possibility of introducing google analytics to the website if we so wish.
# However, a discussion should probably be had if that is even something we need/want.

class CustomIndexDashboard(Dashboard):
    columns = 2

    def init_with_context(self, context):
        self.available_children.append(modules.LinkList)
        self.children.append(modules.AppList(
            _('Applications'),
            exclude=('auth.*',),
            column=0,
            order=0
        ))
        self.children.append(modules.RecentActions(
            _('Recent Actions'),
            10,
            column=1,
            order=0
        ))
