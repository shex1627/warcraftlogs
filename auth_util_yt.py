import requests
import os
import json

token_url = "https://warcraftlogs.com/oauth/token"
client_id = os.getenv("WARCRAFTLOGS_CLIENT_ID", "9e88c213-bde4-4e0d-b005-86e96d73cb48")
client_secret = os.getenv("WARCRAFTLOGS_CLIENT_SECRET", "49wPdfRm09dWC7Id5Pxp9tZMUMV3OQpmPb0kYILL")
print(f"Client ID: {client_id}")
print(f"Client Secret: {client_secret}")

def get_token(store: bool = True):
    data = {"grant_type": "client_credentials"}
    auth = (client_id, client_secret)
    with requests.Session() as session: 
        response = session.post(token_url, data=data, auth=auth)
    if store and response.status_code == 200:
        store_token(response)
    return response

def store_token(response):
    """Store the token in a file for later use."""
    try:
        with open("warcraftlogs_token.json", "w+", encoding="utf-8") as f:
            json.dump(response.json(), f, ensure_ascii=False, indent=4)
    except OSError as e:
        print(f"Error storing token: {e}")
        return None 
    
def main():
    response = get_token()
    print(f"Response status code: {response}")


if __name__ == "__main__":
    main()