from django.contrib import admin
from django.contrib.auth import admin as auth_admin

from members.forms import MemberCreationForm, MemberUpdateForm, SubscriptionPaymentForm
from members.models import Member, Subscription, SubscriptionPayment, MEMBERSHIP_TYPES
from django.contrib.auth.models import Permission

admin.site.register(Permission)
admin.site.register(Subscription)

FRESHMAN = 1
ORDINARY_MEMBER = 2
SUPPORTING_MEMBER = 3
SENIOR_MEMBER = 4


@admin.register(Member)
class UserAdmin(auth_admin.UserAdmin):
    fieldsets = (
        (None, {'fields': MemberUpdateForm.Meta.fields}),
    )
    add_fieldsets = (
        (None, {'fields': MemberCreationForm.Meta.fields}),
    )

    form = MemberUpdateForm
    add_form = MemberCreationForm
    list_display = ('username', 'first_name', 'last_name', 'email', 'membership_type', 'is_active', 'is_staff')
    list_filter = ('membership_type', 'is_active', 'groups')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ('username', )
    readonly_fields = ('last_login',)
    actions = ['activate_user', 'deactivate_user', 'make_ordinary_member', 'make_senior_member']

    def is_staff(self, obj):
        return obj.is_staff
    is_staff.boolean = True

    def activate_user(self, request, queryset):
        queryset.update(is_active=True)
    activate_user.short_description = "Aktivera användare"

    def deactivate_user(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_user.short_description = "Deaktivera användare"

    def make_ordinary_member(self, request, queryset):
        queryset.update(membership_type=ORDINARY_MEMBER)
    make_ordinary_member.short_description = "Sätt medlem till ordinariemedlem"

    def make_senior_member(self, request, queryset):
        queryset.update(membership_type=SENIOR_MEMBER)
    make_senior_member.short_description = "Sätt medlem till seniormedlem"


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    form = SubscriptionPaymentForm
    fields = SubscriptionPaymentForm.Meta.fields
    list_display = ('member', 'subscription', 'is_active', 'expires')
    list_filter = ('subscription', 'member', 'date_expires')
