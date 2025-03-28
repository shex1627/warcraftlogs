"""
Token management functionality for the Warcraft Logs API.

This module provides a TokenManager class that handles:
- In-memory token caching
- Persistent token storage
- Automatic token refresh before expiration
- Thread-safe access to tokens
"""

import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

from .auth import get_client_credentials_token, refresh_access_token


class TokenManager:
    """
    Manages OAuth tokens, handling storage, caching, automatic refresh, and expiration.
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
                try:
                    with open(token_path, 'w') as f:
                        json.dump({
                            "data": token_data,
                            "expires_at": expires_at
                        }, f)
                except (IOError, OSError) as e:
                    self.logger.warning(f"Failed to save token to {token_path}: {e}")
    
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
                if token_path and token_path.exists():
                    try:
                        with open(token_path, 'r') as f:
                            token_info = json.load(f)
                            # Check if token is still valid
                            if token_info["expires_at"] > time.time() + self.buffer_seconds:
                                # Cache in memory
                                self.tokens[token_key] = token_info
                                return token_info["data"]
                    except (json.JSONDecodeError, KeyError, IOError, OSError) as e:
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
                if token_path and token_path.exists():
                    try:
                        token_path.unlink()
                    except (IOError, OSError) as e:
                        self.logger.warning(f"Failed to delete token file {token_path}: {e}")
    
    def clear_all_tokens(self) -> None:
        """Clear all tokens from memory and disk."""
        with self.lock:
            # Clear memory
            self.tokens = {}
            
            # Clear disk
            if self.token_dir:
                try:
                    for token_file in self.token_dir.glob("*.json"):
                        token_file.unlink()
                except (IOError, OSError) as e:
                    self.logger.warning(f"Error clearing token directory: {e}")
