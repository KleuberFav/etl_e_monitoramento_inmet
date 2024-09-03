# Use a base image from Apache Airflow
FROM apache/airflow:2.5.1

# Instale Java
USER root
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Configure JAVA_HOME
ENV JAVA_HOME /usr/lib/jvm/java-11-openjdk-amd64
ENV PATH $JAVA_HOME/bin:$PATH

# Voltar para o usuário airflow
USER airflow

# Copie o arquivo de requisitos para o container
COPY requirements.txt .

# Instale as dependências adicionais do pip
RUN pip install --no-cache-dir -r requirements.txt

# Copie os plugins customizados para o diretório de plugins do Airflow
COPY plugins /opt/airflow/plugins

# Copie os DAGs para o diretório de DAGs do Airflow
COPY dags /opt/airflow/dags

# Ajuste permissões dos diretórios para o usuário airflow
USER root
RUN chmod -R 777 /opt/airflow/plugins /opt/airflow/dags
USER airflow
