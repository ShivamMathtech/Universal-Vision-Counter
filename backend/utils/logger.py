import json
import logging
from datetime import datetime, timezone
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload={'time':datetime.now(timezone.utc).isoformat(),'level':record.levelname,'message':record.getMessage()}
        if record.exc_info: payload['exception']=self.formatException(record.exc_info)
        return json.dumps(payload)
def setup_logging():
    handler=logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO,handlers=[handler])
