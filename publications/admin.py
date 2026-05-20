import logging

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from core.admin_base import (
    UNFOLD_FORMFIELD_OVERRIDES,
    ExtraChangeListLinksMixin,
    ModelAdmin,
    PublicUrlAdminMixin,
    TabularInline,
)
from core.admin_ui import AdminLink
from core.admin_widgets import SafeAdminFileWidget

from .models import PDFFile, PublicationCollection

logger = logging.getLogger('date')


class PublicationCollectionAdminForm(forms.ModelForm):
    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Set or replace the access password. Leave blank to keep the current password.',
    )
    clear_password = forms.BooleanField(
        label='Clear password',
        required=False,
        help_text='Remove the current password.',
    )

    class Meta:
        model = PublicationCollection
        fields = '__all__'  # noqa: DJ007

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('clear_password') and cleaned_data.get('password'):
            raise forms.ValidationError('Choose either a new password or clear the current password, not both.')
        visibility = cleaned_data.get('visibility')
        if visibility == PublicationCollection.VISIBILITY_PASSWORD:
            has_existing_password = self.instance.pk and self.instance.has_password()
            if cleaned_data.get('clear_password'):
                self.add_error('clear_password', 'Password-protected collections must keep or set a password.')
            elif not cleaned_data.get('password') and not has_existing_password:
                self.add_error('password', 'Set a password before saving a password-protected collection.')
        if visibility == PublicationCollection.VISIBILITY_MEMBERSHIP and not cleaned_data.get(
            'allowed_membership_types'
        ):
            self.add_error(
                'allowed_membership_types',
                'Choose at least one membership type for selected-membership access.',
            )
        return cleaned_data

    def save(self, commit=True):
        collection = super().save(commit=False)
        if self.cleaned_data.get('clear_password'):
            collection.set_password('')
        elif self.cleaned_data.get('password'):
            collection.set_password(self.cleaned_data['password'])
        if commit:
            collection.save()
            self.save_m2m()
        return collection


@admin.register(PublicationCollection)
class PublicationCollectionAdmin(PublicUrlAdminMixin, ModelAdmin):
    form = PublicationCollectionAdminForm
    save_on_top = True
    list_display = (
        'title',
        'access_summary',
        'ordering',
        'is_active',
        'publication_count',
        'manage_publications',
        'updated_at',
    )
    list_editable = ('ordering', 'is_active')
    list_filter = ('visibility', 'is_active')
    search_fields = ('title', 'slug', 'description', 'publications__title', 'publications__slug')
    ordering = ('ordering', 'title')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('allowed_membership_types',)
    readonly_fields = ('created_at', 'updated_at', 'has_password', 'publications_changelist_link')
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'slug',
                    'description',
                    'cover_image',
                    'ordering',
                    'is_active',
                    'publications_changelist_link',
                ),
            },
        ),
        (
            'Access Control',
            {
                'fields': ('visibility', 'allowed_membership_types', 'password', 'clear_password', 'has_password'),
                'description': 'Controls whether this collection is listed and who can open its publications.',
            },
        ),
        (
            'Timestamps',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )
    inlines: list[type[TabularInline]] = []

    def get_prepopulated_fields(self, request, obj=None):
        if obj is None:
            return self.prepopulated_fields
        return {}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related('allowed_membership_types')
            .annotate(publication_total=Count('publications', distinct=True))
        )

    def get_inlines(self, request, obj):
        if obj is None:
            return []
        return [PublicationInline]

    @admin.display(description='Access')
    def access_summary(self, obj):
        label = obj.get_visibility_display()
        details = []
        if obj.visibility == PublicationCollection.VISIBILITY_MEMBERSHIP:
            details = [membership.name for membership in obj.allowed_membership_types.all()]
        elif obj.visibility == PublicationCollection.VISIBILITY_PASSWORD:
            details = ['password set' if obj.has_password() else 'missing password']
        if not obj.is_active:
            details.append('inactive')
        if details:
            label = f"{label} ({', '.join(details)})"
        return label

    @admin.display(boolean=True, description='Has password')
    def has_password(self, obj):
        return bool(obj and obj.has_password())

    @admin.display(description='Publications')
    def publication_count(self, obj):
        count = getattr(obj, 'publication_total', obj.publications.count())
        if not count:
            return '0'
        return format_html(
            '<a href="{}?{}">{} {}</a>',
            reverse('admin:publications_pdffile_changelist'),
            urlencode({'collection__id__exact': obj.pk}),
            count,
            ngettext('publication', 'publications', count),
        )

    @admin.display(description='Manage')
    def manage_publications(self, obj):
        return format_html(
            '<a href="{}?{}">{}</a>',
            reverse('admin:publications_pdffile_changelist'),
            urlencode({'collection__id__exact': obj.pk}),
            _('Open list'),
        )

    @admin.display(description='Publication list')
    def publications_changelist_link(self, obj):
        if not obj or not obj.pk:
            return '-'
        return self.manage_publications(obj)


class PublicationInline(TabularInline):
    model = PDFFile
    fk_name = 'collection'
    extra = 1
    show_change_link = True
    fields = (
        'title',
        'publication_date',
        'file',
        'redirect_url',
        'is_public',
        'requires_login',
        'public_page',
    )
    readonly_fields = ('public_page',)
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        models.FileField: {'widget': SafeAdminFileWidget},
        models.ImageField: {'widget': SafeAdminFileWidget},
    }

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        base_form = formset.form

        class ExistingFileReadonlyForm(base_form):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, **form_kwargs)
                if self.instance.pk and 'file' in self.fields:
                    self.fields['file'].disabled = True
                    self.fields['file'].help_text = _(
                        'Open the publication change page to inspect the existing upload.'
                    )

        formset.form = ExistingFileReadonlyForm
        return formset

    @admin.display(description='Public page')
    def public_page(self, obj):
        if not obj or not obj.pk:
            return '-'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            obj.get_absolute_url(),
            _('Open'),
        )


