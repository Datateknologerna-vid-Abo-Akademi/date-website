from django.conf import settings
from django.contrib import admin
from django.db.models import TextField
from django.utils.timezone import now
from django_ckeditor_5.widgets import CKEditor5Widget
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, UNFOLD_FORMFIELD_OVERRIDES
from core.admin_widgets import FLATPICKR_ADMIN_CSS, FLATPICKR_ADMIN_JS

from core.admin import ActiveLanguageTranslationAdminMixin
from news import forms
from news.models import Post, Category

if settings.ENABLE_LANGUAGE_FEATURES:
    from modeltranslation.admin import TabbedTranslationAdmin

    # MRO when USE_UNFOLD=True: Mixin → TabbedTranslation → unfold.ModelAdmin → admin.ModelAdmin
    class NewsTranslationAdminBase(ActiveLanguageTranslationAdminMixin, TabbedTranslationAdmin, ModelAdmin):
        pass
else:
    NewsTranslationAdminBase = ModelAdmin


class CategoryAdmin(PublicUrlAdminMixin, NewsTranslationAdminBase):
    list_display = ('name',)
    search_fields = ('name', 'slug')
    ordering = ('name',)


class PostPublicationFilter(admin.SimpleListFilter):
    title = 'publicering'
    parameter_name = 'publication'

    def lookups(self, request, model_admin):
        return (
            ('published', 'Publicerad'),
            ('scheduled', 'Schemalagd'),
            ('hidden', 'Dold'),
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


class PostAdmin(PublicUrlAdminMixin, NewsTranslationAdminBase):
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {'widget': CKEditor5Widget},
    }

    fieldsets = [
        (None, {'fields': ['title', 'category', 'content', 'published_time', 'slug']}),
    ]
    list_display = ('title', 'author', 'category', 'created_time', 'modified_time', 'publication_status', 'published_time')
    search_fields = ('title', 'slug', 'category__name', 'category__slug', 'author__username', 'author__first_name', 'author__last_name', 'author__email')
    list_filter = (PostPublicationFilter, 'category')
    autocomplete_fields = ('author', 'category')
    list_select_related = ('author', 'category')
    ordering = ('-created_time',)
    date_hierarchy = 'created_time'

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs['form'] = forms.PostCreationForm
        else:
            kwargs['form'] = forms.PostEditForm

        form = super().get_form(request, obj, change=change, **kwargs)
        form.user = request.user
        return form

    def publication_status(self, obj):
        if obj.published_time is None:
            return 'Dold'
        if obj.published_time > now():
            return 'Schemalagd'
        return 'Publicerad'

    publication_status.short_description = 'Publicering'
    publication_status.admin_order_field = 'published_time'

    class Media:
        css = {'all': FLATPICKR_ADMIN_CSS}
        js = ('admin/js/jquery.init.js',) + FLATPICKR_ADMIN_JS


admin.site.register(Category, CategoryAdmin)
admin.site.register(Post, PostAdmin)
