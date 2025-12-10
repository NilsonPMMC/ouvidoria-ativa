# /var/www/ouvidoria/cidadao/management/commands/importar_atendimentos.py
import csv
import requests
import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Importa atendimentos a partir de um arquivo CSV externo.'

    def add_arguments(self, parser):
        parser.add_argument('caminho_csv', type=str, help='Caminho para o arquivo CSV (ex: atendimentos.csv)')

    def handle(self, *args, **options):
        api_url = 'http://localhost:8001/api/atendimentos/registrar/'
        caminho_arquivo = options['caminho_csv']

        if not os.path.exists(caminho_arquivo):
            raise CommandError(f'Arquivo não encontrado: {caminho_arquivo}')

        self.stdout.write(f"Lendo arquivo: {caminho_arquivo}...")

        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            # Lê as linhas e remove espaços extras
            data_lines = [line.strip() for line in f if line.strip()]
            
        csv_reader = csv.reader(data_lines, delimiter=',')
        
        # Tenta pular o cabeçalho se existir
        header = next(csv_reader, None)
        if header and "CPF" not in header[0]:
            # Se a primeira linha não parecer cabeçalho, voltamos o ponteiro (opcional, aqui assumimos que tem cabeçalho)
            pass

        self.stdout.write("Iniciando importação de atendimentos...")

        for row in csv_reader:
            try:
                # Garante que temos 9 colunas
                if len(row) < 9:
                    self.stderr.write(self.style.WARNING(f"Linha incompleta ignorada: {row}"))
                    continue

                cpf, nome, email, telefone, categoria_nome, protocolo, data_conclusao, bairro, distrito = row

                try:
                    data_obj = datetime.strptime(data_conclusao.strip(), '%d/%m/%Y')
                    data_formatada = data_obj.strftime('%Y-%m-%d')
                except ValueError:
                    self.stderr.write(self.style.ERROR(f"Protocolo {protocolo}: Data inválida '{data_conclusao}'. Pulando."))
                    continue

                payload = {
                    "cpf": cpf.strip(),
                    "nome_completo": nome.strip(),
                    "email": email.strip(),
                    "telefone": telefone.strip() if telefone else "",
                    "protocolo": protocolo.strip(),
                    "categoria_nome": categoria_nome.strip(),
                    "data_conclusao": data_formatada,
                    "bairro": bairro.strip() if bairro else "",
                    "distrito": distrito.strip() if distrito else ""
                }

                response = requests.post(api_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})

                if response.status_code == 201:
                    token = response.json().get('token')
                    self.stdout.write(self.style.SUCCESS(f"OK: Protocolo {protocolo} (Token: {token})"))
                else:
                    self.stderr.write(self.style.ERROR(f"ERRO {protocolo}: {response.status_code} - {response.text}"))

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Erro inesperado na linha: {e}"))

        self.stdout.write(self.style.SUCCESS("Importação concluída!"))