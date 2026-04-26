from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Permission
from django.db.models import CharField, Exists, F, OuterRef, Q, Value
from django.db.models.functions import Lower, Replace
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from core.admin_base import ModelAdmin, TabularInline

from members.forms import (MemberCreationForm, AdminMemberUpdateForm,
                           SubscriptionPaymentForm, SubscriptionPaymentChoiceField)
from members.models import (Member, Subscription,
                            SubscriptionPayment, FunctionaryRole, Functionary, MembershipType)


@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ('name', 'content_type', 'codename')
    search_fields = ('name', 'codename', 'content_type__app_label', 'content_type__model')
    list_filter = ('content_type__app_label',)
    ordering = ('content_type__app_label', 'content_type__model', 'codename')


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('name', 'price', 'does_expire', 'renewal_period', 'renewal_scale')
    search_fields = ('name',)
    list_filter = ('does_expire',)
    ordering = ('name',)


class TOTPDeviceInline(TabularInline):
    model = TOTPDevice
    extra = 0
    max_num = 0
    can_delete = True
    fields = ('name', 'created_at', 'last_used_at')
    readonly_fields = ('name', 'created_at', 'last_used_at')
    verbose_name = "2FA device"
    verbose_name_plural = "2FA devices"


class StaticDeviceInline(TabularInline):
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


# Direct `class UserAdmin(ModelAdmin, auth_admin.UserAdmin)` would fail when
# USE_UNFOLD=False because ModelAdmin then IS admin.ModelAdmin — placing it before
# its own subclass (auth_admin.UserAdmin) violates C3 MRO. The shim is only
# introduced when Unfold's ModelAdmin is a distinct class that sits above both.
if getattr(settings, 'USE_UNFOLD', False):
    class _UserAdminBase(ModelAdmin, auth_admin.UserAdmin):
        pass
else:
    _UserAdminBase = auth_admin.UserAdmin


@admin.register(Member)
class UserAdmin(_UserAdminBase):
    fieldsets = (
        (None, {'fields': AdminMemberUpdateForm.Meta.fields}),
    )
    add_fieldsets = (
        (None, {'fields': MemberCreationForm.Meta.fields}),
    )

    form = AdminMemberUpdateForm
    add_form = MemberCreationForm
    list_display = (
        'username',
        'first_name',
        'last_name',
        'email',
        'membership_type',
        'year_of_admission',
        'is_active',
        'is_staff',
        'has_two_factor',
    )
    list_filter = ('membership_type', 'year_of_admission', 'is_active', 'groups')
    autocomplete_fields = ('membership_type', 'groups')
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'phone',
        'address',
        'zip_code',
        'city',
        'country',
        'membership_type__name',
        'groups__name',
        'subscriptionpayment__subscription__name',
    )
    search_help_text = _(
        'Search by name, username, email, phone, address, postal code, city, '
        'membership type, group, subscription, admission year, member ID, or GitHub ID.'
    )
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
        return queryset.select_related('membership_type').prefetch_related('groups').annotate(
            _has_two_factor=Exists(confirmed_devices)
        )

    def get_search_results(self, request, queryset, search_term):
        base_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        search_term = search_term.strip()

        if not search_term:
            return queryset, may_have_duplicates

        extra_query = Q()

        for term in search_term.split():
            if term.isdigit():
                numeric_term = int(term)
                extra_query |= Q(pk=numeric_term)
                extra_query |= Q(year_of_admission=numeric_term)
                extra_query |= Q(github_id=numeric_term)

        phone_digits = ''.join(char for char in search_term if char.isdigit())
        if len(phone_digits) >= 4:
            phone_variants = {phone_digits}
            if phone_digits.startswith('0') and len(phone_digits) > 1:
                phone_variants.add(phone_digits[1:])
                phone_variants.add('358' + phone_digits[1:])
            elif phone_digits.startswith('358') and len(phone_digits) > 3:
                phone_variants.add('0' + phone_digits[3:])
                phone_variants.add(phone_digits[3:])

            # Strip all punctuation/spacing from the stored phone number so
            # digit-only search variants can match regardless of formatting.
            phone_digits_annotation = Replace(
                Replace(
                    Replace(
                        Replace(
                            Replace(
                                Replace(
                                    Replace(F('phone'), Value(' '), Value('')),
                                    Value('-'),
                                    Value(''),
                                ),
                                Value('+'),
                                Value(''),
                            ),
                            Value('('),
                            Value(''),
                        ),
                        Value(')'),
                        Value(''),
                    ),
                    Value('.'),
                    Value(''),
                ),
                Value('/'),
                Value(''),
                output_field=CharField(),
            )

            # Ensure both querysets have matching selected columns before OR-combining.
            queryset = queryset.annotate(_phone_digits=phone_digits_annotation)
            base_queryset = base_queryset.annotate(_phone_digits=phone_digits_annotation)
            phone_query = Q()
            for variant in phone_variants:
                phone_query |= Q(_phone_digits__icontains=variant)
            extra_query |= phone_query

        if extra_query:
            queryset = queryset | base_queryset.filter(extra_query)
            may_have_duplicates = True

        return queryset, may_have_duplicates

    def has_two_factor(self, obj):
        return obj._has_two_factor

    has_two_factor.boolean = True
    has_two_factor.short_description = "2FA"

    def activate_user(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("Aktiverade %(count)d användare.") % {'count': updated})

    activate_user.short_description = "Aktivera användare"

    def deactivate_user(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("Deaktiverade %(count)d användare.") % {'count': updated})

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


@admin.register(MembershipType)
class MembershipTypeAdmin(ModelAdmin):
    list_display = ('name', 'permission_profile')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(ModelAdmin):
    form = SubscriptionPaymentForm
    fields = SubscriptionPaymentForm.Meta.fields
    list_display = ('full_name', 'subscription', 'is_active', 'expires')
    list_filter = ('subscription', 'date_expires')
    search_fields = ('member__first_name', 'member__last_name', 'member__username', 'member__email', 'subscription__name')
    autocomplete_fields = ('subscription',)
    list_select_related = ('member', 'subscription')
    ordering = ('-date_paid',)
    date_hierarchy = 'date_paid'

    def full_name(self, obj):
        return obj.member.get_full_name()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'member':
            return SubscriptionPaymentChoiceField(queryset=Member.objects.all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Functionary)
class FunctionaryAdmin(ModelAdmin):
    list_display = ('member', 'functionary_role', 'year')
    list_filter = ('functionary_role', 'year')
    search_fields = ('member__first_name', 'member__last_name', 'member__username', 'member__email', 'functionary_role__title', 'year')
    autocomplete_fields = ('member', 'functionary_role')
    list_select_related = ('member', 'functionary_role')
    ordering = ['-year']


@admin.register(FunctionaryRole)
class FunctionaryRoleAdmin(ModelAdmin):
    list_display = ('title', 'board')
    list_filter = ('board',)
    search_fields = ('title',)
    ordering = ['title']
