from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from .models import PDFFile
from django.core.paginator import Paginator

@login_required
def pdf_view(request, slug):
    pdf_file = get_object_or_404(PDFFile, slug=slug)
    context = {
        'pdf_url': pdf_file.get_file_url(),
        'pdf_file': pdf_file,
    }
    return render(request, 'publications/viewer.html', context)

@login_required
def pdf_list(request):
    pdfs = PDFFile.objects.all()
    paginator = Paginator(pdfs, 10)  # Show 10 PDFs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'publications/list.html', {'page_obj': page_obj})
