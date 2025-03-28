"""
High-level client interface for the Warcraft Logs API.

This module provides a client class that wraps all functionality in a convenient interface.
"""

import os
import logging
from typing import Dict, Tuple, Optional, Any

from . import CLIENT_ID, CLIENT_SECRET
from .token_manager import TokenManager
from .auth import get_authorization_url, exchange_code_for_token
from .api import execute_graphql_query


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
        global CLIENT_ID, CLIENT_SECRET
        
        if custom_client_id:
            CLIENT_ID = custom_client_id
        
        if custom_client_secret:
            CLIENT_SECRET = custom_client_secret
    
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
