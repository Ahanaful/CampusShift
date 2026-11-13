"""JSON logs without request headers, bodies, URLs, or SQL parameters."""
import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record):
        # Exception messages/tracebacks can contain connection strings or payloads.
        data = {"timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname, "logger": record.name,
                "message": record.getMessage()}
        if record.exc_info:
            data["exception_type"] = record.exc_info[0].__name__
        return json.dumps(data)
