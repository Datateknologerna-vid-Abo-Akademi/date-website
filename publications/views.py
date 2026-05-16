from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from .models import PDFFile
from django.core.paginator import Paginator


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


def pdf_view(request, slug):
    pdf_file = get_object_or_404(PDFFile, slug=slug)

    # Check if the PDF is public and if login is required
    if not pdf_file.is_public:
        return HttpResponseForbidden("You do not have permission to access this PDF.")

    if pdf_file.requires_login and not request.user.is_authenticated:
        return redirect('login')

    context = {
        'pdf_url': pdf_file.get_file_url(),
        'pdf_file': pdf_file,
    }
    return render(request, 'publications/viewer.html', context)

def pdf_list(request):
    if request.user.is_authenticated:
        # For authenticated users, show public PDFs and those that require login, but hide non-public ones
        pdfs = PDFFile.objects.filter(is_public=True)
    else:
        # For non-authenticated users, only show public PDFs that don't require login
        pdfs = PDFFile.objects.filter(is_public=True, requires_login=False)

    pdfs = pdfs.order_by('-publication_date')

    paginator = Paginator(pdfs, 12)  # Show 12 PDFs per page (4×3 grid)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    for pdf in page_obj:
        pdf.thumbnail_url = pdf.get_safe_file_url()
    page_range = _compact_page_range(page_obj.number, paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'page_range': page_range,
    }

    return render(request, 'publications/list.html', context)
