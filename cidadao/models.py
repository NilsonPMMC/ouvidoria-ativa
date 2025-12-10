# /var/www/ouvidoria/cidadao/models.py

from django.db import models
import uuid

class Entidade(models.Model):
    """
    Novo modelo: O nível mais alto da hierarquia (ex: Prefeitura, Câmara, etc.)
    """
    nome = models.CharField(max_length=200, unique=True, verbose_name="Nome da Entidade")
    
    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Entidade"
        verbose_name_plural = "Entidades"
        ordering = ['nome']

class Secretaria(models.Model):
    entidade = models.ForeignKey(
        Entidade, 
        on_delete=models.PROTECT, 
        verbose_name="Entidade",
        null=True,
        blank=True
    )
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome da Secretaria")
    sigla = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Sigla")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Secretaria"
        verbose_name_plural = "Secretarias"
        ordering = ['nome']

class UnidadeAdm(models.Model):
    """
    Novo modelo: A unidade administrativa (divisão/departamento) dentro de uma Secretaria.
    """
    secretaria = models.ForeignKey(Secretaria, on_delete=models.CASCADE, verbose_name="Secretaria")
    nome = models.CharField(max_length=255, verbose_name="Nome da Unidade Administrativa")

    def __str__(self):
        return f"{self.nome} ({self.secretaria.sigla or self.secretaria.nome})"

    class Meta:
        verbose_name = "Unidade Administrativa"
        verbose_name_plural = "Unidades Administrativas"
        ordering = ['secretaria', 'nome']
        unique_together = ('secretaria', 'nome')

class Categoria(models.Model):
    """
    Novo modelo: A categoria ou serviço específico.
    """
    TIPO_CHOICES = [
        ('Serviço', 'Serviço'),
        ('Ouvidoria', 'Ouvidoria'),
    ]
    secretaria = models.ForeignKey(Secretaria, on_delete=models.CASCADE, verbose_name="Secretaria Responsável")
    unidade_adm = models.ForeignKey(
        UnidadeAdm, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Unidade Adm. (Opcional)"
    )
    nome = models.CharField(max_length=255, verbose_name="Nome da Categoria/Serviço")
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES, 
        default='Serviço', 
        verbose_name="Tipo"
    )
    prazo = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name="Prazo (em dias)"
    )
    
    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Categoria (Serviço)"
        verbose_name_plural = "Categorias (Serviços)"
        ordering = ['secretaria', 'nome']
        unique_together = ('secretaria', 'nome')

class Municipe(models.Model):
    cpf = models.CharField(max_length=11, unique=True, verbose_name="CPF")
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    email = models.EmailField(max_length=255, unique=True, verbose_name="E-mail")
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    def __str__(self):
        return self.nome_completo
        
    class Meta:
        verbose_name = "Munícipe"
        verbose_name_plural = "Munícipes"

class Atendimento(models.Model):
    municipe = models.ForeignKey(Municipe, on_delete=models.PROTECT, verbose_name="Munícipe")
    protocolo = models.CharField(max_length=50, unique=True, verbose_name="Protocolo")
    servico_realizado = models.CharField(
        max_length=255, 
        verbose_name="Serviço Realizado (Antigo)",
        blank=True, null=True
    )
    categoria = models.ForeignKey(
        Categoria, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Categoria do Serviço"
    )
    data_conclusao = models.DateField(verbose_name="Data de Conclusão")
    bairro = models.CharField(max_length=100, blank=True, null=True)
    distrito = models.CharField(max_length=100, blank=True, null=True, verbose_name="Distrito")
    latitude = models.FloatField(
        null=True, 
        blank=True, 
        verbose_name="Latitude"
    )
    longitude = models.FloatField(
        null=True, 
        blank=True, 
        verbose_name="Longitude"
    )
    secretaria = models.ForeignKey(Secretaria, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Secretaria Responsável")
    data_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Protocolo {self.protocolo} - {self.municipe.nome_completo}"

    class Meta:
        verbose_name = "Atendimento"
        verbose_name_plural = "Atendimentos"

class Pesquisa(models.Model):
    atendimento = models.OneToOneField(Atendimento, on_delete=models.CASCADE, verbose_name="Atendimento")
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    data_envio = models.DateTimeField(null=True, blank=True, verbose_name="Data de Envio")
    data_resposta = models.DateTimeField(null=True, blank=True, verbose_name="Data da Resposta")
    respondida = models.BooleanField(default=False)
        
    NOTA_CHOICES = [
        (1, 'Muito Insatisfeito'),
        (2, 'Insatisfeito'),
        (3, 'Neutro'),
        (4, 'Satisfeito'),
        (5, 'Muito Satisfeito'),
    ]
    
    nota_geral = models.IntegerField(choices=NOTA_CHOICES, null=True, blank=True, verbose_name="Nota Geral do Atendimento")
    comentario = models.TextField(blank=True, null=True, verbose_name="Comentário do Munícipe")
    
    def __str__(self):
        return f"Pesquisa do Protocolo {self.atendimento.protocolo}"

    class Meta:
        verbose_name = "Pesquisa de Satisfação"
        verbose_name_plural = "Pesquisas de Satisfação"