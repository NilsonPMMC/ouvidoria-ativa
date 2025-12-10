# /var/www/ouvidoria/cidadao/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    RegistrarAtendimentoAPIView,
    PesquisaAPIView,
    DashboardStatsAPIView,
    MunicipeViewSet,
    AtendimentoViewSet,
    SecretariaViewSet
)

router = DefaultRouter()
router.register(r'cidadaos', MunicipeViewSet, basename='municipe')
router.register(r'atendimentos', AtendimentoViewSet, basename='atendimento')
router.register(r'secretarias', SecretariaViewSet, basename='secretaria')

urlpatterns = [
    path('atendimentos/registrar/', RegistrarAtendimentoAPIView.as_view(), name='api-registrar-atendimento'),
    path('pesquisa/<uuid:token>/', PesquisaAPIView.as_view(), name='api-pesquisa-detail'),
    path('dashboard/stats/', DashboardStatsAPIView.as_view(), name='api-dashboard-stats'),
    path('', include(router.urls)),
]