import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import permission_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, OuterRef, Subquery
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import redirect, render
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import DocumentFilter, ExamFilter
from .forms import PictureUploadForm, ExamUploadForm, ExamArchiveUploadForm
from .models import Collection, Document, Picture
from .tables import DocumentTable

logger = logging.getLogger('date')


def user_type(user):
    if not user.is_authenticated:
        return False
    return user.membership_type.permission_profile != 3


@user_passes_test(user_type, login_url='/members/login/')
def year_index(request):
    counts = (
        Collection.objects
        .filter(type='Pictures')
        .values('pub_date__year')
        .annotate(album_count=Count('id'))
        .order_by('-pub_date__year')
    )
    year_albumcount = {str(row['pub_date__year']): row['album_count'] for row in counts}

    context = {
        'type': "pictures",
        'year_albums': year_albumcount
    }
    return render(request, 'archive/index.html', context)


@user_passes_test(user_type, login_url='/members/login/')
def picture_index(request, year):
    first_picture_qs = Picture.objects.filter(collection=OuterRef('pk')).order_by('id')
    picture_image_field = Picture._meta.get_field('image')
    collections = (
        Collection.objects
        .filter(type="Pictures", pub_date__year=year)
        .annotate(
            picture_count=Count('picture'),
            first_picture_image=Subquery(first_picture_qs.values('image')[:1]),
        )
        .order_by('-pub_date')
    )
    collections = list(collections)
    for collection in collections:
        # Avoid instantiating a Picture for every album card; the ImageField
        # storage is enough to turn the annotated file name into a public URL.
        collection.first_picture_url = (
            picture_image_field.storage.url(collection.first_picture_image)
            if collection.first_picture_image
            else ''
        )
    context = {
        'type': "pictures",
        'year': year,
        'collections': collections,
    }
    return render(request, 'archive/picture_index.html', context)


@user_passes_test(user_type, login_url='/members/login/')
def exams_index(request):
    collections = Collection.objects.filter(type="Exams").order_by('title')
    context = {
        'type': "exams",
        'collections': collections,
    }
    return render(request, 'archive/exams_index.html', context)


@user_passes_test(user_type, login_url='/members/login/')
def exam_upload(request, pk):
    collection = Collection.objects.filter(pk=pk).first()
    if request.method == 'POST' and collection:
        form = ExamUploadForm(request.POST)
        if form.is_valid():
            if request.FILES.getlist('exams') is None:
                return redirect('archive:exams')
            for file in request.FILES.getlist('exam'):
                Document(document=file, title=form.cleaned_data['title'], collection=collection).save()
            logger.debug(f'User: {request.user} added files to {collection.title}')
        return redirect('archive:exams_detail', collection.pk)

    form = ExamUploadForm
    context = {
        'collection': collection,
        'exam_form': form,
    }
    return render(request, 'archive/exam_upload.html', context)


@user_passes_test(user_type, login_url='/members/login/')
def exam_archive_upload(request):
    if request.method == 'POST':
        form = ExamArchiveUploadForm(request.POST)
        if form.is_valid():
            Collection(title=form.cleaned_data['title'], type='Exams').save()
            logger.debug(f'User: {request.user} added exams-archive: {form.cleaned_data["title"]}')
        return redirect('archive:exams')

    form = ExamArchiveUploadForm
    context = {
        'exam_form': form,
    }
    return render(request, 'archive/exam_upload.html', context)


class FilteredDocumentsListView(UserPassesTestMixin, SingleTableMixin, FilterView):
    model = Document
    paginate_by = 15
    table_class = DocumentTable
    template_name = 'archive/document_index.html'
    filterset_class = DocumentFilter

    def get_table_data(self):
        filter_collection = self.request.GET.get('collection', '')
        filter_title_contains = self.request.GET.get('title__contains', '')

        if filter_collection or filter_title_contains:
            if filter_collection:
                return Document.objects.filter(
                    collection__type='Documents',
                    collection=filter_collection,
                    title__contains=filter_title_contains
                )
            else:
                return Document.objects.filter(
                    collection__type='Documents',
                    title__contains=filter_title_contains
                )
        else:
            return Document.objects.filter(collection__type='Documents')

    def test_func(self):
        # TODO: get a member object and check user.is_authenticated
        return self.request.user.membership_type.permission_profile != 3


class FilteredExamsListView(UserPassesTestMixin, SingleTableMixin, FilterView):
    model = Document
    paginate_by = 15
    table_class = DocumentTable
    template_name = 'archive/exam_detail.html'
    filterset_class = ExamFilter

    def get_table_data(self):
        collection_pk = self.kwargs.get('pk')
        if collection_pk:
            Collection.objects.filter(pk=collection_pk)
            return Document.objects.filter(collection=collection_pk)
        else:
            return Document.objects.all()

    def get_context_data(self, *args, **kwargs):
        context = super(FilteredExamsListView, self).get_context_data(*args, **kwargs)
        collection_pk = self.kwargs.get('pk')
        collection = Collection.objects.filter(pk=collection_pk).first()
        context['collection'] = collection
        return context

    def test_func(self):
        # TODO: get a member object and check user.is_authenticated
        return self.request.user.membership_type.permission_profile != 3


@user_passes_test(user_type, login_url='/members/login/')
def picture_detail(request, year, album):
    collection = Collection.objects.filter(type="Pictures", pub_date__year=year, title=album).order_by('-pub_date').first()
    if collection is None:
        raise Http404

    if collection.hide_for_gulis and request.user.membership_type.permission_profile == 1:
        return render(request, '404.html', {'error_msg': "Gulisar har inte tillgång till detta album!"})

    # Keep album images in upload order. The recent gallery refactor made the
    # non-2022 path explicitly descending, which flipped long-standing albums.
    pictures_qs = Picture.objects.filter(collection=collection).order_by('id')

    page = request.GET.get('page', 1)
    paginator = Paginator(pictures_qs, 12)
    try:
        pictures = paginator.page(page)
    except PageNotAnInteger:
        pictures = paginator.page(1)
    except EmptyPage:
        pictures = paginator.page(paginator.num_pages)

    if request.GET.get('fragment') == '1':
        html = render_to_string(
            'archive/partials/picture_items.html',
            {
                'pictures': pictures,
                'total_count': paginator.count,
            },
            request=request,
            using='django',
        )
        return JsonResponse({
            'html': html,
            'has_next': pictures.has_next(),
            'next_page': pictures.next_page_number() if pictures.has_next() else None,
            'page': pictures.number,
            'start_index': pictures.start_index(),
            'total_count': paginator.count,
        })

    context = {
        'type': "pictures",
        'year': year,
        'album': album,
        'collection': collection,
        'pictures': pictures,
        'total_count': paginator.count,
    }

    return render(request, 'archive/detail.html', context)


@permission_required('archive.add_collection')
def upload(request):
    if request.method == 'POST':
        form = PictureUploadForm(request.POST)
        if form.is_valid():
            if request.FILES.getlist('images') is None:
                return redirect('archive:pictures')
            collection = Collection(title=form['album'].value(), type='Pictures')
            collection.save()
            for file in request.FILES.getlist('images'):
                Picture(image=file, collection=collection).save()
        return redirect('archive:years')

    form = PictureUploadForm
    context = {
        'picture_form': form,
    }
    return render(request, 'archive/upload.html', context)


def clean_media(request):
    folders = os.walk(settings.MEDIA_ROOT)
    for f in folders:
        print(f[0])
        print(f[2])
        # If picture not in any collection, remove it.
    return redirect('archive:pictures')
