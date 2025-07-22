import os
import configparser
from pathlib import Path
from Lib.CryptHandler import *

class ConfigHandler:    
    
    def __init__(self,filename=None):
        self.conf = configparser.ConfigParser()
        self.loadConfig(filename)
        self.loadVariables()

    def loadEnv(self):
        environment = os.getenv("ENVIRONMENT", "local")

        if environment == None:
            environment = 'local'

        return environment

    def loadConfig(self,filename):
        if filename == None:
            filename = f"config_{self.loadEnv()}.ini"

        self.loadfilename=filename
        filepath = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parent, '../conf/'+filename)
        self.conf.read(filepath, encoding="utf-8")
        

    def writeConfig(self,filename=object()):
        if filename == object():
            filename = self.loadfilename
            
        if filename == None:
            filename = 'config.ini'
            
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../conf/'+filename)
        with open(filepath, 'w', encoding='utf-8') as configfile:
            self.conf.write(configfile)
        
        
    def getKeys(self,section,key):
        arr = []

        if section == None:
            for itemkey in self.conf.keys():
                arr.append(itemkey)
            return arr

        try:
            if key == None:
                for itemkey in self.conf[section].keys():
                    arr.append(itemkey)
            else:
                for itemkey in self.conf[section][key].keys():
                    arr.append(itemkey)
        except:
            raise('해당하는 설정 섹션이 존재하지 않습니다')

        return arr

    def getConf(self, section, key):
        try:
            result = self.conf[section][key]
        except KeyError:
            result = None

        return result

    def getConfWithDecode(self, section, key,cryptkey):

        try:
            result = self.conf[section][key]
            if cryptkey is not None and result is not None and result.startswith("ENC("):
                result = CryptHandler.decryptWithcryptkey(cryptkey,result)
        except Exception:
            result = None

        return result

    def addSection(self,section):
        self.conf.add_section(section)
        
        
    def setConf(self,section,key,value):
        if section not in self.conf.keys():
            self.addSection(section)
        self.conf[section][key] = str(value)
        
        
    def getAllVariables(self):
        return [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]

    
    def loadVariables(self):
        self.SECURITY_CRYPTKEY = self.getConf('security', 'cryptkey')

        self.LOG_KEEPDATE_LIMIT = int(self.getConf('log', 'keepdatelimit'))
        self.LOG_LEVEL = self.getConf('log', 'level')
        self.POSTGRES_HOST = self.getConf('postgres', 'host')
        self.POSTGRES_PORT = self.getConf('postgres', 'port')
        self.POSTGRES_USER = self.getConf('postgres', 'user')
        self.POSTGRES_PASSWORD = self.getConfWithDecode('postgres', 'password',self.SECURITY_CRYPTKEY)
        self.POSTGRES_DATABASE = self.getConf('postgres', 'database')
        self.POSTGRES_SCHEMA = self.getConf('postgres', 'schema')
        self.POSTGRES_METATABLE = self.getConf('postgres', 'metatable')
        self.POSTGRES_CLASSIFICATIONTABLE = self.getConf('postgres', 'classificationtable')
        self.POSTGRES_SYSTEMINFOTABLE = self.getConf('postgres', 'systeminfotable')
        self.POSTGRES_ROLEMETATABLE = self.getConf('postgres', 'rolemetatable')
        self.POSTGRES_ROLEUSERTABLE = self.getConf('postgres', 'roleusertable')
        self.POSTGRES_ROLEDEPTTABLE = self.getConf('postgres', 'roledepttable')
        self.POSTGRES_ACCOUNTTABLE = self.getConf('postgres', 'accounttable')
        self.POSTGRES_HISTORYTABLE = self.getConf('postgres', 'historytable')
        self.POSTGRES_DOWNLOADTABLE = self.getConf('postgres', 'downloadtable')
        self.POSTGRES_DEPTTABLE = self.getConf('postgres', 'depttable')
        self.POSTGRES_CODETABLE = self.getConf('postgres', 'codetable')
        self.ES_URL = self.getConf('elasticsearch', 'url')
        self.ES_METAINDEX = self.getConf('elasticsearch', 'metaindex')
        self.ES_SSHHOST = self.getConf('elasticsearch', 'sshhost')
        self.ES_SSHPORT = self.getConf('elasticsearch', 'sshport')
        self.ES_SSHID = self.getConf('elasticsearch', 'sshid')
        self.ES_SSHPASSWORD = self.getConfWithDecode('elasticsearch', 'sshpassword',self.SECURITY_CRYPTKEY)
        self.ES_SYNONYMLOCALFILEPATH = self.getConf('elasticsearch', 'synonymlocalfilepath')
        self.ES_SYNONYMREMOTEFILEPATH = self.getConf('elasticsearch', 'synonymremotefilepath')
        self.ES_USERDICLOCALFILEPATH = self.getConf('elasticsearch', 'userdiclocalfilepath')
        self.ES_USERDICREMOTEFILEPATH = self.getConf('elasticsearch', 'userdicremotefilepath')
        self.TRINO_HOST = self.getConf('trino', 'host')
        self.TRINO_PORT = self.getConf('trino', 'port')
        self.TRINO_USER = self.getConf('trino', 'user')
        self.ES_API_PREFIXURI = self.getConf('es_api', 'prefixuri')
        self.ES_API_PROJECTNAME = self.getConf('es_api', 'projectname')
        self.ES_API_PORT = self.getConf('es_api', 'port')
        self.ES_SEARCH_API_PREFIXURI = self.getConf('es_search_api', 'prefixuri')
        self.ES_SEARCH_API_PROJECTNAME = self.getConf('es_search_api', 'projectname')
        self.ES_SEARCH_API_PORT = self.getConf('es_search_api', 'port')
        self.DATAEXTRACT_API_URL = self.getConf('dataextract_api', 'url')
        self.DATAEXTRACT_API_PREFIXURI = self.getConf('dataextract_api', 'prefixuri')
        self.DATAEXTRACT_API_PROJECTNAME = self.getConf('dataextract_api', 'projectname')
        self.DATAEXTRACT_API_PORT = self.getConf('dataextract_api', 'port')
        self.DATAEXTRACT_API_SECURITYTOKEN = self.getConf('dataextract_api', 'securitytoken')
        self.DATAEXTRACT_API_SSL_CERTFILE = self.getConf('dataextract_api', 'ssl_certfile')
        self.DATAEXTRACT_API_SSL_KEYFILE = self.getConf('dataextract_api', 'ssl_keyfile')
        self.DATAEXTRACT_MAX_THREAD = self.getConf('dataextract', 'max_thread')
        self.DATAEXTRACT_CHECK_INTERVAL = self.getConf('dataextract', 'check_interval')
        self.DATAEXTRACT_SAVECSVPATH = self.getConf('dataextract', 'savecsvpath')
        self.DATAEXTRACT_REPORTMAIL = self.getConf('dataextract', 'reportmail')
        self.MINIO_URL = self.getConf('minio', 'url')
        self.MINIO_ACCESSKEY = self.getConf('minio', 'accesskey')
        self.MINIO_SECRETKEY = self.getConf('minio', 'secretkey')
        self.MINIO_SECURE = self.getConf('minio', 'secure')
        self.MINIO_DATAEXTRACT_BUCKET = self.getConf('minio', 'dataextract_bucket')
        self.MINIO_FILE_SERVICE_TITLE = self.getConf('minio_file_service', 'title')
        self.MINIO_FILE_SERVICE_DESCRIPTION = self.getConf('minio_file_service', 'description')
        self.MINIO_FILE_SERVICE_PREFIXURI = self.getConf('minio_file_service', 'prefixuri')
        self.MINIO_FILE_SERVICE_HOST = self.getConf('minio_file_service', 'host')
        self.MINIO_FILE_SERVICE_PORT = self.getConf('minio_file_service', 'port')
        self.MONITORING_SERVICE_TITLE = self.getConf('monitoring', 'title')
        self.MONITORING_SERVICE_DESCRIPTION = self.getConf('monitoring', 'description')
        self.MONITORING_SERVICE_PREFIXURI = self.getConf('monitoring', 'prefixuri')
        self.MONITORING_SERVICE_HOST = self.getConf('monitoring', 'host')
        self.MONITORING_SERVICE_PORT = self.getConf('monitoring', 'port')
        self.MONITORING_SERVICE_TEMP_DIR = self.getConf('monitoring', 'tmp_dir')
        self.MONITORING_SERVICE_ALTIBASE_ODBC_INST = self.getConf('monitoring', 'altibase_odbc_inst')
        self.MONITORING_SERVICE_MSSQL_ODBC_INST = self.getConf('monitoring', 'mssql_odbc_inst')
        self.MONITORING_SERVICE_TIBERO_ODBC_INST = self.getConf('monitoring', 'tibero_odbc_inst')
        self.AIRFLOW_HOST = self.getConf('airflow', 'host')
        self.AIRFLOW_PORT = self.getConf('airflow', 'port')
        self.AIRFLOW_USER = self.getConf('airflow', 'user')
        self.AIRFLOW_PASSWORD = self.getConfWithDecode('airflow', 'password',self.SECURITY_CRYPTKEY)
        self.AIRFLOW_DAG_DIR = self.getConf('airflow', 'dag_dir')
        self.AIRFLOW_SSH_HOST = self.getConf('airflow.ssh', 'host')
        self.AIRFLOW_SSH_PORT = self.getConf('airflow.ssh', 'port')
        self.AIRFLOW_SSH_USER = self.getConf('airflow.ssh', 'user')
        self.AIRFLOW_SSH_PASSWORD = self.getConfWithDecode('airflow.ssh', 'password',self.SECURITY_CRYPTKEY)
        self.MINIO_UNSTRUCTURED_BUCKET = self.getConf('minio', 'unstructured_bucket')
        self.MINIO_DOWNLOAD_LIMIT = self.getConf('minio', 'download_limit')
        self.SMTP_SERVER = self.getConf('smtp', 'server')
        self.SMTP_PORT = self.getConf('smtp', 'port')
        self.SMTP_SSL = self.getConf('smtp', 'ssl')
        self.SMTP_USER = self.getConf('smtp', 'user')
        self.SMTP_PASSWORD = self.getConf('smtp', 'password')

