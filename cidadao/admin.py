# /var/www/ouvidoria/cidadao/admin.py

from django.contrib import admin, messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from urllib.parse import quote
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Municipe, Atendimento, Pesquisa, Secretaria,
    Entidade, UnidadeAdm, Categoria
)

@admin.register(Entidade)
class EntidadeAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(UnidadeAdm)
class UnidadeAdmAdmin(admin.ModelAdmin):
    list_display = ('nome', 'secretaria')
    list_filter = ('secretaria',)
    search_fields = ('nome',)
    autocomplete_fields = ['secretaria']

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'secretaria', 'unidade_adm', 'tipo', 'prazo')
    list_filter = ('secretaria', 'unidade_adm', 'tipo')    
    search_fields = ('nome',)
    autocomplete_fields = ['secretaria', 'unidade_adm']

@admin.register(Secretaria)
class SecretariaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla', 'entidade') 
    list_filter = ('entidade',)
    search_fields = ('nome', 'sigla')

class MunicipeAdmin(admin.ModelAdmin):
    """
    Configurações da interface de administração para o model Municipe.
    """
    list_display = ('nome_completo', 'email', 'cpf', 'data_criacao')
    search_fields = ('nome_completo', 'cpf', 'email')
    list_filter = ('data_criacao',)
    readonly_fields = ('data_criacao', 'data_atualizacao')

admin.site.register(Municipe, MunicipeAdmin)

@admin.register(Atendimento)
class AtendimentoAdmin(admin.ModelAdmin):
    list_display = (
        'protocolo', 
        'municipe', 
        'categoria', 
        'secretaria', 
        'bairro', 
        'distrito', 
        'data_conclusao', 
        'latitude',
        'longitude',
        'pesquisa_enviada'
    )
    search_fields = ('protocolo', 'municipe__nome_completo', 'municipe__cpf', 'categoria__nome', 'secretaria__nome', 'bairro', 'distrito')
    list_filter = ('data_conclusao', 'secretaria', 'bairro', 'distrito', 'categoria')
    
    autocomplete_fields = ['municipe', 'secretaria', 'categoria']
    
    @admin.display(description='Pesquisa Enviada?', boolean=True)
    def pesquisa_enviada(self, obj):
        try:
            return obj.pesquisa.data_envio is not None
        except Pesquisa.DoesNotExist:
            return False

    actions = ['enviar_pesquisa_por_email']

    @admin.action(description='Enviar pesquisa de satisfação por e-mail')
    def enviar_pesquisa_por_email(self, request, queryset):
        base_url_frontend = 'https://ouvidoria.mogidascruzes.sp.gov.br' 
        enviados_com_sucesso = 0

        for atendimento in queryset:
            try:
                pesquisa = atendimento.pesquisa
                if atendimento.municipe.email:
                    
                    context = {
                        'nome_cidadao': atendimento.municipe.nome_completo,
                        'protocolo': atendimento.protocolo,
                        'servico': atendimento.categoria.nome if atendimento.categoria else atendimento.servico_realizado, 
                        'url_pesquisa': f"{base_url_frontend}/pesquisa/{pesquisa.token}"
                    }

                    email_html = render_to_string('emails/pesquisa_email.html', context)
                    email_text = render_to_string('emails/pesquisa_email.txt', context)

                    try:
                        send_mail(
                            subject='Sua opinião é importante para nós! Pesquisa de Satisfação',
                            message=email_text,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[atendimento.municipe.email],
                            html_message=email_html,
                            fail_silently=False,
                        )
                        
                        pesquisa.data_envio = timezone.now()
                        pesquisa.save()
                        
                        enviados_com_sucesso += 1
                    except Exception as e:
                        self.message_user(request, f"Falha ao enviar e-mail para o protocolo {atendimento.protocolo}: {e}", level='error')
                
            except Pesquisa.DoesNotExist:
                self.message_user(request, f"Protocolo {atendimento.protocolo} não possui pesquisa.", level='warning')

        if enviados_com_sucesso > 0:
            self.message_user(request, f"{enviados_com_sucesso} e-mail(s) de pesquisa enviados com sucesso.", level='success')


@admin.register(Pesquisa)
class PesquisaAdmin(admin.ModelAdmin):
    list_display = (
        'atendimento', 
        'respondida', 
        'data_envio', 
        'data_resposta', 
        '_gerar_link_whatsapp'
    )
    list_filter = ('respondida', 'data_envio')
    search_fields = ('atendimento__protocolo', 'atendimento__municipe__nome_completo')
    actions = ['marcar_como_enviada_e_gerar_links']

    @admin.display(description="Link de Envio (WhatsApp)")
    def _gerar_link_whatsapp(self, obj):
        if obj.respondida:
            return "Já respondida"
            
        municipe = obj.atendimento.municipe
        if not municipe.telefone:
            return "Munícipe sem telefone"
            
        telefone_limpo = "".join(filter(str.isdigit, municipe.telefone))
        if not telefone_limpo.startswith('55'):
            telefone_limpo = f"55{telefone_limpo}"

        link_pesquisa = f"https://ouvidoria.mogidascruzes.sp.gov.br/pesquisa/{obj.token}/"
        
        template_mensagem = f"""Olá, {municipe.nome_completo}!
        
        Aqui é da Ouvidoria Ativa. Notamos que seu atendimento (Protocolo: {obj.atendimento.protocolo}) foi concluído.

        Para melhorarmos nossos serviços, gostaríamos da sua opinião!
        Por favor, responda nossa breve pesquisa no link:
        {link_pesquisa}

        Obrigado!"""
        
        mensagem_encoded = quote(template_mensagem)
        
        link_wa_me = f"https://wa.me/{telefone_limpo}?text={mensagem_encoded}"
        
        return format_html('<a href="{}" target="_blank">Abrir WhatsApp</a>', link_wa_me)

    @admin.action(description="Marcar como Enviada (e Gerar Links)")
    def marcar_como_enviada_e_gerar_links(self, request, queryset):
        pesquisas_para_enviar = queryset.filter(
            respondida=False, 
            data_envio__isnull=True, 
            atendimento__municipe__telefone__isnull=False
        ).exclude(atendimento__municipe__telefone__exact='')

        count = pesquisas_para_enviar.count()

        if count == 0:
            self.message_user(request, "Nenhuma pesquisa válida selecionada (verifique se já foram enviadas ou se o munícipe tem telefone).", messages.WARNING)
            return

        pesquisas_para_enviar.update(data_envio=timezone.now())
        self.message_user(request, f"{count} pesquisas foram marcadas como 'enviadas'. Os links de envio agora estão disponíveis na coluna 'Link de Envio'.", messages.SUCCESS)