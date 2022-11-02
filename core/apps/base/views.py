from django.shortcuts import render
from django.http import HttpResponse

def home(request):
    '''Vista 1: Página inicial de la aplicación'''
    #return render(request, 'base/home.html')
    return HttpResponse('<h1>Vista 1: Página Inicial de la aplicación.</h2>')

def paso_a_paso(request):
    '''Vista 2: Página que indica los pasos'''
    return HttpResponse('<h2>Vista 2: paso a paso.</h2>')


def autorizacion_servicio(request):
    '''
    Vista 3:
    Página que recibe autorización de servicio y
    la verifica en 2 APIs externas.
    Si la respuesta es positiva, hará un redirect
    a la vista 4, sino  responderá con un mensaje de 
    error.
    '''
    return HttpResponse('<h2>Vista 3: Autorización de Servicio.</h2>')

def tomar_foto_formula_medica(request):
    '''
    Vista 4:
    '''
    return HttpResponse('<h1>Vista 4: Tomar foto de la formula médica.</h2>')
