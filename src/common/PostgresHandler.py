import psycopg2

class PostgresHandler:
    def __init__(self, host,port,dbname,user,password):
        self.host = host 
        self.port = port
        self.dbname  = dbname
        self.user  = user
        self.password  = password
        self.connectPostgres()
    
    def connectPostgres(self):
        self.conn = psycopg2.connect(host=self.host, dbname=self.dbname,user=self.user,password=self.password,port=self.port)
        return self.conn

    def getTableRecord(self,db,table):
        cursor=self.conn.cursor()
        cursor.execute(f'select * from {db}.{table}')
        colnames = [desc[0] for desc in cursor.description]
        row = cursor.fetchall()
        return colnames,row

    def getTableRecordWithCondition(self,db,table,condition):
        cursor=self.conn.cursor()
        cursor.execute(f'select * from {db}.{table} where {condition}')
        colnames = [desc[0] for desc in cursor.description]
        row = cursor.fetchall()
        return colnames,row

    def getTableRecordWithSelectCondition(self,db,table,select,condition):
        cursor=self.conn.cursor()
        cursor.execute(f'select {select} from {db}.{table} where {condition}')
        colnames = [desc[0] for desc in cursor.description]
        row = cursor.fetchall()
        return colnames,row

    def getResultByQuery(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)
        colnames = [desc[0] for desc in cursor.description]
        row = cursor.fetchall()
        return colnames, row

    def getResultByQueryWithArgument(self, query,args):
        cursor = self.conn.cursor()
        cursor.execute(query,args)
        colnames = [desc[0] for desc in cursor.description]
        row = cursor.fetchall()
        return colnames, row

    def executeQuery(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)

    def executeQueryWithArgument(self, query,args):
        cursor = self.conn.cursor()
        cursor.execute(query,args)

    def commit(self):
        self.conn.commit()

    def convertRecordToJsons(colnames,rows):
        jsons = []
        for row in rows:
            jsons.append(dict(zip(colnames, row)))
        return jsons


    def close(self):
        if hasattr(self, 'conn') and self.conn != None:
            if self.conn.closed == 0:
                self.conn.cursor().close()
                self.conn.close()

    def __del__(self):
         self.close()
