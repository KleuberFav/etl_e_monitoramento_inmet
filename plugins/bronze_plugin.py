import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import yaml
import time

def monitorar_tempo_de_execucao(metodo):
    def wrapper(*args, **kwargs):
        inicio = time.time()
        resultado = metodo(*args, **kwargs)
        fim = time.time()
        tempo_decorrido = fim - inicio
        print(f"Tempo de execução de {metodo.__name__}: {tempo_decorrido:.4f} segundos")
        return resultado
    return wrapper

class Bronze:
    def __init__(self, config_path='/opt/airflow/plugins/config.yaml'):
        self.config = self.load_config(config_path)
    
    # Função para carregar as informações do yaml
    def load_config(self, file_path):
        with open(file_path, "r") as file:
            config = yaml.safe_load(file)
        
        # Variáveis de data (M-1)
        config['dates'] = {
            'AAAAMM': '202407',#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%Y%m'),
            'AAAA': '2024',#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%Y'),
            'MM': '07',#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%m'),
            'MM_AAAA': '07-2024'#(datetime.now() - timedelta(days=datetime.now().day)).strftime('%m-%Y')
        }
        
        return config

    # Função para acessar os dados
    @monitorar_tempo_de_execucao
    def download_data(self):
        headers = self.config['headers']
        base_url = self.config['urls']['base_url']
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                r = requests.get(base_url, headers=headers)

                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    pattern = self.config['urls']['file_pattern'].format(AAAA=self.config['dates']['AAAA'])

                    for a in soup.select('.post-preview a'):
                        url = a.get('href')
                        if re.match(pattern, url):
                            return url
                else:
                    print(f"Tentativa {attempt}: Erro ao acessar a página. Código de status {r.status_code}")
            
            except requests.exceptions.RequestException as e:
                print(f"Tentativa {attempt}: Exceção ao acessar a página: {e}")

            if attempt < max_attempts:
                print("Tentando novamente em 5 segundos...")
                time.sleep(5)  # Atraso de 5 segundos antes da próxima tentativa

        print("Erro ao acessar a página ou link não encontrado após 10 tentativas.")
        return None

    # Função para fazer o download e escrever os dados brutos
    @monitorar_tempo_de_execucao
    def download_and_save_file(self, url):
        headers = self.config['headers']
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    bronze_directory = self.config['directories']['bronze']
                    if not os.path.exists(bronze_directory):
                        os.makedirs(bronze_directory)

                    filename = os.path.join(bronze_directory, f"{self.config['dates']['AAAA']}.zip")
                    with open(filename, 'wb') as file:
                        file.write(response.content)
                    print(f'Arquivo salvo como {filename}')
                    return filename
                else:
                    print(f"Tentativa {attempt}: Erro ao baixar o arquivo. Código de status {response.status_code}")

            except requests.exceptions.RequestException as e:
                print(f"Tentativa {attempt}: Exceção ao baixar o arquivo: {e}")

            if attempt < max_attempts:
                print("Tentando novamente em 5 segundos...")
                time.sleep(5)  # Atraso de 5 segundos antes da próxima tentativa

        print("Erro ao baixar o arquivo após 10 tentativas.")
        return None
