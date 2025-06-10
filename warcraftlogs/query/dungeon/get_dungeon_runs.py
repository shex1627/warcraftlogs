from warcraftlogs.query.fight import get_fight_duration
from warcraftlogs.utils import format_number
from warcraftlogs.gear.get_item_level import get_item_level_bracket

def get_role_from_class_spec(class_name, spec_name):
    """
    Determine role from class and spec combination.
    """
    # Tank specs
    tank_specs = {
        'Death Knight': ['Blood'],
        'Druid': ['Guardian'],
        'Monk': ['Brewmaster'],
        'Paladin': ['Protection'],
        'Warrior': ['Protection'],
        'Demon Hunter': ['Vengeance']
    }
    
    # Healer specs
    healer_specs = {
        'Druid': ['Restoration'],
        'Monk': ['Mistweaver'],
        'Paladin': ['Holy'],
        'Priest': ['Discipline', 'Holy'],
        'Shaman': ['Restoration'],
        'Evoker': ['Preservation']
    }
    
    # Check if tank
    if class_name in tank_specs and spec_name in tank_specs[class_name]:
        return 'Tank'
    
    # Check if healer
    if class_name in healer_specs and spec_name in healer_specs[class_name]:
        return 'Healer'
    
    # Check if support DPS (Augmentation Evoker)
    if class_name == 'Evoker' and spec_name == 'Augmentation':
        return 'Support DPS'
    
    # Check if melee or ranged DPS
    melee_specs = {
        'Death Knight': ['Frost', 'Unholy'],
        'Druid': ['Feral'],
        'Hunter': ['Survival'],
        'Monk': ['Windwalker'],
        'Paladin': ['Retribution'],
        'Rogue': ['Assassination', 'Outlaw', 'Subtlety'],
        'Shaman': ['Enhancement'],
        'Warrior': ['Arms', 'Fury'],
        'Demon Hunter': ['Havoc']
    }
    
    if class_name in melee_specs and spec_name in melee_specs[class_name]:
        return 'Melee DPS'
    
    # Everything else is ranged DPS
    return 'Ranged DPS'

def get_damage_healing_data(client, report_code, fight_id, debug=False):
    """
    Get damage and healing data for all players in a fight.
    
    Args:
        client: Object with query_public_api method
        report_code: String - The report code
        fight_id: Integer - The fight ID
    
    Returns:
        Dictionary mapping player names to their damage/healing totals and metadata:
        {
            'PlayerName': {
                'damage': 1234567,
                'healing': 89012,
                'class': 'Warrior',
                'spec': 'Protection',
                'item_level': 659
            }
        }
    """
    
    # Query for damage done data
    damage_query = """
    query GetDamageData($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                table(
                    dataType: DamageDone
                    fightIDs: [$fightId]
                    hostilityType: Friendlies
                )
            }
        }
    }
    """
    
    # Query for healing done data  
    healing_query = """
    query GetHealingData($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                table(
                    dataType: Healing
                    fightIDs: [$fightId]
                    hostilityType: Friendlies
                )
            }
        }
    }
    """
    
    variables = {"code": report_code, "fightId": fight_id}
    
    result = {}
    
    try:
        # Get damage data
        damage_result = client.query_public_api(damage_query, variables)
        damage_table = damage_result.get('data', {}).get('reportData', {}).get('report', {}).get('table', {})
        
        if damage_table and 'data' in damage_table and 'entries' in damage_table['data']:
            for entry in damage_table['data']['entries']:
                player_name = entry.get('name')
                total_damage = entry.get('total', 0)
                item_level = entry.get('itemLevel', 0)
                player_type = entry.get('type', '')
                icon = entry.get('icon', '')
                
                # Skip NPCs and invalid entries
                if not player_name or player_type == 'NPC' or not player_type:
                    continue
                
                if player_name not in result:
                    result[player_name] = {
                        'damage': 0, 
                        'healing': 0,
                        'class': player_type,
                        'spec': '',
                        'item_level': item_level
                    }
                result[player_name]['damage'] = total_damage
                result[player_name]['item_level'] = item_level
                result[player_name]['class'] = player_type
                
                # Extract spec from icon (e.g., "Paladin-Protection" -> "Protection")
                if '-' in icon:
                    spec = icon.split('-')[1]
                    result[player_name]['spec'] = spec
                
                # Debug print
                if debug:
                    print(f"Damage - {player_name}: {total_damage:,} damage, {player_type}, {icon}")
        
        # Get healing data
        healing_result = client.query_public_api(healing_query, variables)
        healing_table = healing_result.get('data', {}).get('reportData', {}).get('report', {}).get('table', {})
        
        if healing_table and 'data' in healing_table and 'entries' in healing_table['data']:
            for entry in healing_table['data']['entries']:
                player_name = entry.get('name')
                total_healing = entry.get('total', 0)
                item_level = entry.get('itemLevel', 0)
                player_type = entry.get('type', '')
                icon = entry.get('icon', '')
                
                # Skip NPCs and invalid entries
                if not player_name or player_type == 'NPC' or not player_type:
                    continue
                
                if player_name not in result:
                    result[player_name] = {
                        'damage': 0, 
                        'healing': 0,
                        'class': player_type,
                        'spec': '',
                        'item_level': item_level
                    }
                result[player_name]['healing'] = total_healing
                
                # Fill in missing data if we didn't get it from damage table
                if not result[player_name]['item_level']:
                    result[player_name]['item_level'] = item_level
                if not result[player_name]['class']:
                    result[player_name]['class'] = player_type
                if not result[player_name]['spec'] and '-' in icon:
                    spec = icon.split('-')[1]
                    result[player_name]['spec'] = spec
                
                # Debug print
                if debug:
                    print(f"Healing - {player_name}: {total_healing:,} healing, {player_type}, {icon}")
                    
    except Exception as e:
        print(f"Error getting damage/healing data: {e}")
        import traceback
        traceback.print_exc()
    
    #
    if debug:
        print(f"Final result keys: {list(result.keys())}")
        for name, data in result.items():
            print(f"{name}: damage={data['damage']}, healing={data['healing']}, class={data['class']}, spec={data['spec']}")
    
    return result

