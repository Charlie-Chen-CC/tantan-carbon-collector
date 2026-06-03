"""
pytest配置 - 设置项目路径
"""
import sys
import os

# tantan包位于项目根目录，需要将tantan的父目录加入path
# __file__ = backend/tests/conftest.py
# abspath(__file__) = .../tantan/backend/tests/conftest.py
# dirname = .../tantan/backend/tests
# dirname = .../tantan/backend
# dirname = .../tantan (project root)
# We need tantan/ in path so 'from tantan.backend import X' works
conftest_dir = os.path.dirname(os.path.abspath(__file__))  # backend/tests
backend_dir = os.path.dirname(conftest_dir)  # backend
project_root = os.path.dirname(backend_dir)  # tantan (project root)
sys.path.insert(0, project_root)