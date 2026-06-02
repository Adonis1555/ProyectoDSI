from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from functools import wraps

def directora_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.es_directora():
            return view_func(request, *args, **kwargs)

        raise PermissionDenied
    return _wrapped_view

def maestro_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.es_maestro():
            return view_func(request, *args, **kwargs)

        raise PermissionDenied
    return _wrapped_view

def responsable_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.es_responsable():
            return view_func(request, *args, **kwargs)

        raise PermissionDenied
    return _wrapped_view

def roles_permitidos(roles_validos):
    """
    roles_validos puede ser una lista como ['directora', 'maestro']
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
                
            es_valido = False
            if 'directora' in roles_validos and request.user.es_directora(): es_valido = True
            if 'maestro' in roles_validos and request.user.es_maestro(): es_valido = True
            if 'responsable' in roles_validos and request.user.es_responsable(): es_valido = True
            
            if es_valido:
                return view_func(request, *args, **kwargs)
            
            raise PermissionDenied
        return _wrapped_view
    return decorator