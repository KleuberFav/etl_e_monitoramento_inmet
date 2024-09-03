from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.email_operator import EmailOperator
from datetime import datetime, timedelta
import pendulum
import logging
import yaml
import time
import pytz
from bronze_plugin import Bronze
from silver_plugin import Silver
from monitoramento_plugin import Monitoramento
from pyspark.sql import SparkSession

safra = (datetime.now() - timedelta(days=datetime.now().day)).strftime('%Y%m'),
fuso_horario = pytz.timezone('America/Sao_Paulo') 

# Configuração dos argumentos padrão do DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

# Função para carregar a configuração
def load_config(config_path='/opt/airflow/plugins/config.yaml'):
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    return config


# Criação do DAG
dag = DAG(
    'dag_inmet',
    default_args=default_args,
    description='ELT INMET',
    schedule_interval='35 21 25 * *',
    start_date=datetime(2024, 7, 28),
    catchup=False,
    default_view='graph'
)

# Carregar a configuração
config = load_config()
config_path = '/opt/airflow/plugins/config.yaml'

# Instanciando os plugins
bronze = Bronze(config_path=config_path)
silver = Silver(config_path=config_path)
monitoramento = Monitoramento(config_path=config_path)

def task_download_data(**kwargs):
    try:
        # Captura a hora de início
        horario_atual = datetime.now(fuso_horario)
        start_time = horario_atual.strftime("%H:%M:%S")

        # Baixa e salva o arquivo
        url = bronze.download_data()
        filename = bronze.download_and_save_file(url)

        # Captura a hora de término
        horario_atual = datetime.now(fuso_horario)
        end_time = horario_atual.strftime("%H:%M:%S")

        # Armazenar informações de tempo no XCom
        ti = kwargs['ti']
        ti.xcom_push(key='download_start_time', value=start_time)  # Chave ajustada
        ti.xcom_push(key='download_end_time', value=end_time)  # Chave ajustada

        return filename
    except Exception as e:
        logging.error(f"Erro ao baixar e salvar o arquivo: {e}")
        raise

def task_process_data(**kwargs):
    try:
        # Obter o caminho do arquivo baixado do XCom
        ti = kwargs['ti']
        filename = ti.xcom_pull(task_ids='download_data')

        # Captura a hora de início
        horario_atual = datetime.now(fuso_horario)
        start_time = horario_atual.strftime("%H:%M:%S")

        # Iniciar a sessão Spark aqui
        spark = (
            SparkSession.builder.appName("process_data")
            .config("spark.driver.memory", "16g")
            .config("spark.executor.memory", "16g")
            .config("spark.sql.session.timeZone", "America/Sao_Paulo")
            .config("spark.executor.cores", "4")
            .config("spark.default.parallelism", "100")
            .config("spark.sql.shuffle.partitions", "200")
            .config("spark.task.cpus", "1")
            .getOrCreate()
        )

        logging.info("SparkSession criado com sucesso.")
        
        # Processar o arquivo CSV
        silver.process_csv_files(filename, spark)
        logging.info("Processamento concluído com sucesso.")

        # Captura a hora de término
        horario_atual = datetime.now(fuso_horario)
        end_time = horario_atual.strftime("%H:%M:%S")

        # Armazenar informações de tempo no XCom
        ti.xcom_push(key='process_start_time', value=start_time)  # Chave ajustada
        ti.xcom_push(key='process_end_time', value=end_time)  # Chave ajustada

    except Exception as e:
        logging.error(f"Erro no processamento dos dados: {e}")
        raise
    finally:
        # Parar a sessão Spark
        spark.stop()