class PublicationAdminMixin(ExtraChangeListLinksMixin):
    changelist_links = (
        AdminLink(
            _('Manage collections and access'),
            icon='collections_bookmark',
            url_name='admin:publications_publicationcollection_changelist',
            permission='publications.view_publicationcollection',
        ),
    )


def collection_access_payload(collection):
    memberships = []
    if collection.visibility == PublicationCollection.VISIBILITY_MEMBERSHIP:
        memberships = [membership.name for membership in collection.allowed_membership_types.all()]
    return {
        'title': collection.title,
        'visibility': collection.visibility,
        'access': collection.get_visibility_display(),
        'active': collection.is_active,
        'has_password': collection.has_password(),
        'memberships': memberships,
        'edit_url': reverse('admin:publications_publicationcollection_change', args=[collection.pk]),
    }


@admin.register(PDFFile)
class PDFFileAdmin(PublicUrlAdminMixin, PublicationAdminMixin, ModelAdmin):
    list_display = (
        'title',
        'collection_link',
        'collection_access',
        'publication_date',
        'is_external_link',
        'is_public',
        'requires_login',
        'uploaded_at',
        'updated_at',
    )
    list_filter = (
        'collection__visibility',
        'collection',
        'is_public',
        'requires_login',
        'uploaded_at',
        'updated_at',
        'publication_date',
    )
    search_fields = ('title', 'slug', 'description', 'file', 'redirect_url', 'collection__title')
    ordering = ('-uploaded_at',)
    date_hierarchy = 'publication_date'
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('collection_access_details', 'uploaded_at', 'updated_at')
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'collection',
                    'title',
                    'slug',
                    'publication_date',
                    'description',
                    'file',
                    'redirect_url',
                    'cover_image',
                ),
            },
        ),
        (
            'Access Control',
            {
                'fields': ('collection_access_details', 'is_public', 'requires_login'),
                'description': 'Collection access is the primary rule. Publication access is checked after it.',
            },
        ),
        ('Timestamps', {'fields': ('uploaded_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'collection-access/<int:collection_id>/',
                self.admin_site.admin_view(self.collection_access_view),
                name='publications_pdffile_collection_access',
            ),
        ]
        return custom_urls + urls

    def get_prepopulated_fields(self, request, obj=None):
        # Only prepopulate slug for new objects
        if obj is None:
            return self.prepopulated_fields
        return {}

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('collection')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.append('file_link')
        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj:
            return fieldsets

        updated_fieldsets = []
        for name, options in fieldsets:
            fields = tuple('file_link' if field == 'file' else field for field in options.get('fields', ()))
            updated_fieldsets.append((name, {**options, 'fields': fields}))
        return updated_fieldsets

    @admin.display(description="File")
    def file_link(self, obj):
        if not obj or not obj.file:
            return '-'
        try:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
                obj.file.url,
                obj.file.name,
            )
        except Exception as exc:
            logger.warning("Unable to resolve PDF file URL for %s: %s", obj.pk, exc)
            return obj.file.name

    @admin.display(description='Selected collection access')
    def collection_access_details(self, obj):
        collection = obj.collection if obj and obj.collection_id else None
        data_url = reverse('admin:publications_pdffile_collection_access', args=[0])
        if not collection:
            return format_html(
                '<div id="publication-collection-access-summary" data-url-template="{}">'
                'Choose a collection to show its current access settings here.'
                '</div>',
                data_url,
            )

        details = collection_access_payload(collection)
        extra = []
        if details['memberships']:
            extra.append(_('Memberships: %(memberships)s') % {'memberships': ', '.join(details['memberships'])})
        if collection.visibility == PublicationCollection.VISIBILITY_PASSWORD:
            extra.append(_('Password configured') if details['has_password'] else _('Password missing'))
        if not details['active']:
            extra.append(_('Inactive'))
        suffix = f" ({'; '.join(str(item) for item in extra)})" if extra else ''
        return format_html(
            '<div id="publication-collection-access-summary" data-url-template="{}">'
            '<strong>{}</strong>: {}{} &nbsp; <a href="{}">{}</a>'
            '</div>',
            data_url,
            details['title'],
            details['access'],
            suffix,
            details['edit_url'],
            _('Edit collection access'),
        )

    def collection_access_view(self, request, collection_id):
        collection_admin = self.admin_site._registry[PublicationCollection]
        if not (
            self.has_view_permission(request)
            or self.has_change_permission(request)
            or collection_admin.has_view_permission(request)
            or collection_admin.has_change_permission(request)
        ):
            raise PermissionDenied
        collection = get_object_or_404(
            PublicationCollection.objects.prefetch_related('allowed_membership_types'),
            pk=collection_id,
        )
        return JsonResponse(collection_access_payload(collection))

    @admin.display(boolean=True, description='External link')
    def is_external_link(self, obj):
        return bool(obj.redirect_url)

    @admin.display(description='Collection')
    def collection_link(self, obj):
        if not obj.collection_id:
            return '-'
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:publications_publicationcollection_change', args=[obj.collection_id]),
            obj.collection,
        )

    @admin.display(description='Collection access')
    def collection_access(self, obj):
        if not obj.collection_id:
            return '-'
        return obj.collection.get_visibility_display()

    class Media:
        js = ('common/publications/js/admin-collection-access.js',)
