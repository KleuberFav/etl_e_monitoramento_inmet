from airflow.plugins_manager import AirflowPlugin

from plugins.bronze_plugin import Bronze
from plugins.silver_plugin import Silver
from plugins.monitoramento_plugin import Monitoramento
from plugins.gold_ts_plugin import Gold_ts, MetricsMonitor

class CustomPlugin(AirflowPlugin):
    name = "custom_plugin"
    operators = []
    sensors = []
    hooks = []
    executors = []
    macros = []
    admin_views = []
    flask_blueprints = []
    menu_links = []
    appbuilder_views = []
    appbuilder_menu_items = []
    global_operator_extra_links = []
    operator_extra_links = []
