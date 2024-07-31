import os,sys,logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


class LogHandler:
    
    def __init__(self,code_path,print_flag):
        log_path = str(Path(os.path.dirname(code_path)).parent.parent.parent.resolve())+'/log'
        log_filename = Path(code_path).stem
        self.setLogger(log_path,log_filename,print_flag)
    
    
    def setLoglevel(self):
        self.logger.setLevel(logging.INFO)
        

    def setLogger(self,log_file_dir,log_file_name, print_flag=False):
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
            
        self.logger = logger
        
        

    def debug(self,message):
        self.logger.debug(message)
        
        
    def info(self,message):
        self.logger.info(message)
        
        
    def warning(self,message):
        self.logger.warning(message)
    
    
    def error(self,message):
        self.logger.error(message)
        
    
    def critical(self,message):
        self.logger.critical(message)
        