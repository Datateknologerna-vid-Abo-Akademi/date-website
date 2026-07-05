from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from core.admin_base import ExtraChangeListLinksMixin, ModelAdmin, TabularInline
from core.admin_ui import AdminLink

from .models import Functionary, FunctionaryRole


class FunctionaryInline(TabularInline):
    model = Functionary
    fk_name = 'functionary_role'
    extra = 1
    autocomplete_fields = ('member',)
    fields = ('member', 'name', 'year')
    ordering = ('-year', 'name')


@admin.register(Functionary)
class FunctionaryAdmin(ModelAdmin):
    list_display = ('get_display_name', 'functionary_role_link', 'year')
    list_filter = ('functionary_role', 'year')
    search_fields = (
        'member__first_name',
        'member__last_name',
        'member__username',
        'member__email',
        'name',
        'functionary_role__title',
        'year',
    )
    autocomplete_fields = ('member', 'functionary_role')
    list_select_related = ('member', 'functionary_role')
    ordering = ['-year']
    fields = ('member', 'name', 'functionary_role', 'year')

    @admin.display(description='Namn')
    def get_display_name(self, obj):
        return obj.get_full_name()

    @admin.display(description=_('Funktionärspost'))
    def functionary_role_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:functionaries_functionaryrole_change', args=[obj.functionary_role_id]),
            obj.functionary_role,
        )


@admin.register(FunctionaryRole)
class FunctionaryRoleAdmin(ExtraChangeListLinksMixin, ModelAdmin):
    changelist_links = (
        AdminLink(
            _('All assignments'),
            icon='manage_accounts',
            url_name='admin:functionaries_functionary_changelist',
            permission='functionaries.view_functionary',
        ),
    )
    save_on_top = True
    list_display = ('title', 'board', 'functionary_count')
    list_filter = ('board',)
    search_fields = ('title', 'functionary__name', 'functionary__member__first_name', 'functionary__member__last_name')
    ordering = ['title']
    inlines = [FunctionaryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(functionary_total=Count('functionary', distinct=True))

    @admin.display(description=_('Funktionärer'))
    def functionary_count(self, obj):
        count = getattr(obj, 'functionary_total', obj.functionary_set.count())
        if not count:
            return '0'
        return format_html(
            '<a href="{}?{}">{} {}</a>',
            reverse('admin:functionaries_functionary_changelist'),
            urlencode({'functionary_role__id__exact': obj.pk}),
            count,
            ngettext('functionary', 'functionaries', count),
        )
