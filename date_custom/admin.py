from django.contrib import admin

from date_custom.models import MembershipSignupRequest
from members.models import Member, SUPPORTING_MEMBER, ORDINARY_MEMBER, MembershipType


@admin.register(MembershipSignupRequest)
class MembershipSignupRequestAdmin(admin.ModelAdmin):
    list_display = ["full_name", "membership_type",
                    "created_by_email", "created_at"]
    readonly_fields = ["created_at", "created_by"]
    actions = ["promote_member"]
    list_filter = [
        "created_at",
    ]

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    @admin.display(description="E-post", ordering="created_by__email")
    def created_by_email(self, obj):
        return obj.created_by.email

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
