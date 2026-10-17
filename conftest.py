"""Root conftest para masiguro na nasa sys.path ang project root sa tests."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
