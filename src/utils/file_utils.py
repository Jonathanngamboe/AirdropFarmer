# utils.py
import json

def load_abi(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)
