import os,sys,logging
from pathlib import Path
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

loggers = {}

class LogHandler:
    
    def __init__(self,code_path,log_filename,logkeepdate,print_flag):
        temp_path = Path(os.path.dirname(code_path))
        limiter = 0
        while limiter < 10 :
            if temp_path.name == 'src':
                temp_path = temp_path.parent
                break
            temp_path = temp_path.parent
            limiter = limiter + 1

        log_path = str(temp_path.resolve())+'/logs'
        self.setLogger(log_path,log_filename,logkeepdate,print_flag)

    def removeOldBackup(self,log_filename, log_path, logkeepdate):
        log_file_list = os.listdir(log_path)
        log_file_path = f"{log_path}/{log_filename}.log"

        correct_log_date = []
        for log_file in log_file_list:

            if os.path.isfile(f"{log_path}/{log_file}") is False:
                continue

            if not log_file.startswith(f"{log_filename}.log"):
                continue

            log_file_split = log_file.split(".")

            if len(log_file_split) < 3:
                continue

            log_date = log_file_split[2]

            try:
                datetime.strptime(log_date, '%Y%m%d')
            except Exception as e:
                continue

            if log_date not in correct_log_date:
                correct_log_date.append(log_date)

        if len(correct_log_date) > logkeepdate:
            correct_log_date.sort(reverse=True)
            for log_date in correct_log_date[logkeepdate:]:
                remove_file_path = f"{log_file_path}.{log_date}"
                if os.path.isfile(remove_file_path) is True:
                    os.remove(remove_file_path)
                for index in range(1, logkeepdate + 1):
                    if os.path.isfile(f"{remove_file_path}.{index}") is True:
                        os.remove(f"{remove_file_path}.{index}")

    def setLoglevel(self):
        self.logger.setLevel(logging.INFO)

    def setLogger(self,log_file_dir,log_file_name,logkeepdate,print_flag):
        global loggers

        if log_file_dir and os.path.isdir(log_file_dir) is True:
            self.removeOldBackup(log_file_name, log_file_dir,logkeepdate)

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
        self.logger.debug(message, stacklevel=3)
        
        
    def info(self,message):
        self.logger.info(message, stacklevel=3)
        
        
    def warning(self,message):
        self.logger.warning(message, stacklevel=3)
    
    
    def error(self,message):
        self.logger.error(message, stacklevel=3)
        
    
    def critical(self,message):
        self.logger.critical(message, stacklevel=3)
        