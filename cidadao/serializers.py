# /var/www/ouvidoria/cidadao/serializers.py

from rest_framework import serializers
from .models import Municipe, Atendimento, Pesquisa, Secretaria, Categoria

class MunicipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipe
        fields = ['id', 'cpf', 'nome_completo', 'email', 'telefone', 'data_criacao']
        read_only_fields = ['data_criacao']
        
    def validate_cpf(self, value):
        """
        Verifica se o CPF contém apenas dígitos e tem 11 caracteres.
        """
        if not value.isdigit():
            raise serializers.ValidationError("O CPF deve conter apenas números.")
        if len(value) != 11:
            raise serializers.ValidationError("O CPF deve ter exatamente 11 dígitos.")
        return value

class SecretariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Secretaria
        fields = ['id', 'nome']

class PesquisaDetailSerializer(serializers.ModelSerializer):
    url_pesquisa = serializers.SerializerMethodField()

    class Meta:
        model = Pesquisa
        fields = ['token', 'url_pesquisa', 'data_envio', 'atendimento']
        depth = 1

    def get_url_pesquisa(self, obj):
        return f"https://ouvidoria.mogidascruzes.sp.gov.br/pesquisa/{obj.token}"

class AtendimentoCreateSerializer(serializers.Serializer):
    # Campos do Munícipe
    cpf = serializers.CharField(max_length=11)
    nome_completo = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    telefone = serializers.CharField(max_length=20, required=False, allow_blank=True) # <-- Já existia, agora vamos usar
    
    # Campos do Atendimento
    protocolo = serializers.CharField(max_length=50)
    data_conclusao = serializers.DateField()
    bairro = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # --- NOVOS CAMPOS ---
    distrito = serializers.CharField(max_length=100, required=False, allow_blank=True) # <-- Novo campo
    categoria_nome = serializers.CharField(max_length=255, write_only=True) # <-- Campo para receber o nome da categoria

    def create(self, validated_data):
        """
        Método customizado ATUALIZADO para a nova estrutura.
        """
        municipe_data = {
            'cpf': validated_data['cpf'],
            'nome_completo': validated_data['nome_completo'],
            'email': validated_data['email'],
            'telefone': validated_data.get('telefone'),
        }
        
        # --- LÓGICA DA CATEGORIA (NOVO) ---
        categoria_nome = validated_data.pop('categoria_nome', None)
        categoria_obj = None
        secretaria_obj = None
        
        if categoria_nome:
            try:
                # Encontra a categoria pelo nome
                categoria_obj = Categoria.objects.get(nome__iexact=categoria_nome.strip())
                # Puxa a secretaria automaticamente da categoria
                secretaria_obj = categoria_obj.secretaria
            except Categoria.DoesNotExist:
                # Se a categoria não for encontrada, não quebra a importação
                # Apenas deixa os campos nulos e salva o nome no campo antigo
                pass
        
        atendimento_data = {
            'protocolo': validated_data['protocolo'],
            'data_conclusao': validated_data['data_conclusao'],
            'bairro': validated_data.get('bairro'),
            'distrito': validated_data.get('distrito'), # <-- Novo campo
            'secretaria': secretaria_obj, # <-- Vinculado automaticamente
            'categoria': categoria_obj,   # <-- Vinculado automaticamente
            'servico_realizado': categoria_nome # <-- Salva o nome original no campo antigo
        }

        municipe, created = Municipe.objects.update_or_create(
            cpf=municipe_data['cpf'],
            defaults=municipe_data
        )

        novo_atendimento = Atendimento.objects.create(
            municipe=municipe, 
            **atendimento_data
        )

        nova_pesquisa = Pesquisa.objects.create(atendimento=novo_atendimento)

        return nova_pesquisa

class AtendimentoListSerializer(serializers.ModelSerializer):
    municipe = serializers.StringRelatedField()
    secretaria = serializers.StringRelatedField()
    municipe_id = serializers.IntegerField(source='municipe.id', read_only=True)
    secretaria_id = serializers.IntegerField(source='secretaria.id', read_only=True)

    # Nossos novos campos que serão preenchidos pelos métodos abaixo
    status_pesquisa = serializers.SerializerMethodField()
    pesquisa_detalhes = serializers.SerializerMethodField()

    class Meta:
        model = Atendimento
        # Adicionamos os novos campos e mantivemos os originais
        fields = [
            'id', 'protocolo', 'servico_realizado', 'data_conclusao',
            'municipe', 'secretaria', 'bairro', 'municipe_id', 'secretaria_id',
            'status_pesquisa', 'pesquisa_detalhes'
        ]

    def get_status_pesquisa(self, obj):
        """
        Calcula o status da pesquisa de forma segura.
        """
        try:
            if obj.pesquisa.respondida:
                return "Respondida"
            return "Enviada"
        except Pesquisa.DoesNotExist:
            return "Não enviada"

    def get_pesquisa_detalhes(self, obj):
        """
        Retorna os detalhes da pesquisa (nota e comentário) de forma segura,
        criando um dicionário diretamente, sem usar outro serializer.
        """
        try:
            pesquisa = obj.pesquisa
            return {
                'nota_geral': pesquisa.nota_geral,
                'comentario': pesquisa.comentario
            }
        except Pesquisa.DoesNotExist:
            # Se não houver pesquisa, retorna nulo
            return None

class AtendimentoDetailSerializer(serializers.ModelSerializer):
    """ Serializer para criar/editar um atendimento. """
    categoria = serializers.StringRelatedField()
    class Meta:
        model = Atendimento
        fields = ['protocolo', 'data_conclusao', 'bairro', 'categoria']

class PesquisaApresentacaoSerializer(serializers.ModelSerializer):
    """
    Serializer para apresentar os dados da pesquisa e do atendimento
    ao cidadão no frontend.
    """
    atendimento = AtendimentoDetailSerializer(read_only=True)

    class Meta:
        model = Pesquisa
        fields = ['token', 'respondida', 'atendimento']

class PesquisaRespostaSerializer(serializers.Serializer):
    """
    Serializer para validar os dados de entrada ao responder uma pesquisa.
    """
    nota_geral = serializers.IntegerField(min_value=1, max_value=5, required=True)
    comentario = serializers.CharField(required=False, allow_blank=True, style={'base_template': 'textarea.html'})

    class Meta:
        fields = ['nota_geral', 'comentario']

class AtendimentoDoCidadaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Atendimento
        fields = ['id', 'protocolo', 'servico_realizado', 'data_conclusao']

class MunicipeDetailSerializer(serializers.ModelSerializer):
    atendimentos = AtendimentoDoCidadaoSerializer(many=True, read_only=True, source='atendimento_set')
    
    class Meta:
        model = Municipe
        fields = ['id', 'cpf', 'nome_completo', 'email', 'telefone', 'atendimentos']