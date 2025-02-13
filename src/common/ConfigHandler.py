import os,configparser
from pathlib import Path
from Lib.CryptHandler import *

class ConfigHandler:    
    
    def __init__(self,filename=None):
        self.conf = configparser.ConfigParser()
        self.loadConfig(filename)
        self.loadVariables()

    def loadEnv(self):
        filepath = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parent, '../conf/environment.ini')
        envconf = configparser.ConfigParser()
        envconf.read(filepath)

        if envconf is None or 'config' not in envconf.keys() or 'file_postfix' not in envconf['config'].keys():
            env = 'local'
        else:
            env = envconf['config']['file_postfix']

        return env

    def loadConfig(self,filename):
        if filename == None:
            filename = f"config_{self.loadEnv()}.ini"

        self.loadfilename=filename
        filepath = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parent, '../conf/'+filename)
        self.conf.read(filepath)
        

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
        except KeyError:
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
        self.DATAEXTRACT_API_URL = self.getConf('dataextract_api', 'url')
        self.DATAEXTRACT_API_PREFIXURI = self.getConf('dataextract_api', 'prefixuri')
        self.DATAEXTRACT_API_PROJECTNAME = self.getConf('dataextract_api', 'projectname')
        self.DATAEXTRACT_API_PORT = self.getConf('dataextract_api', 'port')
        self.DATAEXTRACT_API_SECURITYTOKEN = self.getConf('dataextract_api', 'securitytoken')
        self.DATAEXTRACT_MAX_THREAD = self.getConf('dataextract', 'max_thread')
        self.DATAEXTRACT_CHECK_INTERVAL = self.getConf('dataextract', 'check_interval')
        self.DATAEXTRACT_SAVECSVPATH = self.getConf('dataextract', 'savecsvpath')
        self.DATAEXTRACT_SSL_CERTFILE = self.getConf('dataextract', 'ssl_certfile')
        self.DATAEXTRACT_SSL_KEYFILE = self.getConf('dataextract', 'ssl_keyfile')
        self.MINIO_HOST = self.getConf('minio', 'host')
        self.MINIO_ACCESSKEY = self.getConf('minio', 'accesskey')
        self.MINIO_SECRETKEY = self.getConf('minio', 'secretkey')
        self.MINIO_DATAEXTRACT_BUCKET = self.getConf('minio', 'dataextract_bucket')
        self.MINIO_DOWNLOAD_LIMIT = self.getConf('minio', 'download_limit')


    def setDefaultOptions(self,filename):
        self.addSection('security')
        self.addSection('log')
        self.addSection('postgres')
        self.addSection('elasticsearch')
        self.addSection('trino')
        self.addSection('es_api')
        self.addSection('dataextract_api')
        self.addSection('dataextract')
        self.addSection('minio')
        self.setConf('security','cryptkey','DataCatalog12#')
        self.setConf('log','keepdatelimit','30')
        self.setConf('postgres','host','192.168.100.110')
        self.setConf('postgres','port','15432')
        self.setConf('postgres','user','data_catalog')
        self.setConf('postgres','password','otdev123')
        self.setConf('postgres','database','data_catalog')
        self.setConf('postgres','schema','public')
        self.setConf('postgres','metatable','<table>')
        self.setConf('postgres','classificationtable','<table>')
        self.setConf('postgres','systeminfotable','<table>')
        self.setConf('postgres','rolemetatable','<table>')
        self.setConf('postgres','roleusertable','<table>')
        self.setConf('postgres','roledepttable','<table>')
        self.setConf('postgres','accounttable','<table>')
        self.setConf('postgres','historytable','<table>')
        self.setConf('postgres','downloadtable','<table>')
        self.setConf('postgres','depttable','<table>')
        self.setConf('elasticsearch','url','http://192.168.100.72:9200')
        self.setConf('elasticsearch','metaindex','index_analyzer')
        self.setConf('elasticsearch','sshhost','192.168.100.72')
        self.setConf('elasticsearch','sshport','22')
        self.setConf('elasticsearch','sshid','otdev')
        self.setConf('elasticsearch','sshpassword','otdev123')
        self.setConf('elasticsearch','synonymlocalfilepath','/data1/elasticsearch/elasticsearch-8.9.0/config/analysis/userdic.txt')
        self.setConf('elasticsearch','synonymremotefilepath','synonym.txt')
        self.setConf('elasticsearch','userdiclocalfilepath','/data1/elasticsearch/elasticsearch-8.9.0/config/analysis/userdic.txt')
        self.setConf('elasticsearch','userdicremotefilepath','userdic.txt')
        self.setConf('trino','host','192.168.100.72')
        self.setConf('trino','port','8080')
        self.setConf('trino','user','admin')
        self.setConf('es_api','prefixuri','/v1/')
        self.setConf('es_api','projectname','essink')
        self.setConf('es_api','port','8000')
        self.setConf('dataextract_api','url','http://0.0.0.0')
        self.setConf('dataextract_api','prefixuri','/')
        self.setConf('dataextract_api','projectname','dataextract')
        self.setConf('dataextract_api','port','13200')
        self.setConf('dataextract_api','securitytoken','security_token123')
        self.setConf('dataextract','max_thread','5')
        self.setConf('dataextract','check_interval','20')
        self.setConf('dataextract','savecsvpath','/home/otdev/dataextract_csvdata')
        self.setConf('dataextract','ssl_certfile','')
        self.setConf('dataextract','ssl_keyfile','')
        self.setConf('minio','host','192.168.100.72:44813')
        self.setConf('minio','accesskey','NQ5aS8Ousl3iKVvKT5Dq')
        self.setConf('minio','secretkey','5CZNY0XbhqCn86c6LJ5Sn4ctDqwVnIP3IcMlrzxF')
        self.setConf('minio','dataextract_bucket','dataextract')
        self.setConf('minio','download_limit','7')
        self.writeConfig(filename)
    
    
    
    
    


