from django.shortcuts import render, redirect
from .forms import HarassmentForm

# Create your views here.

def socialIndex(request):
    index = ""
    return render(request, 'social/socialIndex.html', {'index': index})


def harassment_form(request):
    form = HarassmentForm()
    # If user has submitted the form show success page
    if request.session.get("harass_submitted", False):
        request.session['harass_submitted'] = False
        return render(request, 'social/harassment_success.html')

    if request.method == 'POST':
        form = HarassmentForm(request.POST)
        if form.is_valid():
            form.save()  # Save the form data to the Harassment model
            request.session['harass_submitted'] = True
            # Redirect to a success page or perform other actions
            return redirect(request.path)  # Redirect to a success page

    # If the form is not valid or it's a GET request, re-render the form with errors
    return render(request, 'social/harassment_form.html', {'form': form})
