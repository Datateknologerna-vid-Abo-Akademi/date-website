from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from .models import PDFFile, PublicationCollection


def _compact_page_range(current, total, window=1, edges=1):
    """Build a pagination range with ellipsis gaps.

    Returns a list of page numbers; ``None`` marks an ellipsis. For small
    totals every page is shown; otherwise the first/last ``edges`` pages and
    ``window`` neighbours on each side of ``current`` are kept.
    """
    if total <= (edges * 2) + (window * 2) + 3:
        return list(range(1, total + 1))

    pages = set()
    for i in range(1, edges + 1):
        pages.add(i)
        pages.add(total - i + 1)
    for p in range(current - window, current + window + 1):
        if 1 <= p <= total:
            pages.add(p)

    result = []
    prev = 0
    for p in sorted(pages):
        if prev and p - prev > 1:
            result.append(None)
        result.append(p)
        prev = p
    return result


def _collection_session_key(collection):
    return f"publication_collection_access_{collection.pk}"


def _collection_session_token(collection):
    # Store a hash-derived token so admin password rotation invalidates
    # existing grants. The token is opaque (a prefix of the bcrypt-style
    # hash) and not useful for verifying the password.
    return collection.password_hash[:32]


def _collection_is_visible(collection, user):
    if not collection.is_active or collection.visibility == PublicationCollection.VISIBILITY_HIDDEN:
        return False
    if collection.visibility == PublicationCollection.VISIBILITY_PUBLIC:
        return True
    if collection.visibility == PublicationCollection.VISIBILITY_PASSWORD:
        return True
    if not user.is_authenticated:
        return False
    if collection.visibility == PublicationCollection.VISIBILITY_LOGIN:
        return True
    if collection.visibility == PublicationCollection.VISIBILITY_MEMBERSHIP:
        # Iterate the prefetched list rather than re-querying.
        return any(mt.pk == user.membership_type_id for mt in collection.allowed_membership_types.all())
    return False


def _collection_access_response(request, collection):
    if not collection.is_active or collection.visibility == PublicationCollection.VISIBILITY_HIDDEN:
        raise Http404

    if collection.visibility == PublicationCollection.VISIBILITY_PUBLIC:
        return None

    if collection.visibility == PublicationCollection.VISIBILITY_LOGIN:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)
        return None

    if collection.visibility == PublicationCollection.VISIBILITY_MEMBERSHIP:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)
        if collection.allowed_membership_types.filter(pk=request.user.membership_type_id).exists():
            return None
        raise Http404

    if collection.visibility == PublicationCollection.VISIBILITY_PASSWORD:
        session_key = _collection_session_key(collection)
        expected_token = _collection_session_token(collection)
        if expected_token and request.session.get(session_key) == expected_token:
            return None
        error = ''
        if request.method == 'POST':
            if collection.check_password(request.POST.get('password', '')):
                request.session[session_key] = _collection_session_token(collection)
                # Re-issue the current request as a GET. request.get_full_path()
                # is always a local Django-matched path, but gating it through
                # the sanitiser keeps the open-redirect guarantee provable to
                # CodeQL. Fall back to a literal route reverse so the failure
                # branch carries no taint either.
                next_url = request.get_full_path()
                if url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts=None,
                    require_https=False,
                ):
                    return redirect(next_url)
                return redirect('publications:pdf_list')
            error = _('Fel lösenord.')
        return render(
            request,
            'publications/password.html',
            {
                'collection': collection,
                'error': error,
            },
        )

    raise Http404


def _check_pdf_access(request, pdf_file):
    if not pdf_file.is_public:
        return HttpResponseForbidden("You do not have permission to access this PDF.")

    if pdf_file.requires_login and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)

    return None


def _prepare_publication_cards(page_obj):
    for pdf in page_obj:
        pdf.cover_url = pdf.get_safe_cover_url()
        pdf.thumbnail_url = '' if pdf.cover_url else pdf.get_safe_file_url()


def pdf_view(request, collection_slug, slug):
    collection = get_object_or_404(PublicationCollection, slug=collection_slug)
    access_response = _collection_access_response(request, collection)
    if access_response is not None:
        return access_response

    pdf_file = get_object_or_404(PDFFile, collection=collection, slug=slug)
    access_response = _check_pdf_access(request, pdf_file)
    if access_response is not None:
        return access_response

    if pdf_file.redirect_url:
        return redirect(pdf_file.redirect_url)

    context = {
        'pdf_url': pdf_file.get_file_url(),
        'pdf_file': pdf_file,
    }
    return render(request, 'publications/viewer.html', context)


def legacy_pdf_view(request, slug):
    pdf_file = get_object_or_404(PDFFile, slug=slug)
    if pdf_file.collection_id:
        access_response = _collection_access_response(request, pdf_file.collection)
        if access_response is not None:
            return access_response

    access_response = _check_pdf_access(request, pdf_file)
    if access_response is not None:
        return access_response

    if pdf_file.collection_id:
        return redirect(pdf_file.get_absolute_url(), permanent=True)

    if pdf_file.redirect_url:
        return redirect(pdf_file.redirect_url)

    context = {
        'pdf_url': pdf_file.get_file_url(),
        'pdf_file': pdf_file,
    }
    return render(request, 'publications/viewer.html', context)


def pdf_list(request):
    publications_filter = {'collection': OuterRef('pk'), 'is_public': True}
    if not request.user.is_authenticated:
        publications_filter['requires_login'] = False
    collections = [
        collection
        for collection in (
            PublicationCollection.objects.annotate(
                _has_visible_publication=Exists(PDFFile.objects.filter(**publications_filter))
            )
            .filter(_has_visible_publication=True)
            .prefetch_related('allowed_membership_types')
        )
        if _collection_is_visible(collection, request.user)
    ]
    if len(collections) == 1:
        return redirect('publications:collection_detail', collection_slug=collections[0].slug)
    for collection in collections:
        collection.cover_url = collection.get_safe_cover_url()
    return render(request, 'publications/index.html', {'collections': collections})


def collection_detail(request, collection_slug):
    collection = PublicationCollection.objects.filter(slug=collection_slug).first()
    if collection is None:
        return legacy_pdf_view(request, collection_slug)

    access_response = _collection_access_response(request, collection)
    if access_response is not None:
        return access_response

    pdfs = collection.publications.filter(is_public=True)
    if not request.user.is_authenticated:
        pdfs = pdfs.filter(requires_login=False)

    pdfs = pdfs.order_by('-publication_date')

    paginator = Paginator(pdfs, 12)  # Show 12 PDFs per page (4×3 grid)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    _prepare_publication_cards(page_obj)
    page_range = _compact_page_range(page_obj.number, paginator.num_pages)

    context = {
        'collection': collection,
        'page_obj': page_obj,
        'page_range': page_range,
    }

    return render(request, 'publications/list.html', context)
