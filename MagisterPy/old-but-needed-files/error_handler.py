import requests
from .magister_errors import *

def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (BaseMagisterError, requests.exceptions.ConnectionError) as e:
            print(f"Error in {func.__name__}: {e}")
            raise e
    return wrapper