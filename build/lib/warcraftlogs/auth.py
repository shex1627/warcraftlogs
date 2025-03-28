"""
Authentication functions for the Warcraft Logs API.

This module provides functions for different OAuth 2.0 flows:
- Client Credentials Flow
- Authorization Code Flow
- PKCE Code Flow
"""

import requests
from typing import Dict, Tuple, Optional, Any
from urllib.parse import urlencode

from . import CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URI, TOKEN_URI
from .utils import generate_pkce_verifier_and_challenge, generate_random_state


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
    auth = (CLIENT_ID, CLIENT_SECRET)
    data = {"grant_type": "client_credentials"}
    
    response = requests.post(TOKEN_URI, auth=auth, data=data)
    response.raise_for_status()
    
    return response.json()


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
        state = generate_random_state()
    
    params = {
        "client_id": CLIENT_ID,
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
        data["client_id"] = CLIENT_ID
        data["code_verifier"] = code_verifier
        response = requests.post(TOKEN_URI, data=data)
    else:
        # Standard authorization code flow
        auth = (CLIENT_ID, CLIENT_SECRET)
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
    auth = (CLIENT_ID, CLIENT_SECRET)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    response = requests.post(TOKEN_URI, auth=auth, data=data)
    response.raise_for_status()
    
    return response.json()


def validate_token(token: str, query_fn) -> bool:
    """
    Validate if a token is still valid by making a simple query.
    
    Args:
        token: Access token to validate
        query_fn: Function to execute a GraphQL query
        
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
        
        response = query_fn(query, token=token)
        return "data" in response and response.get("data") is not None
    except requests.RequestException:
        return False