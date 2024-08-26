import os,configparser
from pathlib import Path

class ConfigHandler:    
    
    def __init__(self,filename=None):
        self.conf = configparser.ConfigParser()
        self.loadConfig(filename)
        self.loadVariables()
        
    def loadConfig(self,filename):
        if filename == None:
            filename = 'config.ini'
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

    
    def getConf(self,section,key):
        try:
            result = self.conf[section][key]
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
        self.POSTGRES_HOST = self.getConf('postgres', 'host')
        self.POSTGRES_PORT = self.getConf('postgres', 'port')
        self.POSTGRES_USER = self.getConf('postgres', 'user')
        self.POSTGRES_PASSWORD = self.getConf('postgres', 'password')
        self.POSTGRES_DATABASE = self.getConf('postgres', 'database')
        self.POSTGRES_SCHEMA = self.getConf('postgres', 'schema')
        self.POSTGRES_METATABLE = self.getConf('postgres', 'metatable')
        self.POSTGRES_CLASSIFICATIONTABLE = self.getConf('postgres', 'classificationtable')
        self.ES_URL = self.getConf('elasticsearch', 'url')
        self.ES_METAINDEX = self.getConf('elasticsearch', 'metaindex')
        self.API_PREFIXURI = self.getConf('api', 'prefixuri')
        self.API_PROJECTNAME = self.getConf('api', 'projectname')
        self.API_PORT = self.getConf('api', 'port')


    
    def setDefaultOptions(self,filename):
        self.addSection('postgres')
        self.addSection('elasticsearch')
        self.setConf('postgres','host','192.168.100.110')
        self.setConf('postgres','port','15432')
        self.setConf('postgres','user','data_catalog')
        self.setConf('postgres','password','otdev123')
        self.setConf('postgres','database','data_catalog')
        self.setConf('postgres','schema','public')
        self.setConf('postgres','metatable','<table>')
        self.setConf('postgres','classificationtable','<table>')
        self.setConf('elasticsearch','url','http://192.168.100.72:9200')
        self.setConf('elasticsearch','metaindex','index_analyzer')
        self.setConf('api','prefixuri','/v1/')
        self.setConf('api','projectname','essink')
        self.setConf('api','port','8000')
        self.writeConfig(filename)

    
    
    
    
    
    
    
    
    
    


