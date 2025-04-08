import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional
import pandas as pd
from tqdm.notebook import tqdm
import requests
from bs4 import BeautifulSoup

class AbilityDataManager:
    def __init__(self, client, cache_file: str = "ability_cache.json", max_workers: int = 5, batch_size: int = 50):
        """
        Initialize the ability data manager
        
        Parameters:
        -----------
        client : WarcraftLogsClient
            Client instance for querying the API
        cache_file : str
            Path to store the ability data cache
        max_workers : int
            Maximum number of parallel threads for querying
        batch_size : int
            Number of abilities to query in each batch
        """
        self.client = client
        self.cache_file = Path(cache_file)
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.ability_cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load the ability cache from disk if it exists"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save the current ability cache to disk"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.ability_cache, f)

    def _query_single_ability(self, ability_id: int) -> Dict:
        """Query a single ability from the API and WoWHead"""
        # First query WarcraftLogs API
        query = {
            "query": """
            {
                gameData {
                    ability(id: %d) {
                        id
                        name
                        icon
                    }
                }
            }
            """ % ability_id
        }
        
        ability_data = {}
        
        # Get API data
        response = self.client.query_public_api(**query)
        api_data = response.get('data', {}).get('gameData', {}).get('ability')
        if api_data:
            ability_data.update(api_data)
        
        # Get WoWHead tooltip data
        try:
            spell_url = f"https://www.wowhead.com/spell={ability_id}"
            response = requests.get(spell_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Get tooltip description
                spell_links = soup.find_all(attrs={'class': 'q'})
                if spell_links:
                    ability_data['description'] = spell_links[0].text.strip()
                
                # # Update name if not found from API
                # if not ability_data.get('name'):
                #     title_elem = soup.find('h1', {'class': 'heading-size-1'})
                #     if title_elem:
                #         ability_data['name'] = title_elem.text.strip()
                    
        except Exception as e:
            print(f"Error fetching WoWHead data for ability {ability_id}: {e}")
        
        if ability_data:
            ability_data['id'] = str(ability_id)  # Ensure ID is string for JSON
            return ability_data
        return None

    def _query_ability_batch(self, ability_ids: List[int]) -> Dict[int, Dict]:
        """Query a batch of abilities and return results with tooltips"""
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._query_single_ability, aid): aid 
                      for aid in ability_ids}
            
            for future in futures:
                ability_id = futures[future]
                try:
                    result = future.result()
                    if result:
                        results[ability_id] = result
                except Exception as e:
                    print(f"Error querying ability {ability_id}: {e}")
        
        return results

    def get_abilities(self, ability_ids: List[int], refresh: bool = False) -> pd.DataFrame:
        """
        Get ability data for a list of ability IDs
        
        Parameters:
        -----------
        ability_ids : List[int]
            List of ability IDs to fetch
        refresh : bool
            If True, force refresh cache for these abilities
            
        Returns:
        --------
        pd.DataFrame
            DataFrame containing ability data
        """
        # Convert to strings for JSON compatibility
        ability_ids = [str(aid) for aid in ability_ids]
        
        # Find which abilities need to be queried
        missing_ids = [aid for aid in ability_ids 
                      if aid not in self.ability_cache or refresh]
        
        if missing_ids:
            # Split into batches
            batches = [missing_ids[i:i + self.batch_size] 
                      for i in range(0, len(missing_ids), self.batch_size)]
            
            # Query each batch
            for batch in tqdm(batches, desc="Querying abilities"):
                results = self._query_ability_batch([int(aid) for aid in batch])
                
                # Update cache
                for aid, data in results.items():
                    self.ability_cache[str(aid)] = data
            
            # Save updated cache
            self._save_cache()
        
        # Convert cache to DataFrame
        data = [self.ability_cache[aid] for aid in ability_ids if aid in self.ability_cache]
        return pd.DataFrame(data)
    