import logging

from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, OuterRef, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .forms import AlbumUploadForm
from .models import Album, Photo

logger = logging.getLogger('date')


def user_type(user):
    if not user.is_authenticated:
        return False
    return user.membership_type.permission_profile != 3


@user_passes_test(user_type, login_url='/members/login/')
def year_index(request):
    counts = Album.objects.values('pub_date__year').annotate(album_count=Count('id')).order_by('-pub_date__year')
    year_albumcount = {str(row['pub_date__year']): row['album_count'] for row in counts}
    return render(
        request,
        'archive/index.html',
        {
            'type': "pictures",
            'year_albums': year_albumcount,
        },
    )


@user_passes_test(user_type, login_url='/members/login/')
def picture_index(request, year):
    first_photo_qs = Photo.objects.filter(album=OuterRef('pk')).order_by('id')
    image_field = Photo._meta.get_field('image')
    albums = (
        Album.objects.filter(pub_date__year=year)
        .annotate(
            picture_count=Count('photo'),
            first_picture_image=Subquery(first_photo_qs.values('image')[:1]),
        )
        .order_by('-pub_date')
    )
    albums = list(albums)
    for album in albums:
        album.album_thumbnail_url = (
            album.thumbnail.url
            if album.thumbnail
            else (image_field.storage.url(album.first_picture_image) if album.first_picture_image else '')
        )
    return render(
        request,
        'archive/picture_index.html',
        {
            'type': "pictures",
            'year': year,
            'collections': albums,
        },
    )


@user_passes_test(user_type, login_url='/members/login/')
def picture_detail(request, year, album):
    album_obj = Album.objects.filter(pub_date__year=year, title=album).order_by('-pub_date').first()
    if album_obj is None:
        raise Http404

    if album_obj.hide_for_gulis and request.user.membership_type.permission_profile == 1:
        return render(request, '404.html', {'error_msg': "Gulisar har inte tillgång till detta album!"})

    photos_qs = Photo.objects.filter(album=album_obj).order_by('id')
    page = request.GET.get('page', 1)
    paginator = Paginator(photos_qs, 12)
    try:
        photos = paginator.page(page)
    except PageNotAnInteger:
        photos = paginator.page(1)
    except EmptyPage:
        photos = paginator.page(paginator.num_pages)

    if request.GET.get('fragment') == '1':
        html = render_to_string(
            'archive/partials/picture_items.html',
            {
                'pictures': photos,
                'total_count': paginator.count,
            },
            request=request,
            using='django',
        )
        return JsonResponse(
            {
                'html': html,
                'has_next': photos.has_next(),
                'next_page': photos.next_page_number() if photos.has_next() else None,
                'page': photos.number,
                'start_index': photos.start_index(),
                'total_count': paginator.count,
            }
        )

    return render(
        request,
        'archive/detail.html',
        {
            'type': "pictures",
            'year': year,
            'album': album,
            'collection': album_obj,
            'pictures': photos,
            'total_count': paginator.count,
        },
    )


def can_upload_album(user):
    return user.has_perm('gallery.add_album') or user.has_perm('archive.add_collection')


@user_passes_test(can_upload_album)
def upload(request):
    if request.method == 'POST':
        form = AlbumUploadForm(request.POST)
        if form.is_valid():
            if not request.FILES.getlist('images'):
                return redirect('archive:years')
            album = Album.objects.create(title=form['album'].value())
            for uploaded_file in request.FILES.getlist('images'):
                Photo.objects.create(image=uploaded_file, album=album)
        return redirect('archive:years')

    return render(request, 'archive/upload.html', {'picture_form': AlbumUploadForm})
