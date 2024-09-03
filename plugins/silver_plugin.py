import os
import zipfile
import tempfile
import chardet
import time
import yaml
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, regexp_replace, lit, concat, substring
import logging
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from dateutil.relativedelta import relativedelta

# Função para monitorar o tempo de execução
def monitorar_tempo_de_execucao(metodo):
    def wrapper(*args, **kwargs):
        inicio = time.time()
        resultado = metodo(*args, **kwargs)
        fim = time.time()
        tempo_decorrido = fim - inicio
        print(f"Tempo de execução de {metodo.__name__}: {tempo_decorrido:.4f} segundos")
        return resultado
    return wrapper

# Classe Silver
class Silver:
    def __init__(self, config_path='config.yaml'):
        self.config = self.load_config(config_path)
    
    # Função para carregar as informações do yaml
    def load_config(self, file_path):
        with open(file_path, "r") as file:
            config = yaml.safe_load(file)
        
        today = datetime.now()
        last_month = today - timedelta(days=today.day)
        
        # Variáveis de data (M-1)
        config['dates'] = {
            'AAAAMM': '202407',#last_month.strftime('%Y%m'),
            'AAAA': '2024',#last_month.strftime('%Y'),
            'MM': '07',#last_month.strftime('%m'),
            'MM_AAAA': '07-2024'#last_month.strftime('%m-%Y')
        }
        
        if 'dates' not in config or 'AAAAMM' not in config['dates']:
            raise ValueError("Configuração 'dates' ou 'AAAAMM' não encontrada")
        
        return config

    # Função para extrair dados zipados
    def extract_zip(self, zip_path, extract_to):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    # Função para detectar o encoding do arquivo
    def detect_encoding(self, file_path):
        with open(file_path, 'rb') as f:
            return chardet.detect(f.read())['encoding']

    # Função para detectar e fazer algumas transformações em um arquuvo csv
    def process_csv_file(self, tmp_dir, nome_arquivo_zip, spark):
        file_path = os.path.join(tmp_dir, nome_arquivo_zip)
        encoding = self.detect_encoding(file_path)

        # Processa as primeiras linhas para obter metadados
        with open(file_path, 'r', encoding=encoding) as f:
            lines = f.readlines()[:8]
            data_lines = [line.strip().split(';') for line in lines]
            resultado = [line[1].replace(',', '.') for line in data_lines]
        
        # Processa o restante do CSV
        with open(file_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
            nona_linha = lines[8]
            nona_linha = (nona_linha.replace('MAX.NA', 'MAX NA')
                                .replace('MIN. ', 'MIN')
                                .replace('Ã', 'A')
                                .replace('ANT.', 'ANT')
                                .replace('MAX.', 'MAX')
                                .replace('REL.', 'REL')
                                .replace('MAX.NA', 'MAX NA')
                                .replace('MIN. NA', 'MIN NA'))
            outras_linhas = lines[9:]
            outras_linhas = [linha.replace(',', '.') for linha in outras_linhas]
            data = nona_linha + ''.join(outras_linhas)

        # Cria um arquivo CSV temporário para leitura pelo Spark
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding=encoding, dir=tmp_dir) as arquivo_csv:
            arquivo_csv.write(data)
            arquivo_csv_path = arquivo_csv.name
        
        # Lê o CSV usando PySpark
        df = spark.read.csv(arquivo_csv_path, header=True, sep=';', encoding=encoding)
        
        # Renomeia colunas
        df = df.withColumnRenamed('Data', 'DATA (YYYY-MM-DD)') \
               .withColumnRenamed('Hora UTC', 'HORA (UTC)') \
               .withColumnRenamed('RADIACAO GLOBAL (Kj/m²)', 'RADIACAO GLOBAL (KJ/m²)')

        # Aplica transformações nas colunas
        df = df.withColumn('DATA (YYYY-MM-DD)', regexp_replace(col('DATA (YYYY-MM-DD)'), r'/', '-'))
        
        df = df.withColumn('AAAAMM', concat(substring(col('DATA (YYYY-MM-DD)'), 1, 4), substring(col('DATA (YYYY-MM-DD)'), 6, 2))) \
            .withColumn('year_month', substring(col('DATA (YYYY-MM-DD)'), 1, 7)) \
            .drop("_c19")
        
        # Adiciona informações do arquivo CSV aos dados
        df = df.withColumn('REGIÃO', lit(resultado[0]))
        df = df.withColumn('UF', lit(resultado[1]))
        df = df.withColumn('ESTACAO', lit(resultado[2]))
        df = df.withColumn('CODIGO', lit(resultado[3]))
        df = df.withColumn('LATITUDE', lit(resultado[4]))
        df = df.withColumn('LONGITUDE', lit(resultado[5]))
        df = df.withColumn('ALTITUDE', lit(resultado[6]))
        df = df.withColumn('DATA_FUNDACAO', lit(resultado[7]))
        df = df.withColumn('DATA_FUNDACAO', regexp_replace(col('DATA_FUNDACAO'), r'/', '-'))

        # Filtra os dados de acordo com a configuração
        df_filtered = df.filter(col('AAAAMM') == self.config['dates']['AAAAMM'])
        
        return df_filtered

    # Função principal para fazer a transformação dos dados
    @monitorar_tempo_de_execucao
    def process_csv_files(self, zip_file_path, spark):
        with tempfile.TemporaryDirectory() as tmp_dir: 
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                for nome_arquivo_zip in zip_ref.namelist():
                    if nome_arquivo_zip.endswith('.CSV'): # Percorre o diretório e seleciona os arquivos do tipo csv
                        zip_ref.extract(nome_arquivo_zip, tmp_dir) # Extrai os arquivos
                        print(f"Arquivo CSV encontrado: {nome_arquivo_zip}")
                        df = self.process_csv_file(tmp_dir, nome_arquivo_zip, spark) # Faz as primeiras transformações no arquivo
                        df.createOrReplaceTempView('df') # Registra uma tabela temporaria no spark
                        # logging.info(f"dataframe = {df}")
                        
                        clean_data_query = self.config['queries']['clean_data'] # Acessa query no arquivo yaml
                        transform_data_query = self.config['queries']['transform_data'] # Acessa query no arquivo yaml
                        
                        df2 = spark.sql(clean_data_query) # Faz a limpeza dos dados
                        df2.createOrReplaceTempView('df2')
                        
                        df3 = spark.sql(transform_data_query) # Renomeia e transforma dados
                        df3.createOrReplaceTempView('df3')
                        
                        pasta_silver = self.config['directories']['silver_rainfall'] # diretório para salvar
                        unique_year_months = df3.select('year_month').distinct().orderBy('year_month').collect() # Selecionando valores distintos de safra
                        for row in unique_year_months:
                            year_month = row['year_month'] 
                            year, month = year_month.split('-')
                            df_filtered = df3.filter(col('year_month') == year_month) # Selecionando apenas a safra atual
                            parquet_dir = os.path.join(pasta_silver, f"EXTRACT_YEAR={year}", f"EXTRACT_MONTH={month}") # Padrão de escrita 
                            print(f"Escrevendo Safra {year_month}")
                            df_filtered.write.mode("append").parquet(parquet_dir) # Escrevendo os arquivos por ano e mês
                    else:
                        print(f'O arquivo {nome_arquivo_zip} não é um arquivo CSV válido para o período atual. Ignorando...')
                        continue