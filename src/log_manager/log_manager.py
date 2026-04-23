# -*- coding: utf-8 -*-
# src/log_manager/log_manager.py

import json
import os
from datetime import datetime

SECURITY_SENSITIVE_EVENTS = [
    "action_execution_file_create",
    "action_execution_file_append",
    "action_execution_file_delete",
    "action_execution_file_move",
    "action_execution_file_copy",
    "action_execution_command_run",
    "action_execution_apply_code_fix",
    "action_execution_apply_refactoring",
    "action_execution_test_generation",
]

class AuditComplianceError(Exception):
    """Raised when a security-sensitive event fails audit validation."""
    pass

class LogManager:
    SENSITIVE_FIELDS = ["filename", "command", "content", "error_details"]
    DEFAULT_SENSITIVE_KEYWORDS = [
        "token",
        "secret",
        "password",
        "api_key",
        "apikey",
        "access_key",
        "private_key"
    ]

    def __init__(self, log_dir="logs", log_file_prefix="pipeline", log_level="INFO", strict_audit=True, config_manager=None):
        """
        Initializes the LogManager.
        """
        self.config_manager = config_manager
        # Override with config if available
        if config_manager:
            log_config = config_manager.get_section("logging")
            self.log_dir = log_config.get("log_dir", log_dir)
            self.log_file_prefix = log_config.get("log_file_prefix", log_file_prefix)
            self.log_level = self._parse_log_level(log_config.get("log_level", log_level))
            self.strict_audit = log_config.get("strict_audit", strict_audit)
            self.sensitive_fields = log_config.get("sensitive_fields", self.SENSITIVE_FIELDS)
            self.sensitive_field_keywords = [k.lower() for k in log_config.get("sensitive_field_keywords", [])]
        else:
            self.log_dir = log_dir
            self.log_file_prefix = log_file_prefix
            self.log_level = self._parse_log_level(log_level)
            self.strict_audit = strict_audit
            self.sensitive_fields = self.SENSITIVE_FIELDS
            self.sensitive_field_keywords = self.DEFAULT_SENSITIVE_KEYWORDS

        self._ensure_log_dir()
        self.log_file_path = os.path.join(self.log_dir, f"{self.log_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        self.json_log_file_path = os.path.join(self.log_dir, f"{self.log_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        self.error_summary_file_path = os.path.join(self.log_dir, "error_summary.json")

    def _parse_log_level(self, level_str):
        levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        return levels.get(level_str.upper(), 1) # Default to INFO

    def _ensure_log_dir(self):
        """Ensures the log directory exists."""
        os.makedirs(self.log_dir, exist_ok=True)

    def sanitize_log_data(self, data):
        """Recursively sanitizes sensitive fields in log data."""
        if not isinstance(data, dict):
            return data
            
        sanitized = {}
        for key, value in data.items():
            if key in self.sensitive_fields or self._is_sensitive_key(key):
                sanitized[key] = self._mask_sensitive_value(value)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_log_data(value)
            elif isinstance(value, list):
                sanitized[key] = [self.sanitize_log_data(item) if isinstance(item, dict) else item for item in value]
            else:
                sanitized[key] = value
        return sanitized

    def _is_sensitive_key(self, key: str) -> bool:
        if not key or not self.sensitive_field_keywords:
            return False
        lowered = str(key).lower()
        return any(token in lowered for token in self.sensitive_field_keywords)

    def _mask_sensitive_value(self, value):
        """Masks a sensitive value completely for security."""
        return "***"

    def get_events_after(self, start_timestamp: datetime):
        """Retrieves events from the JSON log file that occurred after the given timestamp (with buffer)."""
        from datetime import timedelta
        # Use a small buffer (5 seconds)
        adjusted_start = start_timestamp - timedelta(seconds=5)
        
        events = []
        if not os.path.exists(self.json_log_file_path):
            return []
            
        try:
            with open(self.json_log_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content: return []
                
                # The log file has objects followed by ",\n"
                # Remove trailing comma and newline
                content = content.rstrip(',\n ')
                
                # Wrap in [] to make it a list
                json_content = "[" + content + "]"
                try:
                    raw_events = json.loads(json_content)
                    for ev in raw_events:
                        ev_time = datetime.fromisoformat(ev["timestamp"])
                        if ev_time >= adjusted_start:
                            events.append(ev)
                except json.JSONDecodeError as jde:
                    # print(f"[DEBUG] JSONDecodeError: {jde} at {jde.pos}")
                    # Brute force extraction as fallback
                    import re
                    # Find all { ... } structures
                    start_pos = 0
                    while True:
                        s = content.find('{', start_pos)
                        if s == -1: break
                        
                        count = 0
                        e = -1
                        for i in range(s, len(content)):
                            if content[i] == '{': count += 1
                            elif content[i] == '}':
                                count -= 1
                                if count == 0:
                                    e = i
                                    break
                        if e != -1:
                            try:
                                ev = json.loads(content[s:e+1])
                                ev_time = datetime.fromisoformat(ev["timestamp"])
                                if ev_time >= adjusted_start:
                                    events.append(ev)
                            except: pass
                            start_pos = e + 1
                        else: break
        except Exception as e:
            print(f"Error reading log: {e}")
            
        return events

    def _format_message(self, level, message):
        """Formats the log message with timestamp and level."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"[{timestamp}] [{level}] {message}"

    def log_event(self, event_type: str, data: dict, level: str = "INFO"):
        """
        Logs an event to both human-readable and JSON log files.
        For security-sensitive events, strictly enforces audit data requirements.
        
        Args:
            event_type (str): Type of event.
            data (dict): Event data.
            level (str): Log level.
            
        Raises:
            AuditComplianceError: If strict_audit is True and a security event is missing required fields.
        """
        if self._parse_log_level(level) < self.log_level:
            return

        # Auditability check for security-sensitive events
        if event_type in SECURITY_SENSITIVE_EVENTS:
            missing_fields = []
            required_fields = ["parameters", "status"]
            
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                error_msg = f"Security-sensitive event '{event_type}' missing critical audit fields: {', '.join(missing_fields)}"
                
                # Log the violation attempt before raising error
                violation_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "CRITICAL",
                    "event_type": "audit_violation",
                    "data": {
                        "attempted_event": event_type,
                        "missing_fields": missing_fields,
                        "original_data": data
                    }
                }
                self._write_log(violation_entry, "CRITICAL", f"AUDIT VIOLATION: {error_msg}")

                if self.strict_audit:
                    raise AuditComplianceError(error_msg)
                else:
                    # Fallback to warning if strict mode is disabled (legacy behavior)
                    self.log_event("audit_warning", {"message": error_msg, "original_event_data": data}, "WARNING")

        # Prepare common log data
        sanitized_data = self.sanitize_log_data(data)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "event_type": event_type,
            "data": sanitized_data
        }

        self._write_log(log_entry, level.upper(), f"Event: {event_type}, Data: {json.dumps(sanitized_data, ensure_ascii=False)}")

        # Handle error summary
        if event_type == "action_execution" and data.get("status") == "error":
            self._handle_error_summary(data)

    def _write_log(self, json_entry, level_str, text_message):
        """Internal method to write to files."""
        # Write to human-readable log
        with open(self.log_file_path, 'a', encoding='utf-8') as f_text:
            formatted_message = self._format_message(level_str, text_message)
            f_text.write(formatted_message + "\n")

        # Write to JSON log
        with open(self.json_log_file_path, 'a', encoding='utf-8') as f_json:
            f_json.write(json.dumps(json_entry, ensure_ascii=False) + ",\n")

    def _handle_error_summary(self, data):
        """Logs a summary of action execution errors."""
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "original_text": data.get("original_text", ""),
            "action": data.get("action"),
            "error_message": data.get("message"),
            "original_error": data.get("original_error"),
            "suggested_action": data.get("suggested_action")
        }
        
        error_records = []
        if os.path.exists(self.error_summary_file_path):
            try:
                with open(self.error_summary_file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content.startswith("[") and content.endswith("]"):
                        error_records = json.loads(content)
                    elif content:
                        try:
                            error_records = [json.loads(content)]
                        except json.JSONDecodeError:
                            error_records = []
            except Exception as e:
                print(f"Error reading error summary file: {e}. Starting new.")

        error_records.append(error_data)
        
        with open(self.error_summary_file_path, 'w', encoding='utf-8') as f:
            json.dump(error_records, f, indent=4, ensure_ascii=False)
            # TODO: Implement Logic: **初期化**:
