from airflow.operators.email_operator import EmailOperator
from airflow.operators.python_operator import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow import DAG
from datetime import datetime, timedelta
import pendulum
from pyspark.sql import SparkSession
import yaml
import pandas as pd
from gold_ts_plugin import Gold_ts

AAAAMM = (datetime.now() - timedelta(days=datetime.now().day)).strftime('%Y%m')

# Função para carregar a configuração
def load_config(config_path='/opt/airflow/plugins/config.yaml'):
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    return config

# Função para criar a sessão Spark
def create_spark_session():
    return SparkSession.builder \
        .appName("time_series") \
        .config("spark.driver.memory", "16g") \
        .config("spark.executor.memory", "16g") \
        .config("spark.sql.session.timeZone", "America/Sao_Paulo") \
        .config("spark.executor.cores", "4") \
        .config("spark.default.parallelism", "100") \
        .config("spark.sql.shuffle.partitions", "200") \
        .config("spark.task.cpus", "1") \
        .getOrCreate()

# Função que executa o processamento do Gold_ts e calcula as métricas
def run_gold_ts_and_calculate_metrics(**kwargs):
    config_path = '/opt/airflow/plugins/config.yaml'
    gold_ts = Gold_ts(config_path=config_path)
    spark = create_spark_session()
    
    # Executar o processamento e obter combined_df e métricas
    combined_df, metrics = gold_ts.ts_gold(spark)
    spark.stop()
    
    # Passar as métricas para o XCom
    ti = kwargs['ti']
    ti.xcom_push(key='metrics', value=metrics)

# Função para criar a DAG
dag = DAG(
    'dag_gold_ts',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='Processamento de dados com o plugin Gold_ts',
    schedule_interval='00 22 25 * *',
    start_date=datetime(2024, 7, 28),
    catchup=False,
    default_view='graph'
)

# Tarefa para executar o plugin Gold_ts e calcular as métricas
process_gold_ts_and_metrics = PythonOperator(
    task_id='process_gold_ts_and_metrics',
    python_callable=run_gold_ts_and_calculate_metrics,
    provide_context=True,
    dag=dag
)

# Tarefa para enviar email de alerta em caso de falha
send_email_alert = EmailOperator(
    task_id='send_email_alert',
    to=['seuemail@email.com'],
    subject='Airflow Alert',
    html_content='''
    <h3>Alerta de ELT de Times Series do INMET com erro.</h3>
    <p>Dag: inmet</p>
    ''',
    trigger_rule='one_failed',
    dag=dag
)

# Tarefa para enviar email com resultados em caso de sucesso
send_email_results_task = EmailOperator(
    task_id='send_email_results',
    to=['seuemail@email.com'],
    subject=f'Airflow Advise - INMET - Gold Times Series safra: - {AAAAMM}',
    html_content='''
    <h3>ELT de Time Series do INMET realizado com sucesso</h3>
    <p>Dag: inmet</p>
    <ul>
        <li>RMSE: {{ task_instance.xcom_pull(task_ids='process_gold_ts_and_metrics', key='metrics')['RMSE'] }}</li>
        <li>MAPE: {{ task_instance.xcom_pull(task_ids='process_gold_ts_and_metrics', key='metrics')['MAPE'] }}%</li>
        <li>MAE: {{ task_instance.xcom_pull(task_ids='process_gold_ts_and_metrics', key='metrics')['MAE'] }}</li>
    </ul>
    ''',
    trigger_rule='none_failed',
    dag=dag
)

# Definindo a ordem de execução das tarefas
process_gold_ts_and_metrics >> [send_email_results_task, send_email_alert]
