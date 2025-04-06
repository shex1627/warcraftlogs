from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
import pandas as pd

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

def get_item_level_bracket(item_level: float) -> int:
    """Convert item level to bracket number (1-17)"""
    bracket_ranges = [
        (633, 635), (636, 638), (639, 641), (642, 644),
        (645, 647), (648, 650), (651, 653), (654, 656),
        (657, 659), (660, 662), (663, 665), (666, 668),
        (669, 671), (672, 674), (675, 677), (678, 680)
    ]
    
    for i, (min_ilvl, max_ilvl) in enumerate(bracket_ranges, 1):
        if min_ilvl <= item_level <= max_ilvl:
            return i
    return 17 if item_level > 680 else 1

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
        return player_details
    
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
    print(query)
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