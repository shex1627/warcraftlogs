import requests
import json
from typing import Optional, Dict, List, Any, Union
import warcraftlogs
from warcraftlogs.constants import TOKEN_DIR

from warcraftlogs import WarcraftLogsClient

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

def get_item_level_bracket(item_level):
    """
    Convert item level to bracket number for categorization.
    
    Args:
        item_level: Float - The average item level
    
    Returns:
        Integer - Bracket number (1-10+ scale)
    """
    if item_level < 630:
        return 1
    elif item_level < 640:
        return 2
    elif item_level < 650:
        return 3
    elif item_level < 660:
        return 4
    elif item_level < 670:
        return 5
    elif item_level < 680:
        return 6
    elif item_level < 690:
        return 7
    elif item_level < 700:
        return 8
    elif item_level < 710:
        return 9
    else:
        return 10
    
def get_char_average_item_level(
    character_name: str, 
    report_id: str, 
    fight_id: Union[int, str],
    client: WarcraftLogsClient,
    verbose: bool = False
) -> Optional[float]:
    """
    Calculate the average item level of any character from their gear
    
    Args:
        character_name: Name of the character
        report_id: Warcraftlogs report code (e.g., "Wbcf3HZxjdrTyQqJ")
        fight_id: ID of the specific fight, or "last" for the last fight
        client: Initialized WarcraftLogsClient
        verbose: If True, print detailed analysis information
        
    Returns:
        Average item level as float, or None if character not found or data unavailable
    """
    report_code = report_id
    api_client = client
    # Input validation
    if not character_name or not isinstance(character_name, str):
        print("❌ Error: character_name must be a non-empty string")
        return None
        
    if not report_code or not isinstance(report_code, str):
        print("❌ Error: report_code must be a non-empty string")
        return None
    
    # Validate report code format (basic check)
    if len(report_code) < 10 or not report_code.replace(':', '').isalnum():
        print(f"❌ Error: Invalid report code format: '{report_code}'. Should be like 'Wbcf3HZxjdrTyQqJ'")
        return None
    
    # Step 1: Get comprehensive fight and character data in a single query
    comprehensive_query = """
    {
      reportData {
        report(code: "%s") {
          fights {
            id
            name
            kill
            encounterID
            startTime
            endTime
          }
          masterData {
            actors(type: "Player") {
              id
              name
              subType
            }
          }
        }
      }
    }
    """ % report_code
    
    try:
        # Get all data in one query
        if verbose:
            print(f"🔍 Fetching report data for {character_name} in report {report_code}...")
        
        response = api_client.query_public_api(comprehensive_query)
        
        # Check if report exists
        if not response or "data" not in response:
            print(f"❌ Error: Invalid API response for report {report_code}")
            return None
            
        report_data = response["data"]["reportData"]["report"]
        if not report_data:
            print(f"❌ Error: Report '{report_code}' not found or not accessible")
            return None
        
        # Extract fights and actors
        fights = report_data.get("fights", [])
        actors = report_data.get("masterData", {}).get("actors", [])
        
        if not fights:
            print(f"❌ Error: No fights found in report {report_code}")
            return None
            
        if not actors:
            print(f"❌ Error: No players found in report {report_code}")
            return None
        
        # Step 2: Find the character
        character_source_id = None
        character_class = None
        available_characters = []
        
        for actor in actors:
            available_characters.append(f"{actor['name']} ({actor['subType']})")
            if actor["name"].lower() == character_name.lower():
                character_source_id = actor["id"]
                character_class = actor["subType"]
                break
        
        if character_source_id is None:
            print(f"❌ Error: Character '{character_name}' not found in report {report_code}")
            print(f"📋 Available characters: {', '.join(available_characters)}")
            return None
        
        # Step 3: Resolve fight ID
        actual_fight_id = None
        available_fights = []
        
        for fight in fights:
            fight_info = f"ID {fight['id']}: {fight.get('name', 'Unknown')} ({'Kill' if fight.get('kill') else 'Wipe'})"
            available_fights.append(fight_info)
            
        if fight_id == "last":
            # Get the last fight
            if fights:
                actual_fight_id = fights[-1]["id"]
                if verbose:
                    print(f"✅ Using last fight: ID {actual_fight_id} ({fights[-1].get('name', 'Unknown')})")
            else:
                print(f"❌ Error: No fights found to use as 'last' fight")
                return None
        else:
            # Validate specific fight ID
            try:
                fight_id_int = int(fight_id)
                fight_found = False
                for fight in fights:
                    if fight["id"] == fight_id_int:
                        actual_fight_id = fight_id_int
                        fight_found = True
                        if verbose:
                            print(f"✅ Found fight: ID {actual_fight_id} ({fight.get('name', 'Unknown')})")
                        break
                
                if not fight_found:
                    print(f"❌ Error: Fight ID {fight_id_int} not found in report {report_code}")
                    print(f"📋 Available fights: {', '.join(available_fights)}")
                    return None
                    
            except (ValueError, TypeError):
                print(f"❌ Error: Invalid fight_id '{fight_id}'. Must be an integer or 'last'")
                print(f"📋 Available fights: {', '.join(available_fights)}")
                return None
        
        # Step 4: Get the character's gear from CombatantInfo events
        gear_query = """
        {
          reportData {
            report(code: "%s") {
              events(
                fightIDs: [%d]
                dataType: CombatantInfo
                sourceID: %d
                limit: 1
              ) {
                data
              }
            }
          }
        }
        """ % (report_code, actual_fight_id, character_source_id)
        
        gear_response = api_client.query_public_api(gear_query)
        
        if not gear_response or "data" not in gear_response:
            print(f"❌ Error: Failed to fetch gear data for {character_name}")
            return None
        
        events_data = gear_response["data"]["reportData"]["report"]["events"]["data"]
        
        if not events_data:
            print(f"❌ Error: No combatant info found for {character_name} in fight {actual_fight_id}")
            print("💡 This might happen if:")
            print("   - The character wasn't present in this specific fight")
            print("   - The fight data is incomplete")
            print("   - Try a different fight ID")
            return None
        
        # Extract gear data
        combatant_info = events_data[0]  # First (and should be only) event
        gear_items = combatant_info.get("gear", [])
        
        if not gear_items:
            print(f"❌ Error: No gear data found for {character_name}")
            print("💡 This might happen if the combatant info is incomplete")
            return None
        
        # Step 5: Calculate average item level from gear
        valid_gear_items = []
        gear_details = []  # For verbose output
        
        # Standard gear slot names for reference
        slot_names = [
            "Head", "Neck", "Shoulders", "Shirt/Tabard", "Chest", "Belt", 
            "Legs", "Feet", "Wrists", "Hands", "Ring 1", "Ring 2", 
            "Trinket 1", "Trinket 2", "Main Hand", "Off Hand", "Ranged/Relic"
        ]
        
        for i, item in enumerate(gear_items):
            item_level = item.get("itemLevel", 0)
            item_id = item.get("id", 0)
            item_quality = item.get("quality", 0)
            
            # Filter out cosmetic items (item level 0 or 1) and empty slots (id 0)
            if item_level > 1 and item_id > 0:
                valid_gear_items.append(item_level)
                
                if verbose and i < len(slot_names):
                    gear_details.append({
                        "slot": slot_names[i],
                        "itemLevel": item_level,
                        "itemId": item_id,
                        "quality": item_quality
                    })
        
        if not valid_gear_items:
            print(f"❌ Error: No valid gear items found for {character_name}")
            print("💡 This might happen if all gear slots are empty or contain only cosmetic items")
            return None
        
        # Calculate average
        average_item_level = sum(valid_gear_items) / len(valid_gear_items)
        
        if verbose:
            print(f"\n✅ === {character_name.upper()} ITEM LEVEL ANALYSIS ===")
            print(f"Character: {character_name}")
            print(f"Class: {character_class}")
            print(f"Report: {report_code}")
            print(f"Fight ID: {actual_fight_id}")
            print(f"Source ID: {character_source_id}")
            print(f"Valid gear pieces: {len(valid_gear_items)}")
            print(f"\nGear breakdown:")
            for gear in gear_details:
                quality_names = {1: "Poor", 2: "Common", 3: "Uncommon", 4: "Rare", 5: "Epic", 6: "Legendary"}
                quality_str = quality_names.get(gear['quality'], f"Quality {gear['quality']}")
                print(f"  {gear['slot']:<15}: {gear['itemLevel']:>3} ilvl ({quality_str}, ID: {gear['itemId']})")
            print(f"\nItem levels: {sorted(valid_gear_items, reverse=True)}")
            print(f"Average item level: {average_item_level:.1f}")
        else:
            print(f"✅ {character_name} ({character_class}): {average_item_level:.1f} average item level")
        
        return round(average_item_level, 1)
        
    except KeyError as e:
        print(f"❌ Error: Missing expected data field: {str(e)}")
        print("💡 This might indicate a malformed API response or report structure")
        return None
    except Exception as e:
        if verbose:
            import traceback
            traceback.print_exc()
        print(f"❌ Error calculating item level for {character_name}: {str(e)}")
        return None


