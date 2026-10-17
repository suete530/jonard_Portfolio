"""
extensions.py
-------------
Shared extension instances (para maiwasan ang circular imports).
"""

from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_babel import Babel

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
babel = Babel()
