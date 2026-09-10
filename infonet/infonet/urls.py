from django.urls import include, path

urlpatterns = [
    path('', include('myapp.urls')),
]

handler400 = 'myapp.security.bad_request'
handler403 = 'myapp.security.forbidden'
handler404 = 'myapp.security.not_found'
handler500 = 'myapp.security.server_error'
