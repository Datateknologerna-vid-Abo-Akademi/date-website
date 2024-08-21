from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from .models import PDFFile
from django.core.paginator import Paginator


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

    paginator = Paginator(pdfs, 10)  # Show 10 PDFs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }

    return render(request, 'publications/list.html', context)