def get_mythic_plus_runs(client, dungeon_name, keystone_level, page=1, include_dps_hps=True, max_reports=None, class_filter=None, spec_filter=None):
    """
    Query Warcraft Logs for mythic+ dungeon runs and return detailed player information.
    
    Args:
        client: Object with query_public_api(query, variables) method
        dungeon_name: String - Name of the dungeon (e.g., "Cinderbrew Meadery")
        keystone_level: Integer - Keystone level to filter (e.g., 10)
        page: Integer - Page number for pagination (default: 1)
        include_dps_hps: Boolean - Whether to calculate DPS/HPS (requires extra queries, default: True)
        max_reports: Integer - Maximum number of reports to process (optional)
        class_filter: String - Optional class filter (e.g., "Warrior", "Priest")
        spec_filter: String - Optional spec filter (e.g., "Protection", "Holy")
    
    Returns:
        List of dictionaries containing run information:
        [
            {
                'report_id': 'ABC123',
                'fight_id': 1,
                'bracket': 10,
                'encounter_id': 12661,  # Example encounter ID for Cinderbrew Meadery
                'datetime': '2025-07-07 14:30:45',
                'players': [
                    {
                        'class': 'Warrior',
                        'spec': 'Protection', 
                        'character_name': 'PlayerName',
                        'avg_item_level': 659.5,
                        'item_level_bracket': 9,
                        'dps': 12345.67,  # Only if include_dps_hps=True
                        'hps': 890.12,    # Only if include_dps_hps=True
                        'role': 'Tank'
                    },
                    # ... more players
                ]
            },
            # ... more runs
        ]
    """
    
    # Dungeon name to encounter ID mapping
    dungeon_encounters = {
        "Cinderbrew Meadery": 12661,
        "Darkflame Cleft": 12651,
        "Operation: Floodgate": 12773,
        "Operation: Mechagon - Workshop": 112098,
        "Priory of the Sacred Flame": 12649,
        "The MOTHERLODE!!": 61594,
        "The Rookery": 12648,
        "Theater of Pain": 62293
    }
    
    encounter_id = dungeon_encounters.get(dungeon_name)
    if not encounter_id:
        raise ValueError(f"Unknown dungeon: {dungeon_name}. Available dungeons: {list(dungeon_encounters.keys())}")
    
    # Build the rankings query with optional class/spec filters
    if class_filter or spec_filter:
        rankings_query = """
        query GetMythicPlusRuns($encounterId: Int!, $bracket: Int!, $page: Int!, $className: String, $specName: String) {
            worldData {
                encounter(id: $encounterId) {
                    characterRankings(
                        bracket: $bracket
                        page: $page
                        metric: playerscore
                        leaderboard: LogsOnly
                        className: $className
                        specName: $specName
                    )
                }
            }
        }
        """
        variables = {
            "encounterId": encounter_id,
            "bracket": keystone_level,
            "page": page,
            "className": class_filter,
            "specName": spec_filter
        }
    else:
        rankings_query = """
        query GetMythicPlusRuns($encounterId: Int!, $bracket: Int!, $page: Int!) {
            worldData {
                encounter(id: $encounterId) {
                    characterRankings(
                        bracket: $bracket
                        page: $page
                        metric: playerscore
                        leaderboard: LogsOnly
                    )
                }
            }
        }
        """
        variables = {
            "encounterId": encounter_id,
            "bracket": keystone_level,
            "page": page
        }
    
    try:
        rankings_result = client.query_public_api(rankings_query, variables)
        rankings_data = rankings_result.get('data', {}).get('worldData', {}).get('encounter', {}).get('characterRankings', {}).get('rankings', [])
        
        if not rankings_data:
            return []
        
        # Group rankings by report+fight to avoid duplicates
        runs_dict = {}
        for ranking in rankings_data:
            report_info = ranking.get('report', {})
            report_code = report_info.get('code')
            fight_id = report_info.get('fightID')
            run_start_time = ranking.get('startTime', 0)  # Timestamp in milliseconds
            
            if not report_code or not fight_id:
                continue
                
            run_key = f"{report_code}_{fight_id}"
            if run_key not in runs_dict:
                runs_dict[run_key] = {
                    'report_id': report_code,
                    'fight_id': fight_id,
                    'bracket': keystone_level,
                    'encounter_id': encounter_id,
                    'start_time': run_start_time,
                    'players': [],
                    'ranking_players': []
                }
            
            # Store the ranking player info for later processing
            runs_dict[run_key]['ranking_players'].append(ranking)
        
        result_runs = []
        
        # Process each unique run
        if max_reports is not None:
            runs_dict = dict(list(runs_dict.items())[:max_reports])
        for run_data in runs_dict.values():
            report_code = run_data['report_id']
            fight_id = run_data['fight_id']
            start_time = run_data['start_time']

            try:
                # Convert timestamp to datetime string
                from datetime import datetime
                datetime_str = datetime.fromtimestamp(start_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                # Get damage and healing data which includes all players, item levels, and roles
                damage_healing_data = get_damage_healing_data(client, report_code, fight_id)
                #print(f"damage healing_data: {damage_healing_data}")
                
                # Get fight duration for DPS/HPS calculations (only if needed)
                fight_duration = None
                if include_dps_hps:
                    fight_duration = get_fight_duration(client, report_code, fight_id)
                
                # Build player list with all required information
                players = []
                for player_name, data in damage_healing_data.items():
                    # Get role from class/spec mapping
                    player_class = data.get('class', 'Unknown')
                    player_spec = data.get('spec', 'Unknown')
                    role = get_role_from_class_spec(player_class, player_spec)
                    
                    avg_item_level = data.get('item_level', 0)
                    
                    raw_dps = data.get('damage', 0)/fight_duration if fight_duration else 0
                    raw_hps = data.get('healing', 0)/fight_duration if fight_duration else 0

                    player_info = {
                        'class': player_class,
                        'spec': player_spec,
                        'character_name': player_name,
                        'avg_item_level': avg_item_level,
                        'item_level_bracket': get_item_level_bracket(avg_item_level),
                        'raw_dps': raw_dps,
                        'raw_hps': raw_hps,
                        'dps': format_number(raw_dps, 1),
                        'hps': format_number(raw_hps, 1),
                        'role': role
                    }
                    players.append(player_info)
                
                run_result = {
                    'report_id': report_code,
                    'fight_id': fight_id,
                    'bracket': keystone_level,
                    'datetime': datetime_str,
                    'encounter_id': encounter_id,
                    'players': players
                }
                
                result_runs.append(run_result)
                
            except Exception as e:
                print(f"Error processing run {report_code}#{fight_id}: {e}")
                continue
        
        return result_runs
        
    except Exception as e:
        print(f"Error querying mythic+ runs: {e}")
        return []


def get_damage_healing_data(client, report_code, fight_id, debug=False):
    """
    Get damage and healing data for all players in a fight.
    
    Args:
        client: Object with query_public_api method
        report_code: String - The report code
        fight_id: Integer - The fight ID
    
    Returns:
        Dictionary mapping player names to their damage/healing totals and metadata:
        {
            'PlayerName': {
                'damage': 1234567,
                'healing': 89012,
                'class': 'Warrior',
                'spec': 'Protection',
                'item_level': 659
            }
        }
    """
    
    # Query for damage done data
    damage_query = """
    query GetDamageData($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                table(
                    dataType: DamageDone
                    fightIDs: [$fightId]
                    hostilityType: Friendlies
                )
            }
        }
    }
    """
    
    # Query for healing done data  
    healing_query = """
    query GetHealingData($code: String!, $fightId: Int!) {
        reportData {
            report(code: $code) {
                table(
                    dataType: Healing
                    fightIDs: [$fightId]
                    hostilityType: Friendlies
                )
            }
        }
    }
    """
    
    variables = {"code": report_code, "fightId": fight_id}
    
    result = {}
    
    try:
        # Get damage data
        damage_result = client.query_public_api(damage_query, variables)
        damage_table = damage_result.get('data', {}).get('reportData', {}).get('report', {}).get('table', {})
        
        if damage_table and 'data' in damage_table and 'entries' in damage_table['data']:
            for entry in damage_table['data']['entries']:
                player_name = entry.get('name')
                total_damage = entry.get('total', 0)
                item_level = entry.get('itemLevel', 0)
                player_type = entry.get('type', '')
                icon = entry.get('icon', '')
                
                # Skip NPCs and invalid entries
                if not player_name or player_type == 'NPC' or not player_type:
                    continue
                
                if player_name not in result:
                    result[player_name] = {
                        'damage': 0, 
                        'healing': 0,
                        'class': player_type,
                        'spec': '',
                        'item_level': item_level
                    }
                result[player_name]['damage'] = total_damage
                result[player_name]['item_level'] = item_level
                result[player_name]['class'] = player_type
                
                # Extract spec from icon (e.g., "Paladin-Protection" -> "Protection")
                if '-' in icon:
                    spec = icon.split('-')[1]
                    result[player_name]['spec'] = spec
                
                # Debug print
                if debug:
                    print(f"Damage - {player_name}: {total_damage:,} damage, {player_type}, {icon}")
        
        # Get healing data
        healing_result = client.query_public_api(healing_query, variables)
        healing_table = healing_result.get('data', {}).get('reportData', {}).get('report', {}).get('table', {})
        
        if healing_table and 'data' in healing_table and 'entries' in healing_table['data']:
            for entry in healing_table['data']['entries']:
                player_name = entry.get('name')
                total_healing = entry.get('total', 0)
                item_level = entry.get('itemLevel', 0)
                player_type = entry.get('type', '')
                icon = entry.get('icon', '')
                
                # Skip NPCs and invalid entries
                if not player_name or player_type == 'NPC' or not player_type:
                    continue
                
                if player_name not in result:
                    result[player_name] = {
                        'damage': 0, 
                        'healing': 0,
                        'class': player_type,
                        'spec': '',
                        'item_level': item_level
                    }
                result[player_name]['healing'] = total_healing
                
                # Fill in missing data if we didn't get it from damage table
                if not result[player_name]['item_level']:
                    result[player_name]['item_level'] = item_level
                if not result[player_name]['class']:
                    result[player_name]['class'] = player_type
                if not result[player_name]['spec'] and '-' in icon:
                    spec = icon.split('-')[1]
                    result[player_name]['spec'] = spec
                
                # Debug print
                if debug:
                    print(f"Healing - {player_name}: {total_healing:,} healing, {player_type}, {icon}")
                    
    except Exception as e:
        print(f"Error getting damage/healing data: {e}")
        import traceback
        traceback.print_exc()
    
    #
    if debug:
        print(f"Final result keys: {list(result.keys())}")
        for name, data in result.items():
            print(f"{name}: damage={data['damage']}, healing={data['healing']}, class={data['class']}, spec={data['spec']}")
    
    return result
