from django.contrib import admin

from date_custom.models import MembershipSignupRequest
from members.models import Member, SUPPORTING_MEMBER, ORDINARY_MEMBER, MembershipType


@admin.register(MembershipSignupRequest)
class MembershipSignupRequestAdmin(admin.ModelAdmin):
    list_display = ["full_name", "membership_type",
                    "created_by__email", "created_at"]
    fields = [field.name for field in MembershipSignupRequest._meta.fields]
    actions = ["promote_member"]
    list_filter = [
        "created_at",
    ]

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description="Uppdatera medlemsstatus för de valda medlemsansökningarna")
    def promote_member(self, request, queryset):
        for req in queryset:
            member: Member = req.created_by
            member.is_active = True
            if req.membership_type == "supporting":
                member.membership_type = MembershipType.objects.get(
                    pk=SUPPORTING_MEMBER)
            else:
                member.membership_type = MembershipType.objects.get(
                    pk=ORDINARY_MEMBER)
            member.save()
