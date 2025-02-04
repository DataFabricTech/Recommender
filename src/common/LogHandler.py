import os,sys,logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

loggers = {}

class LogHandler:
    
    def __init__(self,code_path,log_filename,print_flag):
        temp_path = Path(os.path.dirname(code_path))
        limiter = 0
        while limiter < 10 :
            if temp_path.name == 'src':
                temp_path = temp_path.parent
                break
            temp_path = temp_path.parent
            limiter = limiter + 1

        log_path = str(temp_path.resolve())+'/logs'
        self.setLogger(log_path,log_filename,print_flag)

    def setLoglevel(self):
        self.logger.setLevel(logging.INFO)

    def setLogger(self,log_file_dir,log_file_name, print_flag=False):
        global loggers

        if loggers.get(log_file_name):
            self.logger = loggers.get(log_file_name)
        else:
            log_format = '[%(asctime)s] {%(name)s:%(lineno)d} %(levelname)s - %(message)s'
            formatter = logging.Formatter(log_format)

            #file
            log_file_path = log_file_dir + "/" + log_file_name + ".log"
            file_suffix = '%Y%m%d'

            file_path = Path(log_file_dir)
            file_path.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger(log_file_name)
            logger.setLevel(logging.INFO)

            #filetime
            time_handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=31, utc=False)
            time_handler.suffix = file_suffix
            time_handler.setFormatter(formatter)
            logger.addHandler(time_handler)

            #console print
            if print_flag == True:
                stream_handler = logging.StreamHandler(sys.stdout)
                stream_handler.setFormatter(formatter)
                logger.addHandler(stream_handler)

            loggers[log_file_name] = logger
            self.logger = logger
        
        

    def debug(self,message):
        self.logger.debug(message, stacklevel=2)
        
        
    def info(self,message):
        self.logger.info(message, stacklevel=2)
        
        
    def warning(self,message):
        self.logger.warning(message, stacklevel=2)
    
    
    def error(self,message):
        self.logger.error(message, stacklevel=2)
        
    
    def critical(self,message):
        self.logger.critical(message, stacklevel=2)
        