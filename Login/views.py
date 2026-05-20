from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required


def Login(request):
    return render(request, "login.html")

# Create your views here.
