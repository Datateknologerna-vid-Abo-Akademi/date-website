from django.contrib.auth import login, authenticate
from django.shortcuts import render, redirect

from members.forms import SignUpForm


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

class EditView(View):
    def get(self, request):
        user = request.user
        return render(request, 'userinfo.html', {"user":user})