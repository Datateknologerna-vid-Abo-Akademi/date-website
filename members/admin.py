from django.contrib import admin
from django.contrib.auth import admin as auth_admin

from members.forms import MemberCreationForm, MemberUpdateForm
from members.models import Member


class UserAdmin(auth_admin.UserAdmin):
    fieldsets = (
        (None, {'fields': MemberUpdateForm.Meta.fields}),
    )
    add_fieldsets = (
        (None, {'fields': MemberCreationForm.Meta.fields}),
    )

    form = MemberUpdateForm
    add_form = MemberCreationForm
    list_display = ('email', 'first_name', 'last_name', 'membership_type', 'is_staff')
    list_filter = ('membership_type', 'is_active', 'groups')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ('email', )
    readonly_fields = ('last_login',)


admin.site.register(Member, UserAdmin)
