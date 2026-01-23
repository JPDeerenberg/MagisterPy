from typing import Union

class JsonResponseItem():
    def __init__(self, json: Union[list, dict]):
        self.json = json
    def __getitem__(self, key): return self.json[key]
    def __repr__(self): return f"{repr(self.json)}"