import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExpenseClaimForm
from .models import ExpenseClaim, ExpenseReceipt
from .tasks import generate_expense_pdf

logger = logging.getLogger('date')


@login_required
def expense_list(request):
    if request.user.is_staff:
        claims = ExpenseClaim.objects.select_related('submitted_by').all()
    else:
        claims = ExpenseClaim.objects.filter(submitted_by=request.user)
    return render(request, 'expenses/list.html', {'claims': claims})


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseClaimForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                claim = form.save(commit=False)
                claim.submitted_by = request.user
                claim.save()
                for f in form.cleaned_data['receipts']:
                    ExpenseReceipt.objects.create(claim=claim, file=f)
                transaction.on_commit(lambda: generate_expense_pdf.delay(claim.pk))
            return redirect('expenses:detail', pk=claim.pk)
    else:
        form = ExpenseClaimForm()
    return render(request, 'expenses/create.html', {'form': form})


@login_required
def expense_detail(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    if claim.submitted_by != request.user and not request.user.is_staff:
        raise Http404
    return render(request, 'expenses/detail.html', {'claim': claim})


@login_required
def receipt_file(request, pk):
    receipt = get_object_or_404(ExpenseReceipt, pk=pk)
    claim = receipt.claim
    if claim.submitted_by != request.user and not request.user.is_staff:
        raise Http404
    if getattr(settings, 'USE_S3', False):
        return redirect(receipt.file.url)
    try:
        name = receipt.file.name.lower()
        if name.endswith('.pdf'):
            content_type = 'application/pdf'
        elif name.endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif name.endswith('.png'):
            content_type = 'image/png'
        elif name.endswith('.gif'):
            content_type = 'image/gif'
        elif name.endswith('.webp'):
            content_type = 'image/webp'
        else:
            content_type = 'application/octet-stream'
        return FileResponse(receipt.file.open('rb'), content_type=content_type)
    except Exception:
        logger.exception('Could not retrieve receipt %s', pk)
        return HttpResponse('Could not retrieve receipt.', status=500)


@login_required
def download_pdf(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    if not claim.pdf:
        return HttpResponse('PDF not yet generated.', status=404)
    try:
        if getattr(settings, 'USE_S3', False):
            return redirect(claim.pdf.url)
        filename = claim.pdf.name.split('/')[-1]
        return FileResponse(claim.pdf.open('rb'), content_type='application/pdf', as_attachment=True, filename=filename)
    except Exception:
        logger.exception('Could not retrieve PDF for expense claim %s', pk)
        return HttpResponse('Could not retrieve PDF.', status=500)
