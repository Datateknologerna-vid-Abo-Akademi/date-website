from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from botocore.exceptions import ClientError
from .models import PDFFile


@login_required
def pdf_view(request, pk):
    pdf_file = get_object_or_404(PDFFile, pk=pk)
    try:
        pdf_url = pdf_file.get_file_url()
    except ClientError as e:
        return JsonResponse({'error': str(e)}, status=404)

    context = {
        'pdf_url': pdf_url,
        'pdf_file': pdf_file,
    }
    return render(request, 'publications/viewer.html', context)
