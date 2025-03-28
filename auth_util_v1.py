#!/usr/bin/env python3
"""
Warcraft Logs API Authentication Utility

This module provides utility functions for authenticating with the Warcraft Logs API
using different OAuth 2.0 flows as described in the Warcraft Logs API documentation.
"""

import os
import base64
import hashlib
import secrets
import string
import requests
import json
from typing import Dict, Tuple, Optional, Any, Union
from urllib.parse import urlencode

# Default credentials from environment variables
client_id = os.getenv("WARCRAFTLOGS_CLIENT_ID", "9e88c213-bde4-4e0d-b005-86e96d73cb48")
client_secret = os.getenv("WARCRAFTLOGS_CLIENT_SECRET", "49wPdfRm09dWC7Id5Pxp9tZMUMV3OQpmPb0kYILL")

# API endpoints
AUTHORIZE_URI = "https://www.warcraftlogs.com/oauth/authorize"
TOKEN_URI = "https://www.warcraftlogs.com/oauth/token"
CLIENT_API_URL = "https://www.warcraftlogs.com/api/v2/client"
USER_API_URL = "https://www.warcraftlogs.com/api/v2/user"


def get_client_credentials_token() -> Dict[str, Any]:
    """
    Obtain an access token using the client credentials flow.
    This flow is used for accessing public API endpoints.
    
    Returns:
        Dict containing the access token response with keys:
        - access_token: The token to use for API requests
        - token_type: Type of token (usually "Bearer")
        - expires_in: Token validity in seconds
    
    Raises:
        requests.RequestException: If the token request fails
    """
    auth = (client_id, client_secret)
    data = {"grant_type": "client_credentials"}
    
    response = requests.post(TOKEN_URI, auth=auth, data=data)
    response.raise_for_status()
    
    return response.json()


def generate_pkce_verifier_and_challenge() -> Tuple[str, str]:
    """
    Generate a PKCE code verifier and its corresponding challenge.
    
    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate a random code verifier (between 43-128 chars as per RFC 7636)
    allowed_chars = string.ascii_letters + string.digits + "-._~"
    code_verifier = ''.join(secrets.choice(allowed_chars) for _ in range(128))
    
    # Generate code challenge by hashing the verifier with SHA-256
    code_challenge_digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode().rstrip('=')
    
    return code_verifier, code_challenge


def get_authorization_url(redirect_uri: str, state: Optional[str] = None, use_pkce: bool = False) -> Tuple[str, Dict[str, str]]:
    """
    Generate a URL for authorization code flow or PKCE flow.
    
    Args:
        redirect_uri: The URI to redirect to after authorization
        state: Optional state parameter for security
        use_pkce: Whether to use PKCE flow instead of standard authorization code flow
    
    Returns:
        Tuple of (authorization_url, state_data)
        state_data contains:
        - state: The state parameter
        - code_verifier: The code verifier (only if use_pkce=True)
    """
    if state is None:
        state = secrets.token_hex(16)
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state
    }
    
    state_data = {"state": state}
    
    if use_pkce:
        code_verifier, code_challenge = generate_pkce_verifier_and_challenge()
        params.update({
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        })
        state_data["code_verifier"] = code_verifier
    
    auth_url = f"{AUTHORIZE_URI}?{urlencode(params)}"
    return auth_url, state_data


def exchange_code_for_token(code: str, redirect_uri: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
    """
    Exchange an authorization code for an access token.
    
    Args:
        code: The authorization code from the callback
        redirect_uri: The same redirect URI used in the authorization request
        code_verifier: The code verifier (required for PKCE flow)
    
    Returns:
        Dict containing the access token response with keys:
        - access_token: The token to use for API requests
        - token_type: Type of token (usually "Bearer")
        - expires_in: Token validity in seconds
        - refresh_token: Token to get a new access token when it expires
    
    Raises:
        requests.RequestException: If the token request fails
    """
    data = {
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code": code
    }
    
    if code_verifier:
        # PKCE flow
        data["client_id"] = client_id
        data["code_verifier"] = code_verifier
        response = requests.post(TOKEN_URI, data=data)
    else:
        # Standard authorization code flow
        auth = (client_id, client_secret)
        response = requests.post(TOKEN_URI, auth=auth, data=data)
    
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Refresh an access token using a refresh token.
    
    Args:
        refresh_token: The refresh token from a previous token response
    
    Returns:
        Dict containing the new access token response
    
    Raises:
        requests.RequestException: If the token request fails
    """
    auth = (client_id, client_secret)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    response = requests.post(TOKEN_URI, auth=auth, data=data)
    response.raise_for_status()
    
    return response.json()


def execute_graphql_query(query: str, variables: Optional[Dict[str, Any]] = None, 
                         token: Optional[str] = None, is_user_api: bool = False) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Warcraft Logs API.
    
    Args:
        query: The GraphQL query string
        variables: Optional variables for the GraphQL query
        token: Access token (will fetch a new one using client credentials if not provided)
        is_user_api: Whether to use the user API (for private data) or client API (for public data)
    
    Returns:
        Dict containing the GraphQL response
    
    Raises:
        requests.RequestException: If the API request fails
    """
    if token is None and not is_user_api:
        # Get a new token for client API if none provided
        token_data = get_client_credentials_token()
        token = token_data["access_token"]
    elif token is None and is_user_api:
        raise ValueError("Access token is required for user API requests")
    
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
    response.raise_for_status()
    
    return response.json()


def validate_token(token: str) -> bool:
    """
    Validate if a token is still valid by making a simple query.
    
    Args:
        token: Access token to validate
    
    Returns:
        Boolean indicating if the token is valid
    """
    try:
        # Simple query to test if the token works
        query = """
        query {
            worldData {
                expansions {
                    id
                    name
                }
            }
        }
        """
        
        response = execute_graphql_query(query, token=token)
        return "data" in response and response.get("data") is not None
    except requests.RequestException:
        return False


if __name__ == "__main__":
    # Example usage
    print("Warcraft Logs API Authentication Utility")
    print("----------------------------------------")
    
    try:
        # Get a client credentials token
        token_data = get_client_credentials_token()
        print(f"Successfully obtained access token: {token_data['access_token'][:10]}...")
        
        # Example of generating an authorization URL for PKCE flow
        redirect_uri = "http://localhost:8000/callback"
        auth_url, state_data = get_authorization_url(redirect_uri, use_pkce=True)
        print(f"\nAuthorization URL (PKCE flow):\n{auth_url}")
        print(f"\nState data to store in session:\n{json.dumps(state_data, indent=2)}")
        
        # Example GraphQL query with the token
        query = """
        query {
            worldData {
                expansions {
                    id
                    name
                }
            }
        }
        """
        
        result = execute_graphql_query(query, token=token_data["access_token"])
        print(f"\nExample API response:\n{json.dumps(result, indent=2)}")
        
    except requests.RequestException as e:
        print(f"Error: {e}")