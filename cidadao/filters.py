# /var/www/ouvidoria/cidadao/filters.py

from django_filters import rest_framework as filters
from .models import Atendimento

class AtendimentoFilter(filters.FilterSet):
    STATUS_CHOICES = (
        ('Respondida', 'Respondida'),
        ('Enviada', 'Enviada'),
        ('Não enviada', 'Não enviada'),
    )

    status_pesquisa = filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method='filter_by_status',
        label='Status da Pesquisa'
    )

    class Meta:
        model = Atendimento
        fields = ['secretaria']

    def filter_by_status(self, queryset, name, value):
        if value == 'Respondida':
            return queryset.filter(pesquisa__respondida=True)
        if value == 'Enviada':
            return queryset.filter(pesquisa__isnull=False, pesquisa__respondida=False)
        if value == 'Não enviada':
            return queryset.filter(pesquisa__isnull=True)
        return queryset