#!/usr/bin/env python3
"""
Example usage of the Warcraft Logs API client.
"""

import os
import json
import logging
from pathlib import Path

from warcraftlogs import WarcraftLogsClient
from warcraftlogs.constants import TOKEN_DIR

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create a token storage directory in user's home
    token_dir = os.path.expanduser(TOKEN_DIR)
    
    # Create client with persistent token storage
    client = WarcraftLogsClient(token_dir=token_dir)
    
    # Example: Query public API for game expansions
    print("Querying public API for game expansions...")
    try:
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
        
        result = client.query_public_api(query)
        expansions = result['data']['worldData']['expansions']
        
        print("Available expansions:")
        for exp in expansions:
            print(f"  - {exp['name']} (ID: {exp['id']})")
        
    except Exception as e:
        print(f"Error querying API: {e}")
    
    # Example: Generate authorization URL with PKCE
    print("\nGenerating authorization URL for user authorization...")
    redirect_uri = "http://localhost:8000/callback"
    
    try:
        auth_url, state_data = client.authorize_user(redirect_uri)
        
        print(f"Authorization URL:\n{auth_url}")
        print(f"\nState data to store in session:")
        print(json.dumps(state_data, indent=2))
        
        print("\nAfter authorization, call client.handle_callback(code, redirect_uri, code_verifier)")
        
    except Exception as e:
        print(f"Error generating auth URL: {e}")
    
    # Information about token management
    print("\nToken Management Information:")
    print("-----------------------------")
    print(f"1. Tokens are stored in: {token_dir}")
    print("2. Tokens are automatically refreshed before expiration")
    print("3. Use client.clear_tokens() to clear all stored tokens")


if __name__ == "__main__":
    main()