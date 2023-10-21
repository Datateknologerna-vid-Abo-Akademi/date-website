from django.shortcuts import render, redirect
from .forms import HarassmentForm

# Create your views here.

def socialIndex(request):
    index = ""
    return render(request, 'social/socialIndex.html', {'index': index})


def harassment_form(request):
    form = HarassmentForm()

    if request.method == 'POST':
        form = HarassmentForm(request.POST)
        if form.is_valid():
            form.save()  # Save the form data to the Harassment model
            # Redirect to a success page or perform other actions
            return render(request, 'social/harassment_success.html', {'form': form})  # Redirect to a success page

    # If the form is not valid or it's a GET request, re-render the form with errors
    return render(request, 'social/harassment_form.html', {'form': form})