def get_multiple_characters_item_levels(
    characters: List[Dict[str, Any]], 
    api_client: WarcraftLogsClient,
    verbose: bool = False,
    stop_on_error: bool = False
) -> Dict[str, Optional[float]]:
    """
    Calculate item levels for multiple characters with improved error handling
    
    Args:
        characters: List of dicts with keys: 'name', 'report_code', 'fight_id'
        api_client: Initialized WarcraftLogsClient
        verbose: If True, print detailed analysis information
        stop_on_error: If True, stop processing on first error
        
    Returns:
        Dict mapping character names to their average item levels (None if failed)
    """
    if not characters or not isinstance(characters, list):
        print("❌ Error: characters must be a non-empty list")
        return {}
    
    results = {}
    
    for i, char_info in enumerate(characters, 1):
        if not isinstance(char_info, dict):
            print(f"❌ Error: Character info {i} must be a dictionary")
            if stop_on_error:
                break
            continue
            
        name = char_info.get('name')
        report_code = char_info.get('report_code')
        fight_id = char_info.get('fight_id', 'last')
        
        if not name or not report_code:
            print(f"❌ Error: Character {i} missing required 'name' or 'report_code'")
            if stop_on_error:
                break
            continue
        
        if verbose:
            print(f"\n{'='*50}")
            print(f"Processing {i}/{len(characters)}: {name}...")
        
        ilvl = get_char_average_item_level(
            character_name=name,
            report_code=report_code,
            fight_id=fight_id,
            api_client=api_client,
            verbose=verbose
        )
        
        results[name] = ilvl
        
        if ilvl is None and stop_on_error:
            print(f"❌ Stopping due to error with {name}")
            break
            
    return results


