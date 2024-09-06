import os
import time
import yaml
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error
import numpy as np
import logging

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

# Classe de monitoramento das métricas
class MetricsMonitor:
    def __init__(self, y_true, y_pred):
        self.y_true = y_true
        self.y_pred = y_pred
    
    def calculate_metrics(self):
        # Considera apenas o último registro
        y_true_last = self.y_true[-1]
        y_pred_last = self.y_pred[-1]
        
        # Calcula as métricas usando apenas o último registro
        rmse = np.sqrt(mean_squared_error([y_true_last], [y_pred_last]))
        mape = round(np.mean(np.abs((np.array([y_true_last]) - np.array([y_pred_last])) / np.array([y_true_last]))) * 100, 2)
        mae = mean_absolute_error([y_true_last], [y_pred_last])
        
        return {'RMSE': rmse, 'MAPE': mape, 'MAE': mae}

# Classe Gold
class Gold_ts:
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

    # Função para fazer a transformação dos dados
    @monitorar_tempo_de_execucao
    def ts_gold(self, spark):   
        # Obter valores de AAAA e MM da configuração
        AAAA = self.config['dates']['AAAA']
        MM = self.config['dates']['MM']
        
        pasta_silver = self.config['directories']['silver_rainfall']  # diretório para ler os dados
        # caminho_silver = f'EXTRACT_YEAR={AAAA}/EXTRACT_MONTH={MM}'
        # pasta_silver = os.path.join(pasta_silver, caminho_silver) 

        df = spark.read.parquet(pasta_silver)
        df.createOrReplaceTempView("rainfall_view")
        transform_data = self.config['queries']['serie_temporal']  # Acessa query no arquivo yaml
        
        df2 = spark.sql(transform_data)  # Faz a limpeza dos dados
        df2.createOrReplaceTempView('df2')

        # Coletar os dados em um Pandas DataFrame
        pdf = df2.toPandas()

        # Transformar a coluna AAAAMM em um formato de data (YYYY-MM)
        pdf['DATA'] = pd.to_datetime(pdf['AAAAMM'].astype(str) + '01', format='%Y%m%d')

        # Definir a coluna DATA como índice
        pdf.set_index('DATA', inplace=True)

        # Garantir que o índice seja datetime e a precipitação seja numeric
        pdf.index = pd.to_datetime(pdf.index, errors='coerce')
        pdf['PRECIPITACAO_MENSAL'] = pd.to_numeric(pdf['PRECIPITACAO_MENSAL'], errors='coerce')

        # Preparar os dados
        pdf = pdf[['PRECIPITACAO_MENSAL']]

        # Ler previsões
        pasta_gold_artifacts = self.config['directories']['gold_ts_rainfall_artifact']  # diretório
        path_predicoes = os.path.join(pasta_gold_artifacts, 'forecast_36_sarima_model_v_062024.csv')
        predictions_df = pd.read_csv(path_predicoes)
        logging.info(f"colunas de predicions_df: {predictions_df}")

        # Transformar a coluna DATA das previsões em datetime
        predictions_df['DATA'] = pd.to_datetime(predictions_df['DATA'], format='%Y-%m-%d')
        predictions_df.set_index('DATA', inplace=True)

        # Preparar o DataFrame de previsões
        predictions_df = predictions_df[['Forecast']]

        # Unir os DataFrames de valores reais e previsões com base na coluna DATA
        combined_df = pdf.merge(predictions_df, on='DATA', how='inner')
        combined_df.dropna(inplace=True)  # Remover entradas com dados faltantes
        logging.info(f"df combinado: {combined_df}")

        # Calcular as métricas
        metrics = self.calculate_metrics(combined_df['PRECIPITACAO_MENSAL'], combined_df['Forecast'])

        # Salvar a série temporal como CSV
        pasta_gold = self.config['directories']['gold_ts_rainfall']  # diretório
        caminho = os.path.join(pasta_gold, 'serie_temporal.csv')   
        pdf.to_csv(caminho, header=True)

        # Retornar o DataFrame combinado e as métricas
        return combined_df, metrics

    def calculate_metrics(self, y_true, y_pred):
        monitor = MetricsMonitor(y_true, y_pred)
        metrics = monitor.calculate_metrics()
        return metrics