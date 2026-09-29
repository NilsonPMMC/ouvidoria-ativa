# /var/www/ouvidoria/cidadao/management/commands/importar_atendimentos.py
import csv
import os
import re
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from cidadao.models import Atendimento, Municipe, Categoria, Pesquisa

class Command(BaseCommand):
    help = 'Importa atendimentos a partir de um arquivo CSV do Colab.'
    
    def add_arguments(self, parser):
        parser.add_argument('caminho_csv', type=str, help='Caminho para o arquivo CSV (ex: atendimentos.csv)')
        parser.add_argument(
            '--prefixo-protocolo',
            type=str,
            default='COLAB-',
            help='Prefixo para adicionar aos protocolos (padrão: COLAB-)'
        )
        parser.add_argument(
            '--skip-duplicados',
            action='store_true',
            help='Pular atendimentos que já existem (baseado no protocolo)'
        )

    def handle(self, *args, **options):
        caminho_arquivo = options['caminho_csv']
        prefixo_protocolo = options['prefixo_protocolo']
        skip_duplicados = options['skip_duplicados']

        if not os.path.exists(caminho_arquivo):
            raise CommandError(f'Arquivo não encontrado: {caminho_arquivo}')

        self.stdout.write(f"Lendo arquivo: {caminho_arquivo}...")
        
        total_importados = 0
        total_ignorados = 0
        total_erros = 0
        total_duplicados = 0

        try:
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                # Usar DictReader para mapear colunas pelo cabeçalho
                csv_reader = csv.DictReader(f)
                
                # Verificar se as colunas esperadas existem
                colunas_esperadas = [
                    'CPF do Cidadão', 'Nome do Cidadão', 'E-mail do Cidadão',
                    'Protocolo da Empresa', 'Categoria', 'Data de conclusão', 'Origem', 'Bairro'
                ]
                
                colunas_encontradas = csv_reader.fieldnames
                if not colunas_encontradas:
                    raise CommandError("CSV não possui cabeçalho ou está vazio.")
                
                self.stdout.write(f"Colunas encontradas: {', '.join(colunas_encontradas)}")
                
                # Normalizar nomes das colunas
                colunas_map = {}
                for col_esperada in colunas_esperadas:
                    for col_encontrada in colunas_encontradas:
                        if col_esperada.lower() == col_encontrada.lower():
                            colunas_map[col_esperada] = col_encontrada
                            break
                
                if len(colunas_map) < 6:  # Mínimo necessário
                    raise CommandError(f"Colunas esperadas não encontradas. Encontradas: {colunas_encontradas}")

                self.stdout.write("Iniciando importação de atendimentos...")

                for linha_num, row in enumerate(csv_reader, start=2):  # Começa em 2 (linha 1 é cabeçalho)
                    try:
                        cpf_raw = row.get(colunas_map.get('CPF do Cidadão', 'CPF do Cidadão'), '').strip()
                        nome = row.get(colunas_map.get('Nome do Cidadão', 'Nome do Cidadão'), '').strip()
                        email = row.get(colunas_map.get('E-mail do Cidadão', 'E-mail do Cidadão'), '').strip()
                        protocolo_raw = row.get(colunas_map.get('Protocolo da Empresa', 'Protocolo da Empresa'), '').strip()
                        categoria_nome = row.get(colunas_map.get('Categoria', 'Categoria'), '').strip()
                        data_conclusao_str = row.get(colunas_map.get('Data de conclusão', 'Data de conclusão'), '').strip()
                        origem = row.get(colunas_map.get('Origem', 'Origem'), '').strip()
                        bairro = row.get(colunas_map.get('Bairro', 'Bairro'), '').strip()

                        # Validações básicas
                        if not cpf_raw or not nome or not protocolo_raw:
                            self.stdout.write(self.style.WARNING(f"Linha {linha_num}: Dados obrigatórios faltando. Pulando..."))
                            total_ignorados += 1
                            continue

                        # Limpar CPF
                        cpf = re.sub(r'\D', '', cpf_raw)
                        if len(cpf) != 11:
                            self.stdout.write(self.style.WARNING(f"Linha {linha_num}: CPF inválido '{cpf_raw}'. Pulando..."))
                            total_ignorados += 1
                            continue

                        # Validar email
                        if not email or '@' not in email:
                            self.stdout.write(self.style.WARNING(f"Linha {linha_num}: Email inválido '{email}'. Pulando..."))
                            total_ignorados += 1
                            continue

                        # Formatar protocolo com prefixo
                        protocolo = f"{prefixo_protocolo}{protocolo_raw}"

                        # Verificar duplicatas
                        if skip_duplicados and Atendimento.objects.filter(protocolo=protocolo).exists():
                            self.stdout.write(f"   [⏭] Linha {linha_num}: Protocolo {protocolo} já existe. Pulando...")
                            total_duplicados += 1
                            continue

                        # Parsear data
                        try:
                            data_obj = datetime.strptime(data_conclusao_str, '%d/%m/%Y')
                            data_conclusao = data_obj.date()
                        except ValueError:
                            self.stdout.write(self.style.ERROR(f"Linha {linha_num}: Data inválida '{data_conclusao_str}'. Pulando."))
                            total_ignorados += 1
                            continue

                        # Processar no banco de dados
                        with transaction.atomic():
                            # Buscar ou criar categoria
                            categoria_obj = None
                            secretaria_obj = None
                            
                            if categoria_nome:
                                try:
                                    categoria_obj = Categoria.objects.get(nome__iexact=categoria_nome)
                                    secretaria_obj = categoria_obj.secretaria
                                except Categoria.DoesNotExist:
                                    self.stdout.write(self.style.WARNING(
                                        f"   [⚠] Linha {linha_num}: Categoria '{categoria_nome}' não encontrada. Criando atendimento sem categoria."
                                    ))

                            # Criar ou atualizar Munícipe
                            municipe, municipe_created = Municipe.objects.update_or_create(
                                cpf=cpf,
                                defaults={
                                    'nome_completo': nome,
                                    'email': email.lower(),
                                    'telefone': None,  # Não temos telefone no CSV
                                }
                            )

                            # Criar ou atualizar Atendimento
                            atendimento, atendimento_created = Atendimento.objects.update_or_create(
                                protocolo=protocolo,
                                defaults={
                                    'municipe': municipe,
                                    'categoria': categoria_obj,
                                    'secretaria': secretaria_obj,
                                    'servico_realizado': categoria_nome or 'Serviço do Colab',
                                    'data_conclusao': data_conclusao,
                                    'bairro': bairro[:100] if bairro else None,
                                    'distrito': None,  # Não temos distrito no CSV
                                }
                            )

                            # Criar Pesquisa se não existir
                            pesquisa, pesquisa_created = Pesquisa.objects.get_or_create(
                                atendimento=atendimento
                            )

                            total_importados += 1
                            if linha_num % 100 == 0:
                                self.stdout.write(f"   Processados {linha_num} linhas... ({total_importados} importados)")

                    except Exception as e:
                        total_erros += 1
                        self.stdout.write(self.style.ERROR(f"Linha {linha_num}: Erro inesperado - {e}"))
                        import traceback
                        self.stdout.write(self.style.ERROR(traceback.format_exc()))

        except Exception as e:
            raise CommandError(f"Erro ao processar arquivo: {e}")

        # Resumo final
        self.stdout.write(self.style.SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.SUCCESS("IMPORTAÇÃO CONCLUÍDA!"))
        self.stdout.write(self.style.SUCCESS("="*60))
        self.stdout.write(f"✓ Importados com sucesso: {total_importados}")
        self.stdout.write(f"⏭ Duplicados ignorados: {total_duplicados}")
        self.stdout.write(f"⚠ Linhas ignoradas (dados inválidos): {total_ignorados}")
        self.stdout.write(f"❌ Erros: {total_erros}")
        self.stdout.write(self.style.SUCCESS("="*60))