import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import DocumentFilter, ExamFilter
from .forms import PictureUploadForm, ExamUploadForm, ExamArchiveUploadForm
from .models import Collection, Document, Picture
from .tasks import optimize_picture_image
from .tables import DocumentTable
from .uploads import create_presigned_temp_upload, head_temp_upload_object, uploads_use_s3
from core.utils import enqueue_task_on_commit

logger = logging.getLogger('date')
DIRECT_UPLOAD_RATE_LIMIT = 1000
DIRECT_UPLOAD_RATE_LIMIT_WINDOW_SECONDS = 3600
DEFAULT_UPLOAD_MAX_FILE_SIZE_MB = 25


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
    first_picture_qs = (
        Picture.objects.filter(
            collection=OuterRef('pk'),
            processing_status=Picture.PROCESSING_STATUS_READY,
        )
        .exclude(image='')
        .order_by('id')
    )
    picture_image_field = Picture._meta.get_field('image')
    collections = (
        Collection.objects
        .filter(type="Pictures", pub_date__year=year)
        .annotate(
            picture_count=Count(
                'picture',
                filter=Q(picture__processing_status=Picture.PROCESSING_STATUS_READY),
            ),
            first_picture_image=Subquery(first_picture_qs.values('image')[:1]),
        )
        .order_by('-pub_date')
    )
    collections = list(collections)
    for collection in collections:
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
    pictures_qs = (
        Picture.objects.filter(
            collection=collection,
            processing_status=Picture.PROCESSING_STATUS_READY,
        )
        .exclude(image='')
        .order_by('id')
    )

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


def _parse_json_request(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _get_picture_collection(collection_id):
    return get_object_or_404(Collection, pk=collection_id, type="Pictures")


def _check_upload_rate_limit(request, scope):
    cache_key = f"archive:upload-{scope}:{request.user.pk}"
    if not cache.add(cache_key, 1, DIRECT_UPLOAD_RATE_LIMIT_WINDOW_SECONDS):
        count = cache.incr(cache_key)
    else:
        count = 1
    return count <= DIRECT_UPLOAD_RATE_LIMIT


@permission_required('archive.add_collection')
def picture_upload(request, collection_id):
    collection = _get_picture_collection(collection_id)
    context = {
        "collection": collection,
        "direct_upload_enabled": uploads_use_s3(),
        "fallback_upload_enabled": True,
        "upload_max_file_size_mb": DEFAULT_UPLOAD_MAX_FILE_SIZE_MB,
    }
    return render(request, "archive/picture_upload.html", context)


@permission_required('archive.add_collection')
@require_POST
def picture_upload_direct(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    collection_id = payload.get("collection_id")
    if not collection_id:
        return JsonResponse({"error": "collection_id is required."}, status=400)

    collection = _get_picture_collection(collection_id)

    if not uploads_use_s3():
        return JsonResponse({"error": "Direct S3 uploads are not configured."}, status=503)

    if not _check_upload_rate_limit(request, "direct"):
        return JsonResponse({"error": "Too many upload URL requests. Please wait a moment."}, status=429)

    filename = (payload.get("filename") or "").strip()
    content_type = (payload.get("content_type") or "").strip()
    if not filename or not content_type.startswith("image/"):
        return JsonResponse({"error": "filename and image content_type are required."}, status=400)

    try:
        result = create_presigned_temp_upload(
            collection=collection,
            filename=filename,
            content_type=content_type,
            max_file_size=DEFAULT_UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024,
        )
    except Exception as exc:
        logger.warning("Unable to create archive upload session for collection %s: %s", collection_id, exc)
        return JsonResponse({"error": "Unable to create upload session."}, status=502)

    return JsonResponse(
        {
            "upload_url": result["upload_url"],
            "fields": result["fields"],
            "temp_key": result["temp_key"],
        }
    )


@permission_required('archive.add_collection')
@require_POST
def picture_upload_fallback(request):
    collection = _get_picture_collection(request.POST.get("collection_id"))

    if not _check_upload_rate_limit(request, "fallback"):
        return JsonResponse({"error": "Too many uploads. Please wait a moment."}, status=429)

    uploaded_file = request.FILES.get("file")
    if not isinstance(uploaded_file, UploadedFile):
        return JsonResponse({"error": "A file is required."}, status=400)

    if not uploaded_file.content_type or not uploaded_file.content_type.startswith("image/"):
        return JsonResponse({"error": "Only image uploads are supported."}, status=400)

    max_file_size = DEFAULT_UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_file_size:
        return JsonResponse({"error": f"Files must be {DEFAULT_UPLOAD_MAX_FILE_SIZE_MB} MB or smaller."}, status=400)

    picture = Picture(
        collection=collection,
        image=uploaded_file,
        original_filename=(uploaded_file.name or "")[:255],
        upload_provider=Picture.UPLOAD_PROVIDER_LOCAL,
        processing_status=Picture.PROCESSING_STATUS_PENDING,
    )
    picture._skip_compression = True
    picture.save()
    enqueue_task_on_commit(optimize_picture_image, picture.pk)
    return JsonResponse(
        {
            "picture_id": picture.pk,
            "status": picture.processing_status,
            "provider": picture.upload_provider,
        }
    )


@permission_required('archive.add_collection')
@require_POST
def picture_upload_complete(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    collection_id = payload.get("collection_id")
    temp_key = (payload.get("temp_key") or "").strip()
    filename = (payload.get("filename") or "").strip()

    if not collection_id or not temp_key:
        return JsonResponse({"error": "collection_id and temp_key are required."}, status=400)

    collection = _get_picture_collection(collection_id)

    existing_picture = Picture.objects.filter(temp_upload_key=temp_key).first()
    if existing_picture:
        return JsonResponse(
            {
                "picture_id": existing_picture.pk,
                "status": existing_picture.processing_status,
                "duplicate": True,
            }
        )

    try:
        head_temp_upload_object(temp_key)
    except Exception:
        return JsonResponse({"error": "Image upload has not completed yet."}, status=409)

    try:
        picture = Picture.objects.create(
            collection=collection,
            upload_provider=Picture.UPLOAD_PROVIDER_S3_DIRECT,
            original_filename=filename[:255],
            temp_upload_key=temp_key,
            processing_status=Picture.PROCESSING_STATUS_PENDING,
        )
    except IntegrityError:
        existing_picture = Picture.objects.filter(temp_upload_key=temp_key).first()
        if existing_picture:
            return JsonResponse(
                {
                    "picture_id": existing_picture.pk,
                    "status": existing_picture.processing_status,
                    "duplicate": True,
                }
            )
        raise
    enqueue_task_on_commit(optimize_picture_image, picture.pk)
    return JsonResponse(
        {
            "picture_id": picture.pk,
            "status": picture.processing_status,
            "duplicate": False,
        }
    )


@permission_required('archive.add_collection')
def upload(request):
    if request.method == 'POST':
        form = PictureUploadForm(request.POST)
        if form.is_valid():
            collection = Collection(title=form.cleaned_data['album'], type='Pictures')
            collection.save()
            messages.success(request, f'Album "{collection.title}" created. Continue in the bulk uploader.')
            return redirect('archive:picture_upload', collection_id=collection.pk)

    form = PictureUploadForm()
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
