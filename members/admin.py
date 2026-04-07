from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Permission
from django.db.models import Exists, OuterRef
from django.db.models.functions import Lower
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from members.forms import (MemberCreationForm, AdminMemberUpdateForm,
                           SubscriptionPaymentForm, SubscriptionPaymentChoiceField)
from members.models import (Member, Subscription,
                            SubscriptionPayment, FunctionaryRole, Functionary, MembershipType)

admin.site.register(Permission)
admin.site.register(Subscription)


class TOTPDeviceInline(admin.TabularInline):
    model = TOTPDevice
    extra = 0
    max_num = 0
    can_delete = True
    fields = ('name', 'created_at', 'last_used_at')
    readonly_fields = ('name', 'created_at', 'last_used_at')
    verbose_name = "2FA device"
    verbose_name_plural = "2FA devices"


class StaticDeviceInline(admin.TabularInline):
    model = StaticDevice
    extra = 0
    max_num = 0
    can_delete = True
    fields = ('name', 'token_count')
    readonly_fields = ('name', 'token_count')
    verbose_name = "Backup token device"
    verbose_name_plural = "Backup token devices"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('token_set')

    def token_count(self, obj):
        return len(obj.token_set.all())

    token_count.short_description = "Tokens remaining"

FRESHMAN = 1
ORDINARY_MEMBER = 2
SUPPORTING_MEMBER = 3
SENIOR_MEMBER = 4


@admin.register(Member)
class UserAdmin(auth_admin.UserAdmin):
    fieldsets = (
        (None, {'fields': AdminMemberUpdateForm.Meta.fields}),
    )
    add_fieldsets = (
        (None, {'fields': MemberCreationForm.Meta.fields}),
    )

    form = AdminMemberUpdateForm
    add_form = MemberCreationForm
    list_display = ('username', 'first_name', 'last_name', 'email', 'membership_type', 'is_active', 'is_staff', 'has_two_factor')
    list_filter = ('membership_type', 'is_active', 'groups')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = [Lower('username'), ]
    readonly_fields = ('last_login', 'has_two_factor')
    inlines = [TOTPDeviceInline, StaticDeviceInline]
    actions = ['activate_user', 'deactivate_user', 'disable_two_factor']

    def is_staff(self, obj):
        return obj.is_staff

    is_staff.boolean = True

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        confirmed_devices = TOTPDevice.objects.filter(user=OuterRef('pk'), confirmed=True)
        return queryset.annotate(_has_two_factor=Exists(confirmed_devices))

    def has_two_factor(self, obj):
        return obj._has_two_factor

    has_two_factor.boolean = True
    has_two_factor.short_description = "2FA"

    def activate_user(self, request, queryset):
        queryset.update(is_active=True)

    activate_user.short_description = "Aktivera användare"

    def deactivate_user(self, request, queryset):
        queryset.update(is_active=False)

    deactivate_user.short_description = "Deaktivera användare"

    def disable_two_factor(self, request, queryset):
        totp_qs = TOTPDevice.objects.filter(user__in=queryset)
        static_qs = StaticDevice.objects.filter(user__in=queryset)
        total = totp_qs.count() + static_qs.count()
        totp_qs.delete()
        static_qs.delete()
        self.message_user(request, f"2FA inaktiverat för valda medlemmar: {total} enhet(er) borttagna.")

    disable_two_factor.short_description = "Inaktivera 2FA"

    def sorter_username(self, queryset):
        return Member.objects.all().order_by(Lower('username')).values_list('username', flat=True)


admin.site.register(MembershipType)


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    form = SubscriptionPaymentForm
    fields = SubscriptionPaymentForm.Meta.fields
    list_display = ('full_name', 'subscription', 'is_active', 'expires')
    list_filter = ('subscription', 'date_expires')

    def full_name(self, obj):
        return obj.member.get_full_name()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'member':
            return SubscriptionPaymentChoiceField(queryset=Member.objects.all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Functionary)
class FunctionaryAdmin(admin.ModelAdmin):
    list_filter = ('functionary_role', 'year')
    search_fields = ('member__first_name', 'member__last_name', 'functionary_role__title', 'year')
    ordering = ['-year', ]


@admin.register(FunctionaryRole)
class FunctionaryRoleAdmin(admin.ModelAdmin):
    list_filter = ('board',)
    search_fields = ('title',)
    ordering = ['title', ]
