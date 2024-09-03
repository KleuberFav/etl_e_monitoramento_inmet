import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import yaml
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging

class Monitoramento:
    def __init__(self, config_path='config.yaml'):
        self.config = self.load_config(config_path)

    # Função para carregar as informações do yaml
    def load_config(self, file_path):
        with open(file_path, "r") as file:
            config = yaml.safe_load(file)
        
        # Variáveis de data (M-1)
        config['dates'] = {
            'AAAAMM': '202407',#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%Y%m'),
            'AAAA': '2024',#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%Y'),
            'MM_AAAA': '07-2024'#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%m-%Y')
        }
        
        return config

    # Função para calcular a volumetria da Safra
    def volumetria_safra(self, df, spark):
        df.createOrReplaceTempView("temp_df")
        query = """
            SELECT 
                COUNT(*) AS VOLUMETRIA
            FROM temp_df
        """
        resultado = spark.sql(query)
        return resultado.collect()[0]['VOLUMETRIA']

    # Função genérica para calcular a contagem distinta de uma ou mais colunas
    def contagem_distinta(self, df, colunas, spark):
        df.createOrReplaceTempView("temp_df")
        colunas_sql = ', '.join(colunas)
        query = f"""
            SELECT 
                COUNT(DISTINCT {colunas_sql}) AS DISTINTAS
            FROM temp_df
        """
        resultado = spark.sql(query)
        return resultado.collect()[0]['DISTINTAS']

    # função para calcular a Volumetria Esperada da Safra
    def calcular_volumetria_esperada(self, AAAAMM, qtd_estacoes):
        data_safra = pd.to_datetime(AAAAMM, format='%Y%m')
        dias_no_mes = data_safra.days_in_month

        if dias_no_mes in [28, 29, 30, 31]:
            volumetria_esperada = 24 * dias_no_mes * qtd_estacoes
        else:
            volumetria_esperada = "Data inválida"

        return volumetria_esperada

    # Função para ler um arquivo parquet
    def ler_dataframe_parquet(self, spark, pasta):
        df = spark.read.parquet(pasta)
        return df

    # Função para encontrar novas estações de acordo com a safra anterior
    def encontrar_novas_estacoes(self, safra_atual, safra_anterior):
        estacoes_safra_atual = set(row['ESTACAO'] for row in safra_atual.select('ESTACAO').distinct().collect())
        estacoes_safra_anterior = set(row['ESTACAO'] for row in safra_anterior.select('ESTACAO').distinct().collect())
        estacoes_novas = estacoes_safra_atual - estacoes_safra_anterior
        estacoes_desativadas = estacoes_safra_anterior - estacoes_safra_atual

        return list(estacoes_novas), list(estacoes_desativadas)

    # Função para criar um dataframe com os dados de Monitoramento
    def criar_dataframe_monitoramento(self, AAAAMM, vol_safra, vol_esperada, qtd_estacao):
        data = {
            'Safra': [AAAAMM],
            'Volumetria_Safra': [vol_safra],
            'Volumetria_Esperada': [vol_esperada],
            'Quantidade_Estacao': [qtd_estacao]
        }
        df_monitoramento = pd.DataFrame(data)
        return df_monitoramento

    # Função para salvar os dados de um dataframe em csv
    def salvar_dataframe_em_csv(self, df, diretorio, nome_arquivo_csv):
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)
        caminho_arquivo = os.path.join(diretorio, nome_arquivo_csv)
        if os.path.isfile(caminho_arquivo):
            df.to_csv(caminho_arquivo, mode='a', index=False, header=False)
        else:
            df.to_csv(caminho_arquivo, index=False)

    # Função para ler os dados de um csv
    def ler_csv(self, diretorio, nome_arquivo_csv):
        caminho_arquivo = os.path.join(diretorio, nome_arquivo_csv)
        try:
            df = pd.read_csv(caminho_arquivo)
            return df
        except FileNotFoundError:
            logging.info(f"O arquivo {caminho_arquivo} não foi encontrado.")
            return None
        except Exception as e:
            logging.info(f"Ocorreu um erro ao ler o arquivo CSV: {e}")
            return None

    # Função para criar um gráfico de linhas 
    def plot_line_graph(self, diretorio, df, x_col, y_col, title=None, xlabel=None, ylabel=None):
        df[x_col] = df[x_col].astype(str)
        plt.figure(figsize=(10, 6))
        plt.plot(df[x_col], df[y_col], marker='o', linestyle='-')
        if title:
            plt.title(title)
        if xlabel:
            plt.xlabel(xlabel)
        if ylabel:
            plt.ylabel(ylabel)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f'{diretorio}/monitoramento_estacoes_{x_col}.png')

    # Função para criar um gráfico de colunas
    def plot_column_graph(self, diretorio, df, x_col, y_cols, title=None, xlabel=None, ylabel=None):
        df[x_col] = df[x_col].astype(str)
        x = np.arange(len(df[x_col]))
        width = 0.35

        fig, ax = plt.subplots(figsize=(10, 6))
        for i, y_col in enumerate(y_cols):
            ax.bar(x + i * width, df[y_col], width, label=y_col)
        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.set_xticks(x + width / 2 * (len(y_cols) - 1))
        ax.set_xticklabels(df[x_col])
        ax.grid(True, axis='y')
        ax.legend(loc='lower left')
        for i in range(len(df)):
            for j, y_col in enumerate(y_cols):
                ax.annotate(
                    str(df[y_col].iloc[i]), 
                    (x[i] + j * width, df[y_col].iloc[i]),
                    textcoords="offset points",
                    xytext=(0, 5),
                    ha='center'
                )
        plt.tight_layout()
        plt.savefig(f'{diretorio}/monitoramento_volumetria_{x_col}.png')

    # Função principal para executar o monitoramento
    def execute_monitoramento(self, regiao, uf, colunas, spark):
        config = self.config
        AAAAMM = config['dates']['AAAAMM']
        AAAA = config['dates']['AAAA']
        #pasta_atual = config['directories']['silver_rainfall'] + f"/EXTRACT_YEAR={(datetime.now() - relativedelta(months=2)).strftime('%Y')}" + f"/EXTRACT_MONTH={(datetime.now() - relativedelta(months=1)).strftime('%m')}"
        # pasta_anterior = config['directories']['silver_rainfall'] + f"/EXTRACT_YEAR={(datetime.now() - relativedelta(months=2)).strftime('%Y')}" + f"/EXTRACT_MONTH={(datetime.now() - relativedelta(months=2)).strftime('%m')}"
        pasta_atual = config['directories']['silver_rainfall'] + f"/EXTRACT_YEAR={AAAA}/EXTRACT_MONTH=07"
        # pasta_anterior = config['directories']['silver_rainfall'] + f"/EXTRACT_YEAR={AAAA}/EXTRACT_MONTH=02"
        df_safra_atual = self.ler_dataframe_parquet(spark, pasta_atual)
        # df_safra_anterior = self.ler_dataframe_parquet(spark, pasta_anterior)
        vol_safra = self.volumetria_safra(df_safra_atual, spark)
        qtd_estacao = self.contagem_distinta(df_safra_atual, colunas, spark)
        # qtd_estacao_ant = self.contagem_distinta(df_safra_anterior, colunas, spark)
        qtd_regiao = self.contagem_distinta(df_safra_atual, regiao, spark)
        qtd_uf = self.contagem_distinta(df_safra_atual, uf, spark)
        vol_esperada = self.calcular_volumetria_esperada(AAAAMM, qtd_estacao)
        logging.info(f"Volumetria da Safra Atual: {vol_safra}")
        logging.info(f"Volumetria Esperada da Safra Atual: {vol_esperada}")
        logging.info(f"Quantidade de Estações Monitoradas da Safra Atual: {qtd_estacao}")
        # logging.info(f"Quantidade de Estações Monitoradas da Safra Anterior: {qtd_estacao_ant}")
        logging.info(f"Quantidade de Regiões Monitoradas da Safra Atual: {qtd_regiao}")
        logging.info(f"Quantidade de UF Monitoradas da Safra Atual: {qtd_uf}")
        # estacoes_novas, estacoes_desativadas = self.encontrar_novas_estacoes(df_safra_atual, df_safra_anterior)
        # logging.info(f"Estações Novas: {estacoes_novas}")
        # logging.info(f"Estações Desativadas: {estacoes_desativadas}")
        # df_monitoramento = self.criar_dataframe_monitoramento(AAAAMM, vol_safra, vol_esperada, qtd_estacao)
        # self.salvar_dataframe_em_csv(df_monitoramento, config['directories']['monitoramento'], "monitoramento_rainfall.csv")
        # df_monit = self.ler_csv(config['directories']['monitoramento'], "monitoramento_rainfall.csv")

        # self.plot_line_graph(config['directories']['monitoramento'], df_monit, 'Safra', 'Quantidade_Estacao', title=f"Quantidade de Estações da Safra {AAAAMM}", xlabel="AAAAMM", ylabel="Volumetria")
        # self.plot_column_graph(config['directories']['monitoramento'], df_monit, 'Safra', ['Volumetria_Safra', 'Volumetria_Esperada'], title=f"Volumetria da Safra e Volumetria Esperada {AAAAMM}", xlabel="AAAAMM", ylabel="Volumetria")
        return {
            'vol_safra': vol_safra,
            'vol_esperada': vol_esperada,
            'qtd_estacao': qtd_estacao,
            'qtd_regiao': qtd_regiao,
            'qtd_uf': qtd_uf
        }