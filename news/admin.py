from django.conf import settings
from django.contrib import admin
from django.db.models import TextField
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget

from core.admin import (
    ActiveLanguageTranslationAdminMixin,
    LanguageTabbedTranslationAdmin,
    TranslationCompletionAdminMixin,
)
from core.admin_base import UNFOLD_FORMFIELD_OVERRIDES, ModelAdmin, PublicUrlAdminMixin
from core.admin_widgets import FLATPICKR_ADMIN_CSS, FLATPICKR_ADMIN_JS
from news import forms
from news.models import Category, Post

if settings.ENABLE_LANGUAGE_FEATURES:  # type: ignore[misc]

    class NewsTranslationAdminBase(ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin, ModelAdmin):
        pass
else:
    NewsTranslationAdminBase = ModelAdmin  # type: ignore[misc, assignment]


class CategoryAdmin(PublicUrlAdminMixin, TranslationCompletionAdminMixin, NewsTranslationAdminBase):
    list_display = ('name', 'translation_status')
    search_fields = ('name', 'slug')
    ordering = ('name',)
    prepopulated_fields = {'slug': ('name',)}

    def get_prepopulated_fields(self, request, obj=None):
        # Only offer the slug suggestion on creation; an existing public URL
        # must not change just because the name was edited.
        if obj is None:
            return self.prepopulated_fields
        return {}


class PostPublicationFilter(admin.SimpleListFilter):
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


class PostAdmin(PublicUrlAdminMixin, TranslationCompletionAdminMixin, NewsTranslationAdminBase):
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {'widget': CKEditor5Widget},
    }

    fieldsets = [
        (None, {'fields': ['title', 'title_shine', 'category', 'content', 'published_time', 'slug']}),
    ]

    def get_fieldsets(self, request, obj=None):
        # The checkbox does nothing without the association's .title-shine styles.
        fieldsets = super().get_fieldsets(request, obj)
        if settings.TITLE_SHINE_ENABLED:
            return fieldsets
        return [
            (name, {**options, 'fields': [f for f in options['fields'] if f != 'title_shine']})
            for name, options in fieldsets
        ]

    prepopulated_fields = {'slug': ('title',)}

    def get_prepopulated_fields(self, request, obj=None):
        # Only suggest a slug while creating; editing the title of an existing
        # post must not change its already published URL.
        if obj is None:
            return self.prepopulated_fields
        return {}

    list_display = (
        'title',
        'translation_status',
        'author',
        'category',
        'created_time',
        'modified_time',
        'publication_status',
        'published_time',
    )  # noqa: E501
    search_fields = (
        'title',
        'slug',
        'category__name',
        'category__slug',
        'author__username',
        'author__first_name',
        'author__last_name',
        'author__email',
    )
    list_filter = (PostPublicationFilter, 'category')
    autocomplete_fields = ('author', 'category')
    list_select_related = ('author', 'category')
    ordering = ('-created_time',)
    date_hierarchy = 'created_time'
    show_full_result_count = False

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs['form'] = forms.PostCreationForm
        else:
            kwargs['form'] = forms.PostEditForm

        form = super().get_form(request, obj, change=change, **kwargs)
        form.user = request.user
        return form

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


admin.site.register(Category, CategoryAdmin)
admin.site.register(Post, PostAdmin)
