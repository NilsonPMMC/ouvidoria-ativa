# /var/www/ouvidoria/cidadao/management/commands/resetar_pesquisas.py

import datetime
from django.core.management.base import BaseCommand, CommandError
from cidadao.models import Atendimento

class Command(BaseCommand):
    help = 'Reseta o campo data_envio das pesquisas para uma data de atendimento específica.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            required=True,
            help='A data dos atendimentos para os quais resetar as pesquisas (formato: YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        try:
            target_date_str = options['date']
            target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('Formato de data inválido. Use YYYY-MM-DD.')

        self.stdout.write(f"Procurando atendimentos de {target_date_str} para resetar a data de envio da pesquisa...")

        # Encontra as pesquisas dos atendimentos da data especificada
        atendimentos_para_resetar = Atendimento.objects.filter(data_conclusao=target_date)

        if not atendimentos_para_resetar.exists():
            self.stdout.write(self.style.WARNING('Nenhum atendimento encontrado para esta data.'))
            return

        # Zera o campo 'data_envio' para todas as pesquisas encontradas
        pesquisas_atualizadas = 0
        for atendimento in atendimentos_para_resetar:
            try:
                atendimento.pesquisa.data_envio = None
                atendimento.pesquisa.save()
                pesquisas_atualizadas += 1
            except Atendimento.pesquisa.RelatedObjectDoesNotExist:
                # Ignora atendimentos que por ventura não tenham pesquisa
                pass
        
        self.stdout.write(self.style.SUCCESS(
            f"Operação concluída. {pesquisas_atualizadas} pesquisas foram resetadas e estão prontas para um novo envio."
        ))