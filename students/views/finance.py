"""Fee structure and fee payments."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..audit import log_action
from ..forms import (
    FeePaymentForm,
    FeeStructureForm,
)
from ..models import (
    FeePayment,
    FeeStructure,
)
from ..pagination import paginate
from .common import admin_required


@admin_required
def fee_structure_list(request):
    structures = FeeStructure.objects.all().order_by('branch', 'semester', 'fee_type')
    return render(request, 'admin_dashboard/fees.html', {'structures': paginate(request, structures)})


@admin_required
def fee_structure_create(request):
    form = FeeStructureForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Fee structure created.")
        return redirect('fee_structure_list')
    return render(request, 'admin_dashboard/fee_form.html', {'form': form, 'action': 'Create'})


@admin_required
def fee_structure_edit(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    form = FeeStructureForm(request.POST or None, instance=structure)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Fee structure updated.")
        return redirect('fee_structure_list')
    return render(request, 'admin_dashboard/fee_form.html', {'form': form, 'action': 'Edit', 'structure': structure})


@admin_required
def fee_structure_delete(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    if request.method == 'POST':
        structure.delete()
        messages.success(request, "Fee structure deleted.")
        return redirect('fee_structure_list')
    return render(request, 'admin_dashboard/fee_delete_confirm.html', {'structure': structure})


@admin_required
def fee_payments(request):
    payments = FeePayment.objects.select_related('student', 'fee_structure').all()
    q = request.GET.get('q', '')
    if q:
        payments = payments.filter(
            Q(student__name__icontains=q) |
            Q(student__registration_number__icontains=q) |
            Q(receipt_number__icontains=q)
        )
    paginator = Paginator(payments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/fee_payments.html', {'page_obj': page_obj, 'q': q})


@admin_required
def fee_payment_create(request):
    form = FeePaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.recorded_by = request.user.get_full_name() or request.user.username
        payment.save()
        log_action(request, "fee.payment.create", payment,
                   detail=f"{payment.student.registration_number} amount={payment.amount_paid} receipt={payment.receipt_number}")
        messages.success(request, f"Payment recorded: Receipt #{payment.receipt_number}")
        return redirect('fee_payments')
    return render(request, 'admin_dashboard/fee_payment_form.html', {'form': form})

