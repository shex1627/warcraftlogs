#!/usr/bin/env python3
"""
Warcraft Logs API Authentication Utility

This module provides utility functions for authenticating with the Warcraft Logs API
using different OAuth 2.0 flows as described in the Warcraft Logs API documentation.
Includes token management for caching and refreshing tokens automatically.
"""

import os
import base64
import hashlib
import secrets
import string
import requests
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any, Union, Callable
from urllib.parse import urlencode
from pathlib import Path

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
                         token: Optional[str] = None, is_user_api: bool = False,
                         refresh_token: Optional[str] = None, user_id: str = "default",
                         token_manager: Optional[TokenManager] = None) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Warcraft Logs API.
    
    Args:
        query: The GraphQL query string
        variables: Optional variables for the GraphQL query
        token: Access token (will fetch a new one if not provided)
        is_user_api: Whether to use the user API (for private data) or client API (for public data)
        refresh_token: Optional refresh token for automatic token refresh
        user_id: Identifier for the user when using refresh tokens
        token_manager: Optional custom token manager instance
    
    Returns:
        Dict containing the GraphQL response
    
    Raises:
        requests.RequestException: If the API request fails
        ValueError: If no token is provided for user API requests
    """
    manager = token_manager or default_token_manager
    
    if token is None:
        if is_user_api and not refresh_token:
            raise ValueError("Either access token or refresh token is required for user API requests")
        
        # Get token from manager
        token = get_access_token(refresh_token, user_id, manager)
    
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
    if response.status_code == 401 and refresh_token:
        # Token might be expired, try to refresh and retry
        manager.clear_token("user_{user_id}" if is_user_api else "client_credentials")
        new_token = get_access_token(refresh_token, user_id, manager)
        
        # Update headers with new token
        headers["Authorization"] = f"Bearer {new_token}"
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


class TokenManager:
    """
    Manages OAuth tokens, handling storage, caching, automatic refresh, and expiration.
    
    This class provides:
    - In-memory token caching
    - Optional persistent token storage
    - Automatic token refresh before expiration
    - Thread-safe access to tokens
    """
    
    def __init__(self, token_dir: Optional[str] = None, buffer_seconds: int = 300):
        """
        Initialize the token manager.
        
        Args:
            token_dir: Directory to store token files persistently (None for in-memory only)
            buffer_seconds: Seconds before expiration to trigger a refresh (default: 5 minutes)
        """
        self.tokens = {}  # In-memory token cache
        self.token_dir = Path(token_dir) if token_dir else None
        self.buffer_seconds = buffer_seconds
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.logger = logging.getLogger(__name__)
        
        # Create token directory if it doesn't exist
        if self.token_dir and not self.token_dir.exists():
            self.token_dir.mkdir(parents=True)
    
    def _get_token_path(self, token_key: str) -> Optional[Path]:
        """Get the path to a token file."""
        if not self.token_dir:
            return None
        return self.token_dir / f"{token_key}.json"
    
    def save_token(self, token_key: str, token_data: Dict[str, Any]) -> None:
        """
        Save a token to memory and optionally to disk.
        
        Args:
            token_key: Unique identifier for the token
            token_data: Token response from OAuth server
        """
        with self.lock:
            # Calculate expiration time
            expires_at = time.time() + token_data.get("expires_in", 3600)
            
            # Store token with expiration time
            self.tokens[token_key] = {
                "data": token_data,
                "expires_at": expires_at
            }
            
            # Save to disk if enabled
            if self.token_dir:
                token_path = self._get_token_path(token_key)
                with open(token_path, 'w') as f:
                    json.dump({
                        "data": token_data,
                        "expires_at": expires_at
                    }, f)
    
    def load_token(self, token_key: str) -> Optional[Dict[str, Any]]:
        """
        Load a token from memory or disk.
        
        Args:
            token_key: Unique identifier for the token
        
        Returns:
            Token data dict or None if not found or expired
        """
        with self.lock:
            # Check memory cache first
            if token_key in self.tokens:
                token_info = self.tokens[token_key]
                # Return if not expired (accounting for buffer)
                if token_info["expires_at"] > time.time() + self.buffer_seconds:
                    return token_info["data"]
            
            # Try loading from disk if enabled
            if self.token_dir:
                token_path = self._get_token_path(token_key)
                if token_path.exists():
                    try:
                        with open(token_path, 'r') as f:
                            token_info = json.load(f)
                            # Check if token is still valid
                            if token_info["expires_at"] > time.time() + self.buffer_seconds:
                                # Cache in memory
                                self.tokens[token_key] = token_info
                                return token_info["data"]
                    except (json.JSONDecodeError, KeyError) as e:
                        self.logger.warning(f"Error loading token from {token_path}: {e}")
            
            return None
    
    def get_client_token(self) -> str:
        """
        Get a client credentials token, refreshing if necessary.
        
        Returns:
            Access token string
        """
        token_key = "client_credentials"
        
        with self.lock:
            # Try to load existing token
            token_data = self.load_token(token_key)
            
            # If no valid token, get a new one
            if not token_data:
                token_data = get_client_credentials_token()
                self.save_token(token_key, token_data)
            
            return token_data["access_token"]
    
    def get_user_token(self, refresh_token: str, user_id: str = "default") -> str:
        """
        Get a user token, refreshing if necessary.
        
        Args:
            refresh_token: Refresh token to use if needed
            user_id: Unique identifier for the user (default: "default")
        
        Returns:
            Access token string
        """
        token_key = f"user_{user_id}"
        
        with self.lock:
            # Try to load existing token
            token_data = self.load_token(token_key)
            
            # If no valid token, refresh it
            if not token_data:
                token_data = refresh_access_token(refresh_token)
                self.save_token(token_key, token_data)
            
            return token_data["access_token"]
    
    def clear_token(self, token_key: str) -> None:
        """
        Remove a token from memory and disk.
        
        Args:
            token_key: Unique identifier for the token
        """
        with self.lock:
            # Remove from memory
            if token_key in self.tokens:
                del self.tokens[token_key]
            
            # Remove from disk
            if self.token_dir:
                token_path = self._get_token_path(token_key)
                if token_path.exists():
                    token_path.unlink()
    
    def clear_all_tokens(self) -> None:
        """Clear all tokens from memory and disk."""
        with self.lock:
            # Clear memory
            self.tokens = {}
            
            # Clear disk
            if self.token_dir:
                for token_file in self.token_dir.glob("*.json"):
                    token_file.unlink()


# Create a default token manager instance
default_token_manager = TokenManager()


def get_access_token(refresh_token: Optional[str] = None, user_id: str = "default",
                    token_manager: Optional[TokenManager] = None) -> str:
    """
    Convenience function to get an appropriate access token.
    Uses client credentials flow if no refresh token provided,
    otherwise uses the refresh token.
    
    Args:
        refresh_token: Optional refresh token for user-specific access
        user_id: Identifier for the user when using refresh tokens
        token_manager: Optional custom token manager instance
    
    Returns:
        Access token string
    """
    manager = token_manager or default_token_manager
    
    if refresh_token:
        return manager.get_user_token(refresh_token, user_id)
    else:
        return manager.get_client_token()


class WarcraftLogsClient:
    """
    Client for interacting with the Warcraft Logs API.
    
    This class wraps the token management and API calls in a simple interface.
    """
    
    def __init__(self, token_dir: Optional[str] = None, 
                buffer_seconds: int = 300,
                custom_client_id: Optional[str] = None,
                custom_client_secret: Optional[str] = None):
        """
        Initialize the Warcraft Logs client.
        
        Args:
            token_dir: Directory to store token files persistently (None for in-memory only)
            buffer_seconds: Seconds before expiration to trigger a refresh
            custom_client_id: Optional custom client ID (uses module default if None)
            custom_client_secret: Optional custom client secret (uses module default if None)
        """
        self.token_manager = TokenManager(token_dir, buffer_seconds)
        
        # Override module defaults if provided
        global client_id, client_secret
        
        if custom_client_id:
            client_id = custom_client_id
        
        if custom_client_secret:
            client_secret = custom_client_secret
    
    def query_public_api(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a query against the public API.
        Automatically handles token management.
        
        Args:
            query: GraphQL query string
            variables: Optional variables for the query
            
        Returns:
            Dict containing the GraphQL response
        """
        return execute_graphql_query(
            query=query,
            variables=variables,
            is_user_api=False,
            token_manager=self.token_manager
        )
    
    def query_user_api(self, query: str, variables: Optional[Dict[str, Any]] = None, 
                      refresh_token: str = None, user_id: str = "default",
                      token: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a query against the user API.
        Requires either a token or refresh token.
        
        Args:
            query: GraphQL query string
            variables: Optional variables for the query
            refresh_token: Refresh token for automatic token renewal
            user_id: Identifier for the user
            token: Direct access token (will not be refreshed if expired)
            
        Returns:
            Dict containing the GraphQL response
        """
        return execute_graphql_query(
            query=query,
            variables=variables,
            is_user_api=True,
            refresh_token=refresh_token,
            user_id=user_id,
            token=token,
            token_manager=self.token_manager
        )
    
    def authorize_user(self, redirect_uri: str, use_pkce: bool = True) -> Tuple[str, Dict[str, str]]:
        """
        Generate an authorization URL for user authorization.
        
        Args:
            redirect_uri: The URI to redirect to after authorization
            use_pkce: Whether to use PKCE flow (recommended for public clients)
            
        Returns:
            Tuple of (authorization_url, state_data)
        """
        return get_authorization_url(redirect_uri, use_pkce=use_pkce)
    
    def handle_callback(self, code: str, redirect_uri: str, 
                       code_verifier: Optional[str] = None, 
                       user_id: str = "default") -> Dict[str, Any]:
        """
        Handle the callback from the authorization server.
        
        Args:
            code: The authorization code from the callback
            redirect_uri: The redirect URI used in the authorization request
            code_verifier: The code verifier (required for PKCE flow)
            user_id: Identifier for the user
            
        Returns:
            Dict containing the token response
        """
        token_data = exchange_code_for_token(code, redirect_uri, code_verifier)
        
        # Save the token
        if "refresh_token" in token_data:
            token_key = f"user_{user_id}"
            self.token_manager.save_token(token_key, token_data)
        
        return token_data
    
    def clear_tokens(self):
        """Clear all stored tokens."""
        self.token_manager.clear_all_tokens()


if __name__ == "__main__":
    # Example usage
    print("Warcraft Logs API Authentication Utility")
    print("----------------------------------------")
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Example token storage directory in user's home directory
    token_dir = os.path.expanduser("~/.warcraftlogs/tokens")
    
    try:
        # Create a client with persistent token storage
        client = WarcraftLogsClient(token_dir=token_dir)
        
        # Public API example
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
        
        print("Querying public API...")
        result = client.query_public_api(query)
        print(f"Expansions: {', '.join([exp['name'] for exp in result['data']['worldData']['expansions']])}")
        
        # Generate authorization URL example
        redirect_uri = "http://localhost:8000/callback"
        auth_url, state_data = client.authorize_user(redirect_uri)
        print(f"\nAuthorization URL (PKCE flow):\n{auth_url}")
        print(f"\nState data to store in session:\n{json.dumps(state_data, indent=2)}")
        
        print("\nToken Management Example:")
        print("-------------------------")
        print("1. Tokens are automatically cached in memory")
        print("2. Tokens are persistently stored in:", token_dir)
        print("3. Tokens are automatically refreshed before expiration")
        print("4. Use client.clear_tokens() to clear all stored tokens")
        
    except requests.RequestException as e:
        print(f"Error: {e}")