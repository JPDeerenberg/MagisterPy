import json
from .magister_errors import *

class JsParser():
    def get_authcode_from_js(self, js_content: str):
        try:
            # The specific marker the old dev used
            authcode_identifier = "].map((function(t)"
            end_column = js_content.find(authcode_identifier)
            
            if end_column == -1:
                # Fallback: Try the other variation seen in logs
                authcode_identifier = "].map(function(t)"
                end_column = js_content.find(authcode_identifier)

            if end_column == -1:
                raise AuthcodeError("Marker not found in JS.")

            # Grab context before marker
            buffer = 500
            snippet = js_content[max(0, end_column - buffer):end_column + len(authcode_identifier)]
            
            # Find the arrays
            import re
            arrays = []
            for match in re.finditer(r'\[(.*?)\]', snippet):
                try:
                    # Fix JS single quotes
                    clean = match.group(0).replace("'", '"')
                    arr = json.loads(clean)
                    if isinstance(arr, list):
                        arrays.append(arr)
                except: pass

            if len(arrays) < 2:
                raise AuthcodeError("Could not find obfuscated arrays.")

            # Logic: Last array = indices, 2nd last = chars
            indices = arrays[-1]
            chars = arrays[-2]
            
            # Ensure int
            indices = [int(x) for x in indices]
            
            authcode = "".join(str(chars[i]) for i in indices)
            return authcode

        except Exception as e:
            raise AuthcodeError(f"Parser crashed: {e}")