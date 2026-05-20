from django.contrib import admin
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from core.admin_base import ModelAdmin, PublicUrlAdminMixin, StackedInline
from core.admin_widgets import (
    FLATPICKR_ADMIN_CSS,
    FLATPICKR_ADMIN_JS,
    FlatpickrDateTimeAdminMixin,
)

from .models import Ctf, Flag, Guess


class FlagInline(StackedInline):
    model = Flag
    can_delete = True
    extra = 0
    exclude = ('solved_date',)
    autocomplete_fields = ('solver',)


class CtfPublicationFilter(admin.SimpleListFilter):
    title = _('publicering')
    parameter_name = 'publication'

    def lookups(self, request, model_admin):
        return (
            ('published', _('Publicerad')),
            ('scheduled', _('Schemalagd')),
            ('hidden', _('Dold')),
        )

    def queryset(self, request, queryset):
        current_time = now()
        if self.value() == 'published':
            return queryset.filter(published_time__isnull=False, published_time__lte=current_time)
        if self.value() == 'scheduled':
            return queryset.filter(published_time__gt=current_time)
        if self.value() == 'hidden':
            return queryset.filter(published_time__isnull=True)
        return queryset


@admin.register(Ctf)
class CtfAdmin(FlatpickrDateTimeAdminMixin, PublicUrlAdminMixin, ModelAdmin):
    model = Ctf
    save_on_top = True
    list_display = ('title', 'start_date', 'end_date', 'publication_status', 'published_time')
    list_filter = (CtfPublicationFilter,)
    search_fields = ('title', 'slug')
    ordering = ('-start_date',)
    date_hierarchy = 'start_date'
    inlines = [
        FlagInline,
    ]
    flatpickr_datetime_fields = ('published_time', 'start_date', 'end_date')  # type: ignore[assignment]

    @admin.display(description=_("Publicering"), ordering="published_time")
    def publication_status(self, obj):
        if obj.published_time is None:
            return _('Dold')
        if obj.published_time > now():
            return _('Schemalagd')
        return _('Publicerad')

    class Media:
        css = {'all': FLATPICKR_ADMIN_CSS}
        js = ('admin/js/jquery.init.js',) + FLATPICKR_ADMIN_JS


@admin.register(Flag)
class FlagAdmin(PublicUrlAdminMixin, ModelAdmin):
    list_display = ('title', 'ctf', 'solver', 'solved_date')
    list_filter = ('ctf',)
    search_fields = ('title', 'slug', 'flag', 'ctf__title', 'ctf__slug', 'solver__username', 'solver__email')
    autocomplete_fields = ('ctf', 'solver')
    list_select_related = ('ctf', 'solver')
    ordering = ('ctf', 'title')


@admin.register(Guess)
class GuessAdmin(ModelAdmin):
    list_display = ('ctf', 'flag', 'user', 'guess', 'timestamp', 'correct')
    list_filter = ('ctf', 'flag', 'correct')
    search_fields = ('ctf__title', 'ctf__slug', 'flag__title', 'flag__slug', 'user__username', 'user__email', 'guess')
    autocomplete_fields = ('ctf', 'flag', 'user')
    list_select_related = ('ctf', 'flag', 'user')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
