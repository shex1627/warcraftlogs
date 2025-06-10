from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
import pandas as pd

from warcraftlogs.gear.get_item_level import get_item_level_bracket

@dataclass
class PlayerDetails:
    #spec_id: int
    name: str
    id: int # for a particular report
    spec_name: str
    role: str
    #class_id: int
    class_name: str
    item_level: float
    bracket: int

def get_player_details(client, report_code: str, fight_id: int, source_id: int=None) -> PlayerDetails:
    """Fetch player's spec, class and gear information
    
    player_details_resp['data']['reportData']['report']['playerDetails']
    {'data': {'playerDetails': {'tanks': [{'name': 'Ayysd',
     'id': 2,
     'guid': 243812747,
     'type': 'Druid',
     'server': 'Tichondrius',
     'region': 'US',
     'icon': 'Druid-Guardian',
     'specs': [{'spec': 'Guardian', 'count': 1}],
     'minItemLevel': 665,
     'maxItemLevel': 665,
     'potionUse': 0,
     'healthstoneUse': 0,
     'combatantInfo': []},
    
    """
    query = f"""
    {{
        reportData {{
            report(code: "{report_code}") {{
                playerDetails(fightIDs: [{fight_id}])
            }}
        }}
    }}
    """
    
    response = client.query_public_api(query)
    player_details = response['data']['reportData']['report']['playerDetails']
    
    if source_id is None:
        return player_details['data']['playerDetails']
    
    # Find the player in the response
    for role, players_in_role in player_details['data']['playerDetails'].items():
        for player in players_in_role:
            if player['id'] == source_id:
                #return player detail in the obj
                """{'name': 'Shunwalker',
 'id': 12,
 'guid': 242917295,
 'type': 'Paladin',
 'server': 'Tichondrius',
 'region': 'US',
 'icon': 'Paladin-Retribution',
 'specs': [{'spec': 'Retribution', 'count': 1}],
 'minItemLevel': 658,
 'maxItemLevel': 658,
 'potionUse': 0,
 'healthstoneUse': 0,
 'combatantInfo': []}
                """
                return PlayerDetails(
                    name=player['name'],
                    id=player['id'],
                    role=role,
                    spec_name=player['specs'][0]['spec'],
                    class_name=player['type'],
                    item_level=player['minItemLevel'],
                    bracket=get_item_level_bracket(player['minItemLevel'])
                )
    return None

def get_fight_info(client, report_code: str, fight_id: int) -> Dict:
    """Get fight/encounter information"""
    query = f"""
    {{
        reportData {{
            report(code: "{report_code}") {{
                fights(fightIDs: [{fight_id}]) {{
                    encounterID
                    name
                    difficulty
                    averageItemLevel
                    startTime
                    endTime
                    gameZone {{
                        id
                        name
                    }}
                }}
                zone {{
                    id
                    name
                }}
            }}
        }}
    }}
    """
    
    response = client.query_public_api(query)
    return response['data']['reportData']['report'] #['fights'][0]

def get_similar_players(client, encounter_id: int, spec_id: int, bracket: int, 
                       difficulty: int) -> List[Dict]:
    """Find top players with same spec and similar gear on the same encounter"""
    query = f"""
    {{
        reportData {{
            reports(encounterID: {encounter_id}) {{
                data {{
                    code
                    fights(difficulty: {difficulty}) {{
                        id
                        encounterID
                        startTime
                        endTime
                    }}
                }}
            }}
        }}
    }}
    """
    
    response = client.query_public_api(query)
    return response
    reports = response['data']['reportData']['reports']['data']
    
    similar_players = []
    for report in reports:
        # For each fight in the report that matches our encounter
        for fight in report['fights']:
            if fight['encounterID'] == encounter_id:
                # Get rankings for this fight
                rankings_query = f"""
                {{
                    reportData {{
                        report(code: "{report['code']}") {{
                            rankings(fightIDs: [{fight['id']}])
                        }}
                    }}
                }}
                """
                
                rankings = client.query_public_api(rankings_query)
                rankings_data = rankings['data']['reportData']['report']['rankings']
                
                # Filter for players with matching spec and bracket
                for player in rankings_data['data']:
                    if (player['spec']['id'] == spec_id and 
                        player['bracketData']['bracket'] == bracket):
                        similar_players.append({
                            'report_code': report['code'],
                            'fight_id': fight['id'],
                            'source_id': player['id'],
                            'dps': player.get('amount'),
                            'rank': player.get('rank'),
                            'percentile': player.get('percentile')
                        })
    
    return similar_players

