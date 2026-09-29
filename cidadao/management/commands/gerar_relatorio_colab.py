import csv
import os
import time
import requests
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Gera um relatório de chamados do Colab'
        'contendo: protocolo, categoria, status e descrição da demanda.'
    )

    BASE_URL = "https://api.colabapp.com/v2/integration"

    STATUS_LEGIVEL = {
        'OPEN': 'Aberto',
        'PENDING': 'Pendente',
        'IN_PROGRESS': 'Em andamento',
        'WAITING': 'Aguardando',
        'SOLVED': 'Resolvido',
        'CLOSED': 'Fechado',
        'FINALIZADO': 'Finalizado',
        'ATENDIDO': 'Atendido',
        'FECHADO': 'Fechado',
        'RESOLVIDO': 'Resolvido',
        'CONCLUIDO': 'Concluído',
        'RECUSADO': 'Recusado',
        '0': 'Aberto',
        '1': 'Em andamento',
        '2': 'Resolvido',
        '3': 'Fechado',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Quantidade de dias para trás a partir de hoje (padrão: 7).'
        )
        parser.add_argument(
            '--inicio',
            type=str,
            default=None,
            help='Data inicial no formato AAAA-MM-DD (sobrepõe --dias).'
        )
        parser.add_argument(
            '--fim',
            type=str,
            default=None,
            help='Data final no formato AAAA-MM-DD (padrão: hoje).'
        )
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Caminho do arquivo CSV de saída. Se omitido, gera nome automático.'
        )
        parser.add_argument(
            '--status',
            type=str,
            default=None,
            help='Filtrar por status (ex: SOLVED,CLOSED). Padrão: todos.'
        )
        parser.add_argument(
            '--tabela',
            action='store_true',
            help='Exibe o resultado em tabela no terminal além de gerar o CSV.'
        )

    def handle(self, *args, **options):
        APP_ID = os.environ.get('COLAB_APP_ID')
        API_KEY = os.environ.get('COLAB_API_KEY')
        USER_TOKEN = os.environ.get('COLAB_USER_TOKEN')

        if not all([APP_ID, API_KEY, USER_TOKEN]):
            self.stdout.write(self.style.ERROR(
                "ERRO: Credenciais do Colab não configuradas no .env "
                "(COLAB_APP_ID, COLAB_API_KEY, COLAB_USER_TOKEN)."
            ))
            return

        self.headers = {
            'x-colab-application-id': APP_ID,
            'x-colab-rest-api-key': API_KEY,
            'x-colab-admin-user-auth-ticket': USER_TOKEN,
            'Content-Type': 'application/json'
        }

        try:
            dt_start, dt_end = self._resolver_periodo(options)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f"ERRO: {e}"))
            return

        filtro_status = None
        if options['status']:
            filtro_status = {s.strip().upper() for s in options['status'].split(',') if s.strip()}

        self.stdout.write("Carregando categorias do Colab...")
        category_map = self._carregar_categorias()
        if category_map is None:
            return
        self.stdout.write(self.style.SUCCESS(f"Mapeadas {len(category_map)} categorias externas."))

        self.stdout.write(f"Buscando chamados de {dt_start} até {dt_end}...")

        registros = self._buscar_chamados(dt_start, dt_end, category_map, filtro_status)

        if not registros:
            self.stdout.write(self.style.WARNING("Nenhum chamado encontrado no período."))
            return

        caminho_csv = options['output'] or self._nome_arquivo_padrao(dt_start, dt_end)
        self._gravar_csv(registros, caminho_csv)
        self.stdout.write(self.style.SUCCESS(
            f"\nRelatório gerado: {caminho_csv} ({len(registros)} registros)."
        ))

        if options['tabela']:
            self._imprimir_tabela(registros)

    def _resolver_periodo(self, options):
        if options['inicio']:
            try:
                dt_start = datetime.strptime(options['inicio'], '%Y-%m-%d')
            except ValueError:
                raise ValueError("Formato de --inicio inválido. Use AAAA-MM-DD.")
        else:
            dias = options['dias']
            if dias <= 0:
                raise ValueError("--dias deve ser maior que zero.")
            dt_start = datetime.combine(
                (timezone.now() - timedelta(days=dias)).date(),
                datetime.min.time()
            )

        if options['fim']:
            try:
                dt_end = datetime.strptime(options['fim'], '%Y-%m-%d')
                dt_end = dt_end.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise ValueError("Formato de --fim inválido. Use AAAA-MM-DD.")
        else:
            dt_end = datetime.now()

        if dt_start >= dt_end:
            raise ValueError("Data inicial deve ser anterior à data final.")

        return dt_start, dt_end

    def _carregar_categorias(self):
        try:
            resp = requests.get(f"{self.BASE_URL}/categories", headers=self.headers, timeout=15)
            if resp.status_code != 200:
                self.stdout.write(self.style.ERROR(
                    f"Erro ao baixar categorias: {resp.status_code}"
                ))
                return None
            cat_map = {}
            for cat in resp.json().get('categories', []):
                cat_map[cat['id']] = cat['name'].strip()
            return cat_map
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro de conexão ao buscar categorias: {e}"))
            return None

    def _buscar_chamados(self, dt_start, dt_end, category_map, filtro_status):
        registros = []
        current_chunk = dt_start

        while current_chunk < dt_end:
            next_chunk = current_chunk + timedelta(hours=6)
            if next_chunk > dt_end:
                next_chunk = dt_end

            params = {
                'start_date': current_chunk.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': next_chunk.strftime('%Y-%m-%d %H:%M:%S'),
            }

            try:
                response = requests.get(
                    f"{self.BASE_URL}/posts",
                    params=params,
                    headers=self.headers,
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        posts = data
                    elif isinstance(data, dict):
                        posts = data.get('posts', [])
                    else:
                        posts = []

                    if posts:
                        self.stdout.write(
                            f" > Período {current_chunk.strftime('%d/%m %H:%M')}: "
                            f"{len(posts)} registros encontrados."
                        )
                        for post in posts:
                            linha = self._montar_linha(post, category_map, filtro_status)
                            if linha is not None:
                                registros.append(linha)
                    else:
                        self.stdout.write(
                            f" > Período {current_chunk.strftime('%d/%m %H:%M')}: nenhum registro."
                        )

                elif response.status_code == 429:
                    self.stdout.write(self.style.WARNING("Rate Limit atingido. Pausando 10s..."))
                    time.sleep(10)
                    continue
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Erro HTTP {response.status_code} no período "
                        f"{current_chunk} -> {next_chunk}."
                    ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao processar lote: {e}"))

            current_chunk = next_chunk
            time.sleep(1)

        return registros

    def _montar_linha(self, item, cat_map, filtro_status):
        try:
            protocolo_externo = str(item.get('id', '')).strip()
            if not protocolo_externo:
                return None

            status_raw = str(item.get('status', '')).strip().upper()
            if filtro_status and status_raw not in filtro_status:
                return None

            status_legivel = self.STATUS_LEGIVEL.get(status_raw, status_raw or 'Desconhecido')

            categoria_id = item.get('category_id')
            if not categoria_id and isinstance(item.get('category'), dict):
                categoria_id = item['category'].get('id')

            categoria_nome = ''
            if categoria_id and categoria_id in cat_map:
                categoria_nome = cat_map[categoria_id]
            elif isinstance(item.get('category'), dict):
                categoria_nome = (item['category'].get('name') or '').strip()

            descricao = (
                item.get('description')
                or item.get('content')
                or item.get('message')
                or item.get('text')
                or item.get('body')
                or ''
            )
            descricao = str(descricao).strip().replace('\r', ' ').replace('\n', ' ')

            return {
                'protocolo': f"COLAB-{protocolo_externo}",
                'categoria': categoria_nome or 'Sem categoria',
                'status': status_legivel,
                'descricao': descricao or 'Sem descrição',
            }
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"   [!] Erro ao montar linha do protocolo {item.get('id')}: {e}"
            ))
            return None

    def _nome_arquivo_padrao(self, dt_start, dt_end):
        stamp_inicio = dt_start.strftime('%Y%m%d')
        stamp_fim = dt_end.strftime('%Y%m%d')
        return f"relatorio_colab_{stamp_inicio}_a_{stamp_fim}.csv"

    def _gravar_csv(self, registros, caminho):
        diretorio = os.path.dirname(caminho)
        if diretorio and not os.path.exists(diretorio):
            os.makedirs(diretorio, exist_ok=True)

        with open(caminho, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_ALL)
            writer.writerow(['Protocolo', 'Categoria', 'Status', 'Descrição da demanda'])
            for r in registros:
                writer.writerow([r['protocolo'], r['categoria'], r['status'], r['descricao']])

    def _imprimir_tabela(self, registros):
        self.stdout.write("\n" + "=" * 120)
        cab = f"{'PROTOCOLO':<20} | {'CATEGORIA':<28} | {'STATUS':<14} | DESCRIÇÃO"
        self.stdout.write(cab)
        self.stdout.write("-" * 120)
        for r in registros:
            desc = r['descricao'][:60] + ('...' if len(r['descricao']) > 60 else '')
            linha = (
                f"{r['protocolo']:<20} | "
                f"{r['categoria'][:28]:<28} | "
                f"{r['status'][:14]:<14} | "
                f"{desc}"
            )
            self.stdout.write(linha)
        self.stdout.write("=" * 120)
