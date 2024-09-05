# Projeto de Extração de Dados Meteorológicos do INMET gerenciados pelo Airflow

Repositório com códigos para extração, tratamento e carga de dados meteorológicos do INMET em um LakeHouse

## Índice
- [Sobre](#sobre)
- [Dados](#dados)
- [Instalação](#instalação)
- [Autor](#autor)


## Sobre

Este projeto foi desenvolvido para automatizar a extração dos dados meteorológicos do INMET e carregar as informações nas suas devidas camadas no LakeHouse (Bronze, Silver e Gold). 
Todas as querys, repositórios e URL's estão no arquivo [config.yaml](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/plugins/config.yaml).

### Fonte dos Dados

A fonte dos dados está no site do [INMET](https://portal.inmet.gov.br/dadoshistoricos). Os dados estão armazenados em arquivos CSV separados por estação meteorológica e organizados em pastas, onde cada pasta corresponde a um ano. A extração desses dados é compactada em arquivos `.zip`.

### Estrutura do Projeto

- **Bronze**: Camada de dados brutos.
- **Silver**: Camada de dados limpos e transformados.
- **Gold**: Camada de dados agregados e prontos para análise.

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/arquitetura_lakehouse.png?raw=true" width="3000"/>


### Gerenciamento de Processos com Airflow

O Airflow foi utilizado para fazer o gerenciamento dos processos de ETL (Extração, Transformação e Carga). Foram criadas duas DAGs:

### DAGs

#### 1. [dag_inmet](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/dags/dag_inmet.py)

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/dag_inmet.png?raw=true" width="1000"/>

Esta DAG foi utilizada para gerenciar o fluxo de trabalho no Lake, incluindo:

- **Extração e Ingestão na Camada Bronze**:
  - A extração dos dados brutos é feita diretamente do site do INMET e os dados são carregados na camada bronze ainda compactados. 
  - Plugin usado: [bronze_plugin](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/plugins/bronze_plugin.py).

- **Limpeza, Transformação e Carga na Camada Silver**:
  - Os arquivos são descompactados e tratados, removendo as primeiras 8 linhas que não estão em um formato adequado.
  - Após a limpeza inicial, os dados são transformados usando PySpark.
  - Plugin usado: [silver_plugin](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/plugins/silver_plugin.py).

- **Monitoramento dos Dados e do Processo**:
  - Monitoramento da quantidade de regiões, de estações e de UF das safras.
  - Verificação da volumetria da safra e da volumetria esperada.
  - Registro dos horários de início do processo, de ingestão na camada bronze, e de ingestão na camada silver.
  - Plugin usado: [monitoramento_plugin](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/plugins/monitoramento_plugin.py).

- **Notificações**:
  - Se o processo for realizado com sucesso, todas as informações relevantes são enviadas por email. 
  - Em caso de erro, um email de alerta é enviado.

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/etl_sucesso.png?raw=true" width="500"/>

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/alert_etl_erro.png?raw=true" width="500"/>

#### 2. [dag_ts_inmet](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/dags/dag_ts_inmet.py)

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/dag_gold_ts.png?raw=true" width="1000"/>

Esta DAG foi utilizada para gerenciar a ingestão na camada Gold. Nesse caso, a camada gold é uma tabela contendo os registros históricos mensais de precipitação em ml, na estação de Belém-PA. Inclui:

- **Agregação dos dados**:
  - A agregação dos dados é feita usando a soma da precipitação, agrupando por safra, onde UF="PA" e Estação = "BElÉM"
  - O valor da precipitação mensal é adicionada em um arquivo que tem a série temporal completa
  - É feita o cálculo das métricas (RMSE, MAPE e MAE), comparando os dados previstos para essa safra com a precipitação mensal calculada.
  - Obs: A obtenção dos dados previstos foi feita em outro projeto, usando o mesmo LakeHouse, a partir de um modelo de séries temporais do tipo SARIMA
  - Plugin usado: [gold_ts_plugin](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/plugins/gold_ts_plugin.py).

- **Notificações**:
  - Se o processo for realizado com sucesso, todas as métricas são enviadas por email.
  - Em caso de erro, um email de alerta é enviado.

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/ts_sucesso.png?raw=true" width="1000"/>

<img src="https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/artefatos/ts_erro.png?raw=true" width="1000"/>

## Dados

Os dados meteorológicos extraídos do INMET são transformados e armazenados na camada Silver do Lake. A seguir estão as colunas utilizadas no processo de transformação:

# Tabela Comparativa: Metadados Bronze e Silver

| Coluna Bronze                                            | Tipo Bronze   | Descrição Bronze                                                   | Coluna Silver                    | Tipo Silver   | Descrição Silver                                                         |
|----------------------------------------------------------|---------------|--------------------------------------------------------------------|----------------------------------|---------------|-------------------------------------------------------------------------|
| YYYY-MM-DD                                               | date          | Data em formato YYYY-MM-DD                                         | DATE_YYYYMMDD                    | string          | Data em formato YYYY-MM-DD                                              |
| HORA (UTC)                                               | string        | Hora no formato UTC                                                | HORA                             | string        | Hora no formato UTC                                                     |
| REGIÃO                                                   | string        | Região da estação monitorada                                       | N/A                              | N/A           | N/A                                                                     |
| UF                                                       | string        | UF da estação monitorada                                           | UF                                | string        | UF da estação monitorada                                                |
| ESTACAO                                                  | string        | Estação monitorada                                                 | ESTACAO                          | string        | Estação monitorada                                                      |
| CODIGO                                                   | string        | Código da estação monitorada                                       | CODIGO                           | string        | Código da estação monitorada                                            |
| DATA_FUNDACAO                                            | string        | Data de fundação da estação monitorada                             | DATA_FUNDACAO                    | string        | Data de fundação da estação monitorada                                  |
| LATITUDE                                                 | string       | Latitude da Estação monitorada                                     | LATITUDE                         | decimal       | Latitude da Estação monitorada                                          |
| LONGITUDE                                                | string       | Longitude da Estação monitorada                                    | LONGITUDE                        | decimal       | Longitude da Estação monitorada                                         |
| ALTITUDE                                                 | string       | Altitude em metros da Estação monitorada                           | ALTITUDE                         | decimal       | Altitude em metros da Estação monitorada                                |
| PRECIPITAÇAO TOTAL, HORÁRIO (mm)                         | string       | Precipitação total no horário em milímetros                        | PRECIPITACAO                     | decimal       | Precipitação total no horário em milímetros                             |
| PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)    | string       | Pressão Atmosférica ao nível da estação                            | PA_ESTACAO                       | decimal       | Pressão Atmosférica ao nível da estação                                 |
| PRESSAO ATMOSFERICA MAX NA HORA ANT (AUT) (mB)           | string       | Pressão Atmosférica máxima na hora anterior ao nível da estação    | PA_MAX_ANT                       | decimal       | Pressão Atmosférica máxima na hora anterior ao nível da estação         |
| PRESSAO ATMOSFERICA MINNA HORA ANT (AUT) (mB)            | string       | Pressão Atmosférica mínima na hora anterior ao nível da estação    | PA_MIN_ANT                       | decimal       | Pressão Atmosférica mínima na hora anterior ao nível da estação         |
| RADIACAO GLOBAL (KJ/m²)                                  | string       | Radiação global em KJ/m²                                           | RADIACAO_GLOBAL                  | decimal       | Radiação global em KJ/m²                                                |
| TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)             | string       | Temperatura do ar no horário - Bulbo seco °C                       | TEMPERATURA_AR                   | decimal       | Temperatura do ar no horário - Bulbo seco °C                            |
| TEMPERATURA DO PONTO DE ORVALHO (°C)                     | string       | Temperatura do ar no horário - Orvalho °C                          | TEMPERATURA_ORVALHO              | decimal       | Temperatura do ar no horário - Orvalho °C                               |
| TEMPERATURA MÁXIMA NA HORA ANT (AUT) (°C)                | string       | Temperatura máxima do ar na hora anterior - Bulbo seco °C          | TEMPERATURA_MAX_ANT              | decimal       | Temperatura máxima do ar na hora anterior - Bulbo seco °C               |
| TEMPERATURA MÍNIMA NA HORA ANT (AUT) (°C)                | string       | Temperatura mínima do ar na hora anterior - Bulbo seco °C          | TEMPERATURA_MIN_ANT              | decimal       | Temperatura mínima do ar na hora anterior - Bulbo seco °C               |
| TEMPERATURA ORVALHO MAX NA HORA ANT (AUT) (°C)           | string       | Temperatura máxima do ar na hora anterior - Orvalho °C             | TEMPERATURA_MAX_ORVALHO_ANT      | decimal       | Temperatura máxima do ar na hora anterior - Orvalho °C                  |
| TEMPERATURA ORVALHO MINNA HORA ANT (AUT) (°C)            | string       | Temperatura mínima do ar na hora anterior - Orvalho °C             | TEMPERATURA_MIN_ORVALHO_ANT      | decimal       | Temperatura mínima do ar na hora anterior - Orvalho °C                  |
| UMIDADE REL MAX NA HORA ANT (AUT) (%)                    | string       | Umidade relativa do ar máxima na hora anterior                     | UMIDADE_REL_MAX_ANT              | decimal       | Umidade relativa do ar máxima na hora anterior                          |
| UMIDADE REL MINNA HORA ANT (AUT) (%)                     | string       | Umidade relativa do ar mínima na hora anterior                     | UMIDADE_REL_MIN_ANT              | decimal       | Umidade relativa do ar mínima na hora anterior                          |
| UMIDADE RELATIVA DO AR, HORARIA (%)                      | string       | Umidade relativa do ar mínima no horário                           | UMIDADE_REL_AR                   | decimal       | Umidade relativa do ar mínima no horário                                |
| VENTO, DIREÇAO HORARIA (gr) (° (gr))                     | string       | Direção do Vento no horário                                        | VENTO_DIRECAO_HORARIA            | decimal       | Direção do Vento no horário                                             |
| VENTO, RAJADA MAXIMA (m/s)                               | string       | Rajada máxima do vento no horário - m/s                            | VENTO_RAJADA_MAX                 | decimal       | Rajada máxima do vento no horário - m/s                                 |
| VENTO, VELOCIDADE HORARIA (m/s)` IS NULL OR `VENTO, VELOCIDADE HORARIA (m/s) | decimal | Velocidade máxima do vento no horário - m/s                       | VENTO_VELOCIDADE_HORARIA         | decimal       | Velocidade máxima do vento no horário - m/s                             |
| N/A                                                      | N/A           | N/A                                                                | PK_RAINFALL                      | string        | Chave Primária (AAAAMM+HORA+UF+CODIGO)                                                          |
| N/A                                                      | N/A           | N/A                                                                | AAAAMM                           | string        | Safra do monitoramento                                                  |
| N/A                                                      | N/A           | N/A                                                                | year_month                       | string        | Ano e Mês do monitoramento                                              |



## Instalação

Para configurar e rodar este projeto, certifique-se de que você possui os seguintes pré-requisitos configurados:

### 1. Docker e Docker Compose

O projeto utiliza Docker para containerizar o ambiente. Certifique-se de que o Docker e o Docker Compose estão instalados na sua máquina.

### 2. Arquivo `docker-compose.yml`

O arquivo `docker-compose.yml` configura os serviços necessários, como Airflow, PostgreSQL e Redis. Ele também define as variáveis de ambiente e volumes necessários para o funcionamento do Airflow.

- **Localização**: O arquivo [`docker-compose.yml`](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/docker-compose.yaml) está na raiz do projeto.
- **Função**: Gerencia a orquestração dos contêineres Docker.

### 3. Dockerfile

O `Dockerfile` define a imagem base para o Airflow e especifica a instalação de dependências adicionais, como o Java e pacotes Python necessários.

- **Localização**: O [`Dockerfile`](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/Dockerfile) está na raiz do projeto.
- **Função**: Cria a imagem personalizada do Airflow com as dependências necessárias.

### 4. Requisitos do Python (`requirements.txt`)

O arquivo `requirements.txt` contém todas as bibliotecas Python necessárias para o projeto.

- **Localização**: O arquivo [`requirements.txt`](https://github.com/KleuberFav/etl_e_monitoramento_inmet/blob/master/requirements.txt) está na raiz do projeto.
- **Função**: Lista as dependências Python que serão instaladas no ambiente Airflow.

### 5. Plugins e DAGs

- **DAGs**: As DAGs que definem o fluxo de trabalho do Airflow estão localizadas na pasta `dags/`.
- **Plugins**: Os plugins personalizados estão localizados na pasta `plugins/`.

### 6. Variáveis de Ambiente

Você precisará criar um arquivo chamado `.env`, localizado no diretório virtual `.venv`. Dentro desse arquivo você precisa informar as seguintes variáveis:

- AIRFLOW__SMTP__SMTP_HOST= smtp.seuprovedor.com
- IRFLOW__SMTP__SMTP_USER= seuemail@email.com
- AIRFLOW__SMTP__SMTP_PASSWORD= senha_do_seu_email
- AIRFLOW__SMTP__SMTP_PORT= porta
- AIRFLOW__SMTP__MAIL_FROM=s euemail@email.com

### 7. Execução do Projeto

Para rodar o projeto, siga os passos abaixo:

1. **Construa os contêineres**: 
   ```bash
   docker-compose up --build
### Resumo

- **Docker Compose**: Explica a função do arquivo sem revelar o conteúdo.
- **Dockerfile**: Resume o propósito do Dockerfile.
- **requirements.txt**: Descreve o arquivo de dependências Python.
- **Plugins e DAGs**: Indica onde estão localizados.
- **Variáveis de Ambiente**: Menciona o uso do arquivo `.env`.
- **Execução**: Orienta sobre como iniciar o projeto.


## Autor
**Kleuber Favacho** - *Engenheiro de Dados e Estatístico* 
- [github](https://github.com/KleuberFav)
- [linkedin](https://www.linkedin.com/in/kleuber-favacho/)
