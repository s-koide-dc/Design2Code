# -*- coding: utf-8 -*-
import time
import random
import functools

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=10, exceptions=(IOError, OSError, ConnectionError)):
    """
    Retry decorator with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        break
                    
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    
                    # If the first argument is an instance of a class with a log_manager or ae.log_manager
                    log_manager = None
                    if hasattr(args[0], 'log_manager'):
                        log_manager = args[0].log_manager
                    elif hasattr(args[0], 'ae') and hasattr(args[0].ae, 'log_manager'):
                        log_manager = args[0].ae.log_manager
                    
                    if log_manager:
                        log_manager.log_event("retry_attempt", {
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e)
                        }, level="WARNING")
                    
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator
