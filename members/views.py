from django.shortcuts import render
from django.views import View

# Create your views here.

class EditView(View):
    def get(self, request):
        user = request.user
        return render(request, 'userinfo.html', {"user":user})