def analyze_player_performance(client, report_code: str, fight_id: int, source_id: int):
    """Main function to analyze player performance against similar players"""
    
    # 1. Get player details
    player = get_player_details(client, report_code, fight_id, source_id)
    print(f"Analyzing {player.class_name} - {player.spec_name} (ilvl: {player.item_level}, bracket: {player.bracket})")
    
    # 2. Get fight info
    fight = get_fight_info(client, report_code, fight_id)
    print(f"Fight: {fight['name']} (Encounter ID: {fight['encounterID']}, Difficulty: {fight['difficulty']})")
    
    # 3. Find similar players
    similar = get_similar_players(
        client,
        encounter_id=fight['encounterID'],
        spec_id=player.spec_id,
        bracket=player.bracket,
        difficulty=fight['difficulty']
    )
    
    # 4. Convert to DataFrame for analysis
    if similar:
        df = pd.DataFrame(similar)
        print("\nTop similar players:")
        print(df.sort_values('percentile', ascending=False).head())
    else:
        print("No similar players found")

def example_usage(client):
    analyze_player_performance(
        client=client,
        report_code="your_report_code",
        fight_id=1,
        source_id=42
    ) 

def get_player_info(client, report_code, fight_id):
    """
    Get all player names, class and spec information for a specific fight in a report.
    
    Args:
        client: Object with query_public_api(query, variables) method
        report_code: String - The report code (e.g., "Wbcf3HZxjdrTyQqJ")
        fight_id: Integer - The fight ID within the report
    
    Returns:
        List of dictionaries containing player information:
        [
            {
                'name': 'PlayerName',
                'class': 'ClassName', 
                'spec': 'SpecName',
                'actor_id': 123,
                'type': 'Player',
                'server': 'ServerName',
                'role': 'Tank/Healer/DPS'
            }
        ]
    """
    
    # GraphQL query to get fight data and player details
    query = """
    query GetPlayerInfo($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                fights(fightIDs: [$fightId]) {
                    id
                    name
                    friendlyPlayers
                }
                playerDetails(fightIDs: [$fightId], includeCombatantInfo: true)
            }
        }
    }
    """
    
    variables = {
        "code": report_code,
        "fightId": fight_id
    }
    
    try:
        # Execute the query
        response = client.query_public_api(query, variables)
        
        if not response or 'data' not in response:
            raise Exception(f"Invalid response from API: {response}")
            
        report = response['data']['reportData']['report']
        
        if not report:
            raise Exception(f"Report not found: {report_code}")
            
        if not report['fights']:
            raise Exception(f"Fight {fight_id} not found in report {report_code}")
            
        player_details_data = report.get('playerDetails')
        
        if not player_details_data or 'data' not in player_details_data:
            raise Exception(f"No player details found for fight {fight_id}")
            
        # Extract player information from all roles
        players = []
        player_data = player_details_data['data']['playerDetails']
        
        # Process tanks
        for tank in player_data.get('tanks', []):
            spec_info = tank.get('specs', [{}])[0] if tank.get('specs') else {}
            player_info = {
                'name': tank.get('name', 'Unknown'),
                'class': tank.get('type', 'Unknown'),  # 'type' field contains the class
                'spec': spec_info.get('spec', 'Unknown'),
                'actor_id': tank.get('id'),
                'type': 'Player',
                'server': tank.get('server', 'Unknown'),
                'role': 'Tank'
            }
            players.append(player_info)
        
        # Process healers  
        for healer in player_data.get('healers', []):
            spec_info = healer.get('specs', [{}])[0] if healer.get('specs') else {}
            player_info = {
                'name': healer.get('name', 'Unknown'),
                'class': healer.get('type', 'Unknown'),
                'spec': spec_info.get('spec', 'Unknown'),
                'actor_id': healer.get('id'),
                'type': 'Player',
                'server': healer.get('server', 'Unknown'),
                'role': 'Healer'
            }
            players.append(player_info)
            
        # Process DPS
        for dps in player_data.get('dps', []):
            spec_info = dps.get('specs', [{}])[0] if dps.get('specs') else {}
            player_info = {
                'name': dps.get('name', 'Unknown'),
                'class': dps.get('type', 'Unknown'),
                'spec': spec_info.get('spec', 'Unknown'),
                'actor_id': dps.get('id'),
                'type': 'Player',
                'server': dps.get('server', 'Unknown'),
                'role': 'DPS'
            }
            players.append(player_info)
        
        return players
        
    except Exception as e:
        raise Exception(f"Error fetching player info: {str(e)}")
