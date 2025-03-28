warcraftlogs/__init__.py

"""
Warcraft Logs API Client

A Python package for authenticating and interacting with the Warcraft Logs API.
"""

import os

__version__ = '0.1.0'

# Default credentials from environment variables
CLIENT_ID = os.getenv("WARCRAFTLOGS_CLIENT_ID", "9e88c213-bde4-4e0d-b005-86e96d73cb48")
CLIENT_SECRET = os.getenv("WARCRAFTLOGS_CLIENT_SECRET", "49wPdfRm09dWC7Id5Pxp9tZMUMV3OQpmPb0kYILL")

# API endpoints
AUTHORIZE_URI = "https://www.warcraftlogs.com/oauth/authorize"
TOKEN_URI = "https://www.warcraftlogs.com/oauth/token"
CLIENT_API_URL = "https://www.warcraftlogs.com/api/v2/client"
USER_API_URL = "https://www.warcraftlogs.com/api/v2/user"

# Import main classes for easier access
from .client import WarcraftLogsClient
from .token_manager import TokenManager
from .api import execute_graphql_query
from .auth import (
    get_client_credentials_token,
    get_authorization_url,
    exchange_code_for_token,
    refresh_access_token
)