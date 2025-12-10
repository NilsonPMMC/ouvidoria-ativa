# /var/www/ouvidoria/cidadao/management/commands/importar_categorias.py

import csv
import io
from django.core.management.base import BaseCommand
from cidadao.models import Entidade, Secretaria, UnidadeAdm, Categoria

# Dados CSV fornecidos por você
DADOS_CSV = """Categoria,Tipo,Prazo,Unid. Adm. Responsável,Secretaria_Órgão,Entidade
Capinação de guias e sarjetas,Serviço,30,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Desobstrução de galeria de drenagem,Serviço,60,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Implantação de guias e sarjetas,Serviço,90,Departamento de Manutenção Viária,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Implantação guias e sarjetas,Serviço,90,Departamento de Manutenção Viária,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Instalação de braço ou luminária,Serviço,120,Departamento de Gerenciamento Administrativo,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Instalação de lixeiras,Serviço,60,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Lavagem de vias públicas,Serviço,3,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza de valas e córregos,Serviço,90,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza de valetas e córregos,Serviço,90,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza e capinação de estradas,Serviço,30,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza e capinação de praças,Serviço,30,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza/manutenção de boca de leão,Serviço,120,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza/manutenção de boca de lobo,Serviço,60,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza/manutenção de bola de lobo,Serviço,60,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza/manutenção de caixa pluvial,Serviço,60,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza/manutenção de galerias,Serviço,60,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Luz acesa durante o dia,Serviço,30,Departamento de Gerenciamento Administrativo,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção braço de iluminação,Serviço,30,Departamento de Gerenciamento Administrativo,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção civil de praças,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção civil de praças,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de bancos de praças,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de braço de iluminação,Serviço,30,Departamento de Gerenciamento Administrativo,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de calçada pública,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de calçadas de praças,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de corrimão de escadaria,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de gradis de córrego,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de gradis de córregos,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de guarda corpo,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de guias e sarjetas,Serviço,90,Departamento de Manutenção Viária,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de jardins e canteiros,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de lixeiras,Serviço,30,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção de próprios públicos,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção ou novas lixeiras,Serviço,30,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Manutenção passarela sobre córrego,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Nivelamento e cascalhamento de via,Serviço,90,Divisão de Conservação das Estradas Rurais e Vicinais,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Pintura de praças,Serviço,60,Departamento de Manutenção de Próprios Públicos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Recapeamento asfáltico,Serviço,60,Divisão de Recapeamento Asfáltico,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Roçada lateral de estrada rural,Serviço,60,Divisão de Conservação das Estradas Rurais e Vicinais,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Tapa buraco,Serviço,60,Divisão de Tapa-Buracos,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Troca de lâmpada,Serviço,5,Departamento de Gerenciamento Administrativo,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Limpeza/capinação de área pública,Serviço,90,Divisão de Fiscalização e Controle da Limpeza Pública,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes
Instalação de poste,Serviço,120,Departamento de Gerenciamento Administrativo,Serviços Urbanos e Zeladoria,Prefeitura Municipal de Mogi das Cruzes"""

class Command(BaseCommand):
    help = 'Importa a hierarquia de categorias (serviços) a partir de um CSV.'

    def handle(self, *args, **options):
        data_lines = DADOS_CSV.strip().splitlines()
        csv_reader = csv.reader(data_lines, delimiter=',')
        
        # Pula a linha do cabeçalho
        next(csv_reader)
        
        self.stdout.write("Iniciando importação de Categorias, Secretarias e Unidades...")
        
        importados = 0
        atualizados = 0
        erros = 0

        for row in csv_reader:
            try:
                nome_categoria, tipo, prazo_str, nome_unidade_adm, nome_secretaria, nome_entidade = row

                # Limpa os dados
                nome_entidade = nome_entidade.strip()
                nome_secretaria = nome_secretaria.strip()
                nome_unidade_adm = nome_unidade_adm.strip()
                nome_categoria = nome_categoria.strip()
                tipo = tipo.strip()

                # Converte o prazo para inteiro, ou None se estiver vazio
                try:
                    prazo = int(prazo_str) if prazo_str else None
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"Prazo inválido '{prazo_str}' para {nome_categoria}. Definindo como nulo."))
                    prazo = None

                # 1. Garante que a Entidade exista
                entidade, ent_created = Entidade.objects.get_or_create(nome=nome_entidade)
                if ent_created:
                    self.stdout.write(f"  > Criada Entidade: {nome_entidade}")

                # 2. Garante que a Secretaria exista e esteja vinculada à Entidade
                secretaria, sec_created = Secretaria.objects.get_or_create(
                    nome=nome_secretaria,
                    defaults={'entidade': entidade}
                )
                if sec_created:
                    self.stdout.write(f"    > Criada Secretaria: {nome_secretaria}")

                # 3. Garante que a Unidade Administrativa exista e esteja vinculada à Secretaria
                unidade_adm, unid_created = UnidadeAdm.objects.get_or_create(
                    nome=nome_unidade_adm,
                    secretaria=secretaria
                )
                if unid_created:
                    self.stdout.write(f"      > Criada Unidade Adm: {nome_unidade_adm}")

                # 4. Cria ou atualiza a Categoria (Serviço)
                # Usamos update_or_create para evitar duplicatas se o script for rodado novamente
                categoria, cat_created = Categoria.objects.update_or_create(
                    nome=nome_categoria,
                    secretaria=secretaria,
                    defaults={
                        'unidade_adm': unidade_adm,
                        'tipo': tipo,
                        'prazo': prazo
                    }
                )
                
                if cat_created:
                    self.stdout.write(self.style.SUCCESS(f"Importada Categoria: {nome_categoria}"))
                    importados += 1
                else:
                    atualizados += 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Erro ao importar linha {row}: {e}"))
                erros += 1

        self.stdout.write(self.style.SUCCESS(f"\nImportação concluída!"))
        self.stdout.write(f"Novas categorias importadas: {importados}")
        self.stdout.write(f"Categorias atualizadas: {atualizados}")
        self.stdout.write(f"Erros: {erros}")