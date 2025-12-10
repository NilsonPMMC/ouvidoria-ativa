# /var/www/ouvidoria/cidadao/views.py

from django.utils import timezone
from django.db.models import Count, Avg
from rest_framework import generics, status, viewsets, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Municipe, Atendimento, Pesquisa, Secretaria
from .filters import AtendimentoFilter
from .serializers import (
    AtendimentoCreateSerializer, AtendimentoListSerializer, AtendimentoDetailSerializer,
    PesquisaDetailSerializer, PesquisaApresentacaoSerializer, PesquisaRespostaSerializer,
    MunicipeSerializer, MunicipeDetailSerializer, SecretariaSerializer
)

class RegistrarAtendimentoAPIView(generics.CreateAPIView):
    """
    Endpoint para receber dados de um atendimento concluído via POST,
    criar os registros necessários e retornar os dados da pesquisa gerada.
    """    
    serializer_class = AtendimentoCreateSerializer
    authentication_classes = []
    permission_classes = []

    def create(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        pesquisa_criada = input_serializer.save()
        output_serializer = PesquisaDetailSerializer(pesquisa_criada)
        
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

class PesquisaAPIView(generics.RetrieveUpdateAPIView):
    """
    View para recuperar os dados de uma pesquisa (GET) e
    para atualizar com as respostas (PATCH).
    """
    queryset = Pesquisa.objects.filter(respondida=False)
    lookup_field = 'token'
    authentication_classes = []
    permission_classes = []
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PesquisaRespostaSerializer
        return PesquisaApresentacaoSerializer

    def update(self, request, *args, **kwargs):
        pesquisa = self.get_object()
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nota = serializer.validated_data.get('nota_geral')
        comentario = serializer.validated_data.get('comentario')

        pesquisa.nota_geral = nota
        pesquisa.comentario = comentario
        pesquisa.respondida = True
        pesquisa.data_resposta = timezone.now()
        pesquisa.save()

        return Response({"message": "Pesquisa respondida com sucesso!"}, status=status.HTTP_200_OK)

class DashboardStatsAPIView(APIView):
    """
    Endpoint que retorna dados agregados para o dashboard de resultados.
    """
    def get(self, request, *args, **kwargs):
        total_pesquisas = Pesquisa.objects.count()
        respondidas = Pesquisa.objects.filter(respondida=True)
        total_respondidas = respondidas.count()
        taxa_resposta = (total_respondidas / total_pesquisas * 100) if total_pesquisas > 0 else 0
        nota_media_geral = respondidas.aggregate(media=Avg('nota_geral'))['media'] or 0
        distribuicao_notas = respondidas.values('nota_geral').annotate(total=Count('nota_geral')).order_by('nota_geral')
        distribuicao_formatada = {f"{item['nota_geral']}_estrelas": item['total'] for item in distribuicao_notas if item['nota_geral']}
        satisfacao_por_secretaria = (
            Atendimento.objects.filter(pesquisa__respondida=True)
            .values('secretaria__nome')
            .annotate(nota_media=Avg('pesquisa__nota_geral'))
            .order_by('-nota_media')
        )
        data = {
            "total_pesquisas_enviadas": total_pesquisas,
            "total_pesquisas_respondidas": total_respondidas,
            "taxa_de_resposta_percentual": round(taxa_resposta, 2),
            "nota_media_geral": round(nota_media_geral, 2),
            "distribuicao_de_notas": distribuicao_formatada,
            "satisfacao_por_secretaria": list(satisfacao_por_secretaria)
        }
        
        return Response(data)

class MunicipeViewSet(viewsets.ModelViewSet):
    """
    ViewSet para CRUD completo de Munícipes com busca e paginação.
    """
    queryset = Municipe.objects.all().order_by('nome_completo')
    filter_backends = [filters.SearchFilter]
    search_fields = ['nome_completo', 'cpf', 'email']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MunicipeDetailSerializer
        return MunicipeSerializer

class AtendimentoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para CRUD completo de Atendimentos.
    """
    queryset = Atendimento.objects.select_related('municipe', 'secretaria', 'pesquisa').order_by('-data_conclusao')
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_class = AtendimentoFilter
    search_fields = ['protocolo', 'servico_realizado', 'municipe__nome_completo', 'secretaria__nome']

    def get_serializer_class(self):
        if self.action == 'list':
            return AtendimentoListSerializer
        return AtendimentoDetailSerializer

class SecretariaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Secretaria.objects.all()
    serializer_class = SecretariaSerializer
    pagination_class = None