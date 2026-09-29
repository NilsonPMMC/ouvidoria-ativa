import requests
import time
import os
import re
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from cidadao.models import Atendimento, Municipe, Categoria, Secretaria, Pesquisa

class Command(BaseCommand):
    help = 'Sincroniza atendimentos concluídos da API do Colab para o sistema de Ouvidoria.'
    
    BASE_URL = "https://api.colabapp.com/v2/integration"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = None

    def handle(self, *args, **options):
        APP_ID = os.environ.get('COLAB_APP_ID')
        API_KEY = os.environ.get('COLAB_API_KEY')
        USER_TOKEN = os.environ.get('COLAB_USER_TOKEN')

        if not all([APP_ID, API_KEY, USER_TOKEN]):
            self.stdout.write(self.style.ERROR("ERRO: Credenciais do Colab não configuradas no .env (COLAB_APP_ID, COLAB_API_KEY, COLAB_USER_TOKEN)."))
            return

        self.headers = {
            'x-colab-application-id': APP_ID,
            'x-colab-rest-api-key': API_KEY,
            'x-colab-admin-user-auth-ticket': USER_TOKEN,
            'Content-Type': 'application/json'
        }

        self.stdout.write("Carregando categorias do Colab...")
        category_map = {}
        try:
            resp = requests.get(f"{self.BASE_URL}/categories", headers=self.headers)
            if resp.status_code == 200:
                for cat in resp.json().get('categories', []):
                    category_map[cat['id']] = cat['name'].strip()
                self.stdout.write(self.style.SUCCESS(f"Mapeadas {len(category_map)} categorias externas."))
            else:
                self.stdout.write(self.style.ERROR(f"Erro ao baixar categorias: {resp.status_code}"))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro de conexão: {e}"))
            return

        ultimo = Atendimento.objects.filter(protocolo__startswith='COLAB-').order_by('-data_conclusao').first()
        
        if ultimo:
            inicio = ultimo.data_conclusao
        else:
            inicio = timezone.now().date() - timedelta(days=7)

        if isinstance(inicio, datetime):
            dt_start = inicio
        else:
            dt_start = datetime.combine(inicio, datetime.min.time())
        dt_end = datetime.now()

        self.stdout.write(f"Iniciando sincronização de {dt_start} até {dt_end}...")

        current_chunk = dt_start
        total_importados = 0
        total_ignorados = 0

        while current_chunk < dt_end:
            next_chunk = current_chunk + timedelta(hours=6)
            if next_chunk > dt_end: next_chunk = dt_end

            params = {
                'start_date': current_chunk.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': next_chunk.strftime('%Y-%m-%d %H:%M:%S')
            }

            try:
                response = requests.get(f"{self.BASE_URL}/posts", params=params, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if isinstance(data, list):
                        posts = data
                    elif isinstance(data, dict):
                        posts = data.get('posts', [])
                    else:
                        posts = []

                    if posts:
                        self.stdout.write(f" > Período {current_chunk.strftime('%d/%m %H:%M')}: {len(posts)} registros encontrados.")
                        
                        for post in posts:
                            if self.processar_post(post, category_map):
                                total_importados += 1
                            else:
                                total_ignorados += 1
                    else:
                        self.stdout.write(f" > Período {current_chunk.strftime('%d/%m %H:%M')}: Nenhum registro.")

                elif response.status_code == 429:
                    self.stdout.write(self.style.WARNING("Rate Limit atingido. Pausando 10s..."))
                    time.sleep(10)
                    continue

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao processar lote: {e}"))

            current_chunk = next_chunk
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"\nSincronização Finalizada! Importados: {total_importados} | Ignorados: {total_ignorados}"))

    def processar_post(self, item, cat_map):
        """
        Processa um post/chamado do Colab e importa para o sistema local.
        Retorna True se importado com sucesso, False caso contrário.
        """
        try:
            protocolo_externo = str(item.get('id'))
            status_raw = str(item.get('status', '')).upper()
            
            STATUS_ACEITOS = ['SOLVED', 'CLOSED', 'FINALIZADO', '2', '3', 'ATENDIDO', 'FECHADO', 'RESOLVIDO', 'CONCLUIDO', 'RECUSADO']
            
            if status_raw not in STATUS_ACEITOS:
                return False 

            protocolo_local = f"COLAB-{protocolo_externo}"
            if Atendimento.objects.filter(protocolo=protocolo_local).exists():
                self.stdout.write(f"   [⏭] Protocolo {protocolo_local} já importado. Pulando...")
                return False

            nome_completo = (item.get('citizen') or '').strip()
            
            if not nome_completo:
                self.stdout.write(self.style.WARNING(f"   [!] Protocolo {protocolo_externo}: Nome do cidadão não encontrado. Pulando..."))
                return False

            email_raw = (
                item.get('citizen_email') or 
                item.get('email') or 
                ''
            ).strip()
            
            if not email_raw:
                email_raw = f"sem_email_{protocolo_externo}@ouvidoria.sistema"
            
            cpf_raw = (
                item.get('citizen_cpf') or 
                item.get('cpf') or 
                ''
            ).strip()
            
            import re
            cpf_raw = re.sub(r'\D', '', cpf_raw) if cpf_raw else f"COLAB{protocolo_externo}"[:11]
            
            telefone_raw = (item.get('phone') or '').strip()
            
            if not email_raw or '@' not in email_raw:
                email_fake = f"sem_email_{protocolo_externo}@ouvidoria.sistema"
                self.stdout.write(self.style.WARNING(f"   [⚠] Protocolo {protocolo_externo}: Email não disponível (LGPD). Usando email fake para estatísticas."))
                email_final = email_fake
            else:
                email_final = email_raw.lower()
            
            if not cpf_raw or len(cpf_raw) != 11:
                protocolo_digits = re.sub(r'\D', '', protocolo_externo)[-11:]
                cpf_fake = protocolo_digits.zfill(11)
                self.stdout.write(self.style.WARNING(f"   [⚠] Protocolo {protocolo_externo}: CPF não disponível (LGPD). Usando CPF fake para estatísticas."))
                cpf_final = cpf_fake
            else:
                cpf_final = cpf_raw
            
            categoria_id = item.get('category_id') or item.get('category', {}).get('id')
            categoria_nome = None
            if categoria_id and categoria_id in cat_map:
                categoria_nome = cat_map[categoria_id]
            
            data_conclusao_str = (
                item.get('solved_at') or 
                item.get('closed_at') or 
                item.get('updated_at') or 
                item.get('created_at') or 
                ''
            )
            
            try:
                if data_conclusao_str:
                    if 'T' in data_conclusao_str:
                        data_conclusao = parse_datetime(data_conclusao_str)
                    else:
                        data_conclusao = datetime.strptime(data_conclusao_str, '%Y-%m-%d %H:%M:%S')
                    
                    if data_conclusao:
                        data_conclusao = data_conclusao.date()
                    else:
                        data_conclusao = timezone.now().date()
                else:
                    data_conclusao = timezone.now().date()
            except (ValueError, TypeError):
                data_conclusao = timezone.now().date()
            
            bairro = (item.get('neighborhood') or item.get('address_neighborhood') or item.get('bairro') or '').strip()
            distrito = (item.get('district') or item.get('distrito') or '').strip()
            
            latitude = item.get('lat') or item.get('latitude')
            longitude = item.get('lng') or item.get('longitude')
            
            try:
                latitude = float(latitude) if latitude else None
            except (ValueError, TypeError):
                latitude = None
                
            try:
                longitude = float(longitude) if longitude else None
            except (ValueError, TypeError):
                longitude = None

            with transaction.atomic():
                # Buscar ou criar categoria
                categoria_obj = None
                secretaria_obj = None
                
                if categoria_nome:
                    try:
                        categoria_obj = Categoria.objects.get(nome__iexact=categoria_nome.strip())
                        secretaria_obj = categoria_obj.secretaria
                    except Categoria.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"   [⚠] Categoria '{categoria_nome}' não encontrada no sistema. Criando atendimento sem categoria."))
                
                try:
                    municipe = Municipe.objects.get(cpf=cpf_final)
                    municipe_created = False
                except Municipe.DoesNotExist:
                    email_em_uso = Municipe.objects.filter(email=email_final).exists()
                    if email_em_uso and '@ouvidoria.sistema' in email_final:
                        email_final = f"sem_email_{protocolo_externo}_{cpf_final[-4:]}@ouvidoria.sistema"
                        self.stdout.write(self.style.WARNING(f"   [⚠] Email fake em conflito. Usando: {email_final}"))
                    
                    try:
                        municipe = Municipe.objects.create(
                            cpf=cpf_final,
                            nome_completo=nome_completo,
                            email=email_final,
                            telefone=telefone_raw[:20] if telefone_raw else None,
                        )
                        municipe_created = True
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"   [⚠] Erro ao criar munícipe: {e}. Tentando buscar por email..."))
                        try:
                            municipe = Municipe.objects.get(email=email_final)
                            municipe_created = False
                        except Municipe.DoesNotExist:
                            email_final = f"sem_email_{protocolo_externo}_{timezone.now().timestamp()}@ouvidoria.sistema"
                            municipe = Municipe.objects.create(
                                cpf=cpf_final,
                                nome_completo=nome_completo,
                                email=email_final,
                                telefone=telefone_raw[:20] if telefone_raw else None,
                            )
                            municipe_created = True
                
                if not municipe_created:
                    update_fields = []
                    if municipe.nome_completo != nome_completo:
                        municipe.nome_completo = nome_completo
                        update_fields.append('nome_completo')
                    
                    if municipe.email != email_final:
                        if '@ouvidoria.sistema' in municipe.email:
                            email_em_uso = Municipe.objects.filter(email=email_final).exclude(cpf=cpf_final).exists()
                            if not email_em_uso:
                                municipe.email = email_final
                                update_fields.append('email')
                    
                    if telefone_raw and municipe.telefone != telefone_raw[:20]:
                        municipe.telefone = telefone_raw[:20]
                        update_fields.append('telefone')
                    
                    if update_fields:
                        municipe.save(update_fields=update_fields)
                
                atendimento = Atendimento.objects.create(
                    protocolo=protocolo_local,
                    municipe=municipe,
                    categoria=categoria_obj,
                    secretaria=secretaria_obj,
                    servico_realizado=categoria_nome or 'Serviço do Colab',
                    data_conclusao=data_conclusao,
                    bairro=bairro[:100] if bairro else None,
                    distrito=distrito[:100] if distrito else None,
                    latitude=latitude,
                    longitude=longitude,
                )
                
                pesquisa, pesquisa_created = Pesquisa.objects.get_or_create(
                    atendimento=atendimento
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f"   [✓] Importado: {protocolo_local} - {nome_completo} "
                    f"({'Email real' if '@ouvidoria.sistema' not in email_final else 'Email fake - LGPD'})"
                ))
                
                return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   [!] Erro ao processar protocolo {item.get('id')}: {e}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            return False