def analyze_group_item_levels(
    report_code: str,
    api_client,
    fight_id: Union[int, str],
    verbose: bool = False,
    
) -> Dict[str, Dict[str, Any]]:
    """
    Analyze item levels for all players in a specific fight with improved error handling
    
    Args:
        report_code: Warcraftlogs report code
        fight_id: Fight ID or "last" for the last fight
        api_client: Initialized WarcraftLogsClient
        verbose: If True, print detailed analysis information
        
    Returns:
        Dict mapping character names to their info including item level
    """
    
    # Input validation
    if not report_code or not isinstance(report_code, str):
        print("❌ Error: report_code must be a non-empty string")
        return {}
    
    # Use the same comprehensive query approach
    comprehensive_query = """
    {
      reportData {
        report(code: "%s") {
          fights {
            id
            name
            kill
            encounterID
            startTime
            endTime
          }
          masterData {
            actors(type: "Player") {
              id
              name
              subType
            }
          }
        }
      }
    }
    """ % report_code
    
    try:
        response = api_client.query_public_api(comprehensive_query)
        
        if not response or "data" not in response:
            print(f"❌ Error: Invalid API response for report {report_code}")
            return {}
            
        report_data = response["data"]["reportData"]["report"]
        if not report_data:
            print(f"❌ Error: Report '{report_code}' not found or not accessible")
            return {}
        
        fights = report_data.get("fights", [])
        actors = report_data.get("masterData", {}).get("actors", [])
        
        if not fights:
            print(f"❌ Error: No fights found in report {report_code}")
            return {}
            
        if not actors:
            print(f"❌ Error: No players found in report {report_code}")
            return {}
        
        # Resolve fight ID
        actual_fight_id = None
        if fight_id == "last":
            actual_fight_id = fights[-1]["id"]
        else:
            try:
                fight_id_int = int(fight_id)
                for fight in fights:
                    if fight["id"] == fight_id_int:
                        actual_fight_id = fight_id_int
                        break
                if actual_fight_id is None:
                    available_fights = [f"ID {f['id']}: {f.get('name', 'Unknown')}" for f in fights]
                    print(f"❌ Error: Fight ID {fight_id_int} not found")
                    print(f"📋 Available fights: {', '.join(available_fights)}")
                    return {}
            except (ValueError, TypeError):
                print(f"❌ Error: Invalid fight_id '{fight_id}'. Must be an integer or 'last'")
                return {}
        
        results = {}
        successful = 0
        failed = 0
        
        print(f"🔍 Analyzing {len(actors)} characters in fight {actual_fight_id}...")
        
        for actor in actors:
            char_name = actor["name"]
            char_class = actor["subType"]
            
            ilvl = get_char_average_item_level(
                character_name=char_name,
                report_code=report_code,
                fight_id=actual_fight_id,
                api_client=api_client,
                verbose=False  # Set to False to avoid spam
            )
            
            results[char_name] = {
                "class": char_class,
                "sourceId": actor["id"],
                "itemLevel": ilvl
            }
            
            if ilvl is not None:
                successful += 1
            else:
                failed += 1
        
        print(f"📊 Analysis complete: {successful} successful, {failed} failed")
        
        if verbose and successful > 0:
            print(f"\n✅ === GROUP ITEM LEVEL ANALYSIS ===")
            print(f"Report: {report_code}, Fight: {actual_fight_id}")
            print(f"{'Character':<15} {'Class':<12} {'Item Level':<10}")
            print("-" * 40)
            
            # Sort by item level descending
            sorted_chars = sorted(
                [(name, info) for name, info in results.items() if info["itemLevel"] is not None], 
                key=lambda x: x[1]["itemLevel"], 
                reverse=True
            )
            
            for char_name, info in sorted_chars:
                ilvl_str = f"{info['itemLevel']:.1f}"
                print(f"{char_name:<15} {info['class']:<12} {ilvl_str:<10}")
            
            # Show failed characters
            failed_chars = [name for name, info in results.items() if info["itemLevel"] is None]
            if failed_chars:
                print(f"\n❌ Failed to get item level for: {', '.join(failed_chars)}")
        
        return results
        
    except Exception as e:
        if verbose:
            import traceback
            traceback.print_exc()
        print(f"❌ Error analyzing group item levels: {str(e)}")
        return {}


def validate_inputs_before_query(character_name: str, report_code: str, fight_id: Union[int, str]) -> bool:
    """
    Validate inputs before making any API calls
    
    Returns:
        True if inputs look valid, False otherwise
    """
    errors = []
    
    if not character_name or not isinstance(character_name, str):
        errors.append("character_name must be a non-empty string")
    elif len(character_name.strip()) == 0:
        errors.append("character_name cannot be empty or just whitespace")
        
    if not report_code or not isinstance(report_code, str):
        errors.append("report_code must be a non-empty string")
    elif len(report_code) < 10 or not report_code.replace(':', '').isalnum():
        errors.append(f"report_code '{report_code}' doesn't look like a valid format")
    
    if fight_id != "last":
        try:
            fight_id_int = int(fight_id)
            if fight_id_int < 1:
                errors.append("fight_id must be a positive integer or 'last'")
        except (ValueError, TypeError):
            errors.append(f"fight_id '{fight_id}' must be an integer or 'last'")
    
    if errors:
        print("❌ Input validation errors:")
        for error in errors:
            print(f"   • {error}")
        return False
    
    return True