def task_monitoramento(**kwargs):
    try:
        # Captura a hora de início
        horario_atual = datetime.now(fuso_horario)
        start_time = horario_atual.strftime("%H:%M:%S")

        # Iniciar a sessão Spark aqui
        spark = (
            SparkSession.builder.appName("monitoramento")
            .config("spark.driver.memory", "16g")
            .config("spark.executor.memory", "16g")
            .config("spark.sql.session.timeZone", "America/Sao_Paulo")
            .config("spark.executor.cores", "4")
            .config("spark.default.parallelism", "100")
            .config("spark.sql.shuffle.partitions", "200")
            .config("spark.task.cpus", "1")
            .getOrCreate()
        )

        logging.info("SparkSession criado com sucesso.")
        
        # Executar o monitoramento
        results = monitoramento.execute_monitoramento(regiao=['REGIAO'], uf=['UF'], colunas=['UF', 'ESTACAO'], spark=spark)

        # Captura a hora de término
        horario_atual = datetime.now(fuso_horario)
        end_time = horario_atual.strftime("%H:%M:%S")

        # Armazenar informações de tempo no XCom
        ti = kwargs['ti']
        ti.xcom_push(key='monitoramento_start_time', value=start_time)  # Chave ajustada
        ti.xcom_push(key='monitoramento_end_time', value=end_time)  # Chave ajustada

        # Retornar os resultados para o XCom
        return results
    except Exception as e:
        logging.error(f"Erro no monitoramento: {e}")
        raise
    finally:
        # Parar a sessão Spark
        spark.stop()

# Definição das tarefas

# tarefa de download e load
download_data_task = PythonOperator(
    task_id='download_data',
    python_callable=task_download_data,
    provide_context=True,
    dag=dag,
)

# tarefa de processamento dos dados
process_data_task = PythonOperator(
    task_id='process_data',
    python_callable=task_process_data,
    provide_context=True,
    dag=dag,
)

# tarefa de monitoramento da safra
monitoramento_task = PythonOperator(
    task_id='monitoramento_task',
    python_callable=task_monitoramento,
    provide_context=True,
    dag=dag,
)

# tarefa de envio de email em caso de falha
send_email_alert = EmailOperator(
    task_id='send_email_alert',
    to=['kleuber94@gmail.com','vferreiramesquita@gmail.com'],
    subject='Airflow Alert',
    html_content='''
    <h3>Alerta de ELT do INMET com erro. </h3>
    <p> Dag: inmet </p>
    ''',
    dag=dag,
    trigger_rule='one_failed',
)

# Tarefa de envio de email com as informações da safra
send_email_results_task = EmailOperator(
    task_id='send_email_results',  # Nome diferente e único
    to=['seuemail@email.com'],
    subject=f'Airflow Advise - INMET safra: {safra}',
    html_content='''<h3>ELT do INMET realizado com sucesso</h3>
        <p>Dag: inmet</p>
        <ul>
            <li>Região: {{ task_instance.xcom_pull(task_ids='monitoramento_task')['qtd_regiao'] }}</li>
            <li>UF: {{ task_instance.xcom_pull(task_ids='monitoramento_task')['qtd_uf'] }}</li>
            <li>Volumetria da Safra: {{ task_instance.xcom_pull(task_ids='monitoramento_task')['vol_safra'] }}</li>
            <li>Volumetria Esperada: {{ task_instance.xcom_pull(task_ids='monitoramento_task')['vol_esperada'] }}</li>
            <li>Quantidade de Estações: {{ task_instance.xcom_pull(task_ids='monitoramento_task')['qtd_estacao'] }}</li>
            <li>Horário do início do ETL: {{ task_instance.xcom_pull(task_ids='download_data', key='download_start_time') }}</li>
            <li>Horário do insert na camada bronze: {{ task_instance.xcom_pull(task_ids='download_data', key='download_end_time') }}</li>
            <li>Horário do Fim do ETL: {{ task_instance.xcom_pull(task_ids='process_data', key='process_end_time') }}</li> <!-- Corrigido -->
        </ul>
    ''',
    trigger_rule='none_failed',
    dag=dag
)

# Definindo a ordem de execução das tarefas
download_data_task >> process_data_task >> monitoramento_task >> [send_email_alert, send_email_results_task]
