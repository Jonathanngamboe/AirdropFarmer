# file_utils.py
import json
import os

def load_json(file_path):
    base_dir = os.path.dirname(os.path.abspath(__file__))  # get the directory of the current file
    abs_file_path = os.path.join(base_dir, file_path)  # join it with the relative path
    with open(abs_file_path, 'r') as f:
        return json.load(f)
