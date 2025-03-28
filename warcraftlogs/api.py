"""
API interaction functions for the Warcraft Logs API.

This module provides functions for executing GraphQL queries against
the Warcraft Logs API endpoints.
"""

import requests
from typing import Dict, Optional, Any

from . import CLIENT_API_URL, USER_API_URL


def execute_graphql_query(
    query: str, 
    variables: Optional[Dict[str, Any]] = None, 
    token: Optional[str] = None, 
    is_user_api: bool = False,
    refresh_token: Optional[str] = None, 
    user_id: str = "default",
    token_manager=None
) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Warcraft Logs API.
    
    Args:
        query: The GraphQL query string
        variables: Optional variables for the GraphQL query
        token: Access token (will fetch a new one if not provided)
        is_user_api: Whether to use the user API (for private data) or client API (for public data)
        refresh_token: Optional refresh token for automatic token refresh
        user_id: Identifier for the user when using refresh tokens
        token_manager: Optional token manager instance
    
    Returns:
        Dict containing the GraphQL response
    
    Raises:
        requests.RequestException: If the API request fails
        ValueError: If no token is provided for user API requests
    """
    # Lazy import to avoid circular dependency
    from .client import get_access_token
    
    if token is None:
        if is_user_api and not refresh_token:
            raise ValueError("Either access token or refresh token is required for user API requests")
        
        # Get token from manager or generate a new one
        token = get_access_token(refresh_token, user_id, token_manager)
    
    api_url = USER_API_URL if is_user_api else CLIENT_API_URL
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query
    }
    
    if variables:
        payload["variables"] = variables
    
    response = requests.post(api_url, headers=headers, json=payload)
    
    # Handle token expiration
    if response.status_code == 401 and refresh_token and token_manager:
        # Token might be expired, try to refresh and retry
        token_manager.clear_token(f"user_{user_id}" if is_user_api else "client_credentials")
        new_token = get_access_token(refresh_token, user_id, token_manager)
        
        # Update headers with new token
        headers["Authorization"] = f"Bearer {new_token}"
        response = requests.post(api_url, headers=headers, json=payload)
    
    response.raise_for_status()
    return response.json()
