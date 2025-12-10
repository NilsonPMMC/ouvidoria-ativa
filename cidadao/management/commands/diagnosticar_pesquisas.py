# /var/www/ouvidoria/cidadao/management/commands/diagnosticar_pesquisas.py

import datetime
from django.core.management.base import BaseCommand, CommandError
from cidadao.models import Atendimento, Pesquisa

class Command(BaseCommand):
    help = 'Diagnostica o status das pesquisas para atendimentos de uma data específica.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            required=True,
            help='A data dos atendimentos para diagnosticar (formato: YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        try:
            target_date_str = options['date']
            target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('Formato de data inválido. Use YYYY-MM-DD.')

        self.stdout.write(f"--- Diagnóstico de Pesquisas para Atendimentos de {target_date_str} ---")

        # 1. Busca TODOS os atendimentos da data, sem filtrar pela pesquisa
        atendimentos_do_dia = Atendimento.objects.filter(data_conclusao=target_date)
        total_atendimentos = atendimentos_do_dia.count()

        if not atendimentos_do_dia.exists():
            self.stdout.write(self.style.WARNING('Nenhum atendimento encontrado para esta data.'))
            return

        self.stdout.write(f"Total de {total_atendimentos} atendimentos encontrados.")

        # 2. Contadores para o nosso relatório
        com_pesquisa_nao_enviada = 0
        com_pesquisa_ja_enviada = 0
        sem_pesquisa_associada = 0

        # 3. Itera sobre cada atendimento para verificar seu status
        for atendimento in atendimentos_do_dia:
            try:
                # Tenta acessar a pesquisa relacionada
                pesquisa = atendimento.pesquisa
                if pesquisa.data_envio is None:
                    # Encontrou uma pesquisa que deveria ser enviada
                    com_pesquisa_nao_enviada += 1
                else:
                    # A pesquisa já foi enviada em outra ocasião
                    com_pesquisa_ja_enviada += 1
            except Pesquisa.DoesNotExist:
                # O atendimento não tem um registro de pesquisa
                sem_pesquisa_associada += 1

        # 4. Imprime o relatório final
        self.stdout.write("\n--- Relatório Final ---")
        self.stdout.write(self.style.SUCCESS(f"Atendimentos com pesquisa pendente de envio: {com_pesquisa_nao_enviada}"))
        self.stdout.write(self.style.WARNING(f"Atendimentos com pesquisa JÁ ENVIADA: {com_pesquisa_ja_enviada}"))
        self.stdout.write(self.style.ERROR(f"Atendimentos SEM PESQUISA ASSOCIADA: {sem_pesquisa_associada}"))
        self.stdout.write("-" * 25)