# /var/www/ouvidoria/cidadao/management/commands/enviar_pesquisas.py

import datetime
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from cidadao.models import Atendimento, Pesquisa

class Command(BaseCommand):
    help = 'Envia e-mails de pesquisa de satisfação para atendimentos de uma data específica.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            required=True,
            help='A data dos atendimentos para os quais enviar pesquisas (formato: YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        try:
            target_date_str = options['date']
            target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('Formato de data inválido. Use YYYY-MM-DD.')

        self.stdout.write(f"Procurando atendimentos concluídos em {target_date_str}...")

        # Removemos o prefixo 'atendimento__' dos filtros de 'municipe'
        atendimentos_para_enviar = Atendimento.objects.select_related(
            'pesquisa', 
            'municipe', 
            'categoria',
            'secretaria'
        ).filter(
            data_conclusao=target_date,
            pesquisa__data_envio__isnull=True,
            pesquisa__respondida=False,
            municipe__email__isnull=False 
        ).exclude(
            municipe__email=''
        )

        if not atendimentos_para_enviar.exists():
            self.stdout.write(self.style.WARNING('Nenhuma pesquisa pendente de envio para esta data.'))
            return

        total_encontrados = atendimentos_para_enviar.count()
        self.stdout.write(f"Encontrados {total_encontrados} atendimentos válidos. Iniciando envios...")

        enviados_com_sucesso = 0
        for atendimento in atendimentos_para_enviar:
            try:
                with transaction.atomic():
                    pesquisa = atendimento.pesquisa
                    cidadao = atendimento.municipe
                    servico = atendimento.categoria.nome if atendimento.categoria else atendimento.servico_realizado
                    
                    context = {
                        # Usando 'municipe_nome' como padronizado no template
                        'municipe_nome': cidadao.nome_completo.split(' ')[0], 
                        'protocolo': atendimento.protocolo,
                        'servico': servico,
                        'bairro': atendimento.bairro or 'Não informado',
                        'data_conclusao': atendimento.data_conclusao.strftime('%d/%m/%Y'),
                        'url_pesquisa': f"https://ouvidoria.mogidascruzes.sp.gov.br/pesquisa/{pesquisa.token}"
                    }

                    html_message = render_to_string('emails/pesquisa_email.html', context)
                    plain_message = render_to_string('emails/pesquisa_email.txt', context)

                    send_mail(
                        subject=f"Sua opinião sobre o atendimento {atendimento.protocolo} é importante!",
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[cidadao.email],
                        html_message=html_message,
                        fail_silently=False,
                    )

                    pesquisa.data_envio = timezone.now()
                    pesquisa.save(update_fields=['data_envio'])

                    enviados_com_sucesso += 1
                    self.stdout.write(self.style.SUCCESS(f"({enviados_com_sucesso}/{total_encontrados}) E-mail enviado para {cidadao.email} (Protocolo: {atendimento.protocolo})"))

            except Pesquisa.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"ERRO: Atendimento {atendimento.protocolo} não possui pesquisa associada."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"ERRO ao enviar para {cidadao.email} (Protocolo: {atendimento.protocolo}): {e}"))
        
        self.stdout.write(f"\nOperação concluída. Total de e-mails enviados com sucesso: {enviados_com_sucesso}.")