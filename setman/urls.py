from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.edit, name='setman_edit'),
    url(r'^revert/$', views.revert, name='setman_revert'),
]
