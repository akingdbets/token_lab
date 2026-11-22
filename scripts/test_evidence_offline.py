"""Run repository and research tests with outbound HTTP/socket access forbidden."""
import os
import socket
import unittest
from pathlib import Path
from unittest.mock import patch
import requests

ROOT=Path(__file__).resolve().parents[1]

def main():
    os.environ.update({'TOKENIZER':'tiktoken:o200k_base','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
    def forbidden(*args,**kwargs):raise AssertionError('Network access is forbidden in offline tests')
    with patch.object(requests.sessions.Session,'request',forbidden),patch.object(socket.socket,'connect',forbidden):
        suite=unittest.TestSuite()
        for directory in ['tests','scripts']:
            suite.addTests(unittest.TestLoader().discover(str(ROOT/directory),pattern='test_*.py'))
        result=unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(not result.wasSuccessful())

if __name__=='__main__':main()
