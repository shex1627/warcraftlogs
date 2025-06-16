import json
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

class ResourceChangeType(Enum):
    """Resource change types for primary resources that appear in resourceChangeType field"""
    MANA = 0
    RAGE = 1
    FOCUS = 2
    ENERGY = 3
    COMBO_POINTS = 4
    RUNES = 5
    RUNIC_POWER = 6
    SOUL_SHARDS = 7
    MAELSTROM = 8
    CHI = 9
    INSANITY = 10
    ARCANE_CHARGES = 16  # Special case for Arcane Mages
    HOLY_POWER = 9       # Seems to share with Chi - need investigation
    
class ResourceType(Enum):
    """WoW resource types based on classResources type field"""
    MANA = 0
    RAGE = 1
    FOCUS = 2
    ENERGY = 3
    COMBO_POINTS = 4
    RUNES = 5
    RUNIC_POWER = 6
    SOUL_SHARDS = 7
    #MAELSTROM = 8
    ASTRAL_POWER = 8  # Used by Balance Druid, but also Maelstrom for Shaman
    CHI = 9
    INSANITY = 10
    ARCANE_CHARGES = 11  # When it appears in classResources (rare)
    FURY = 12
    PAIN = 13
    DEMON_HUNTER_FURY = 17  # NEW: Demon Hunter Fury (hybrid resource)

    @classmethod
    def from_int(cls, value: int) -> 'ResourceType':
        """Convert an integer to a ResourceType enum"""
        try:
            return ResourceType(value)
        except ValueError:
            raise ValueError(f"Invalid resource type value: {value}")

@dataclass
class ResourceSnapshot:
    """Represents the state of a single resource at a point in time"""
    timestamp: int
    amount: int
    max_amount: int
    resource_type: int
    change: int = 0
    waste: int = 0
    is_primary_resource: bool = False  # True if tracked via resourceChangeType, False if via classResources
    
    @property
    def percentage(self) -> float:
        """Returns resource as percentage (0-100)"""
        if self.max_amount == 0:
            return 0.0
        return (self.amount / self.max_amount) * 100.0

@dataclass
class PlayerState:
    """Complete player state at a point in time"""
    timestamp: int
    resources: Dict[int, ResourceSnapshot] = field(default_factory=dict)
    hit_points: int = 0
    max_hit_points: int = 0
    attack_power: int = 0
    spell_power: int = 0
    armor: int = 0
    item_level: int = 0
    position: Tuple[int, int] = (0, 0)
    
    @property
    def health_percentage(self) -> float:
        """Returns health as percentage (0-100)"""
        if self.max_hit_points == 0:
            return 0.0
        return (self.hit_points / self.max_hit_points) * 100.0

class WarcraftLogsResourceTracker:
    """
    Tracks player resources throughout a WoW raid fight using Warcraft Logs GraphQL API.
    
    Supports all WoW classes and their various resource types:
    - Death Knight: Runes + Runic Power
    - Demon Hunter: Fury + Pain
    - Druid: Mana (or Energy/Rage in forms)
    - Evoker: Mana
    - Hunter: Focus
    - Mage: Mana + Arcane Charges
    - Monk: Energy + Chi
    - Paladin: Mana + Holy Power
    - Priest: Mana + Insanity (Shadow)
    - Rogue: Energy + Combo Points
    - Shaman: Mana + Maelstrom
    - Warlock: Mana + Soul Shards
    - Warrior: Rage
    """
    
    def __init__(self, graphql_query_func: Callable):
        """
        Initialize the resource tracker.
        
        Args:
            graphql_query_func: Function that executes GraphQL queries against Warcraft Logs API
                               Should accept (query: str, variables: dict) and return dict
        """
        self.query_func = graphql_query_func
        self.player_data: Dict[str, List[PlayerState]] = {}
        self.fight_start_time: int = 0
        self.fight_end_time: int = 0
        self.primary_resource_tracking: Dict[str, Dict[int, int]] = {}  # {character: {resource_type: current_amount}}
        
    def track_player_resources(self, report_code: str, fight_id: int, character_name: str) -> Dict[str, List[PlayerState]]:
        """
        Track all resource changes for a specific player throughout a fight.
        
        Args:
            report_code: Warcraft Logs report code (e.g., "6HXLzJf2PjFdDCn1")
            fight_id: Specific fight ID within the report
            character_name: Name of the character to track
            
        Returns:
            Dictionary with character name as key and list of PlayerState snapshots as value
        """
        # First, get fight info and find the player
        fight_info = self._get_fight_info(report_code, fight_id)
        player_id = self._find_player_id(report_code, character_name)
        
        if player_id is None:
            raise ValueError(f"Character '{character_name}' not found in report")
        
        self.fight_start_time = fight_info['startTime']
        self.fight_end_time = fight_info['endTime']
        
        # Get all resource change events for this player
        resource_events = self._get_resource_events(report_code, fight_id, player_id)
        
        # Process events into player states
        player_states = self._process_resource_events(resource_events, character_name)
        
        self.player_data[character_name] = player_states
        return {character_name: player_states}
    
    def track_multiple_players(self, report_code: str, fight_id: int, character_names: List[str]) -> Dict[str, List[PlayerState]]:
        """
        Track resources for multiple players in the same fight.
        
        Args:
            report_code: Warcraft Logs report code
            fight_id: Specific fight ID within the report
            character_names: List of character names to track
            
        Returns:
            Dictionary with character names as keys and lists of PlayerState snapshots as values
        """
        result = {}
        for character_name in character_names:
            try:
                character_data = self.track_player_resources(report_code, fight_id, character_name)
                result.update(character_data)
            except ValueError as e:
                print(f"Warning: {e}")
                
        return result
    
    def get_resource_at_time(self, character_name: str, seconds_from_fight_start: float, resource_type: int) -> Optional[ResourceSnapshot]:
        """
        Get the state of a specific resource type at a given time relative to fight start.
        
        Args:
            character_name: Name of the character
            seconds_from_fight_start: Time in seconds from the start of the fight (e.g., 30.5 for 30.5 seconds into fight)
            resource_type: Resource type ID (see ResourceType enum)
            
        Returns:
            ResourceSnapshot at the closest timestamp, or None if not found
        """
        if character_name not in self.player_data:
            return None
            
        states = self.player_data[character_name]
        if not states:
            return None
            
        # Convert fight-relative seconds to absolute timestamp
        absolute_timestamp = self.fight_start_time + (seconds_from_fight_start * 1000)
        
        # Find the closest state at or before the requested timestamp
        closest_state = None
        for state in states:
            if state.timestamp <= absolute_timestamp:
                closest_state = state
            else:
                break
                
        if closest_state and resource_type in closest_state.resources:
            return closest_state.resources[resource_type]
            
        return None
    
    def get_player_state_at_time(self, character_name: str, seconds_from_fight_start: float) -> Optional[PlayerState]:
        """
        Get complete player state at a given time relative to fight start.
        
        Args:
            character_name: Name of the character
            seconds_from_fight_start: Time in seconds from the start of the fight (e.g., 30.5 for 30.5 seconds into fight)
            
        Returns:
            Complete PlayerState at the closest timestamp, or None if not found
        """
        if character_name not in self.player_data:
            return None
            
        states = self.player_data[character_name]
        if not states:
            return None
            
        # Convert fight-relative seconds to absolute timestamp
        absolute_timestamp = self.fight_start_time + (seconds_from_fight_start * 1000)
        
        # Find the closest state at or before the requested timestamp
        closest_state = None
        for state in states:
            if state.timestamp <= absolute_timestamp:
                closest_state = state
            else:
                break
                
        return closest_state
    
    def get_resource_timeline(self, character_name: str, resource_type: int) -> List[Tuple[float, float]]:
        """
        Get the full timeline of a specific resource as percentages with fight-relative timestamps.
        
        Args:
            character_name: Name of the character
            resource_type: Resource type ID
            
        Returns:
            List of (seconds_from_fight_start, percentage) tuples
        """
        if character_name not in self.player_data:
            return []
            
        timeline = []
        for state in self.player_data[character_name]:
            if resource_type in state.resources:
                resource = state.resources[resource_type]
                # Convert absolute timestamp to fight-relative seconds
                seconds_from_start = (state.timestamp - self.fight_start_time) / 1000.0
                timeline.append((seconds_from_start, resource.percentage))
                
        return timeline
    
    def get_resources_at_intervals(self, character_name: str, interval_seconds: float = 30.0) -> List[Tuple[float, Dict[int, ResourceSnapshot]]]:
        """
        Get all resources at regular intervals throughout the fight.
        
        Args:
            character_name: Name of the character
            interval_seconds: Time interval in seconds (default: every 30 seconds)
            
        Returns:
            List of (seconds_from_fight_start, {resource_type: ResourceSnapshot}) tuples
        """
        if character_name not in self.player_data:
            return []
            
        fight_duration = (self.fight_end_time - self.fight_start_time) / 1000.0
        intervals = []
        
        current_time = 0.0
        while current_time <= fight_duration:
            resources_at_time = {}
            player_state = self.get_player_state_at_time(character_name, current_time)
            
            if player_state:
                resources_at_time = player_state.resources.copy()
                
            intervals.append((current_time, resources_at_time))
            current_time += interval_seconds
            
        return intervals
    
    def get_fight_duration_seconds(self) -> float:
        """
        Get the total fight duration in seconds.
        
        Returns:
            Fight duration in seconds
        """
        return (self.fight_end_time - self.fight_start_time) / 1000.0
    
    def get_resource_summary(self, character_name: str) -> Dict[str, Any]:
        """
        Get a summary of resource usage for a character.
        
        Args:
            character_name: Name of the character
            
        Returns:
            Dictionary containing resource usage statistics
        """
        if character_name not in self.player_data:
            return {}
            
        states = self.player_data[character_name]
        if not states:
            return {}
            
        summary = {
            'fight_duration_seconds': (self.fight_end_time - self.fight_start_time) / 1000,
            'total_states_tracked': len(states),
            'resources': {}
        }
        
        # Analyze each resource type
        all_resource_types = set()
        for state in states:
            all_resource_types.update(state.resources.keys())
            
        for resource_type in all_resource_types:
            values = []
            total_waste = 0
            
            for state in states:
                if resource_type in state.resources:
                    resource = state.resources[resource_type]
                    values.append(resource.percentage)
                    total_waste += resource.waste
                    
            if values:
                summary['resources'][resource_type] = {
                    'resource_name': self._get_resource_name(resource_type),
                    'average_percentage': sum(values) / len(values),
                    'min_percentage': min(values),
                    'max_percentage': max(values),
                    'total_waste': total_waste,
                    'samples': len(values)
                }
                
        return summary
    
    def _get_fight_info(self, report_code: str, fight_id: int) -> Dict:
        """Get basic fight information"""
        query = """
        query GetFightInfo($reportCode: String!, $fightID: Int!) {
          reportData {
            report(code: $reportCode) {
              fights(fightIDs: [$fightID]) {
                id
                startTime
                endTime
                name
                encounterID
              }
            }
          }
        }
        """
        
        variables = {"reportCode": report_code, "fightID": fight_id}
        response = self.query_func(query, variables)
        
        fights = response['data']['reportData']['report']['fights']
        if not fights:
            raise ValueError(f"Fight {fight_id} not found in report")
            
        return fights[0]
    
    def _find_player_id(self, report_code: str, character_name: str) -> Optional[int]:
        """Find the player ID for a character name"""
        query = """
        query GetPlayers($reportCode: String!) {
          reportData {
            report(code: $reportCode) {
              masterData {
                actors(type: "Player") {
                  id
                  name
                  type
                  subType
                }
              }
            }
          }
        }
        """
        
        variables = {"reportCode": report_code}
        response = self.query_func(query, variables)
        
        actors = response['data']['reportData']['report']['masterData']['actors']
        for actor in actors:
            if actor['name'].lower() == character_name.lower():
                return actor['id']
                
        return None
    
    def _get_resource_events(self, report_code: str, fight_id: int, player_id: int) -> List[Dict]:
        """Get all resource change events for a specific player"""
        query = """
        query GetResourceEvents($reportCode: String!, $fightID: Int!, $playerID: Int!) {
          reportData {
            report(code: $reportCode) {
              events(
                fightIDs: [$fightID]
                sourceID: $playerID
                dataType: Resources
                includeResources: true
                limit: 10000
              ) {
                data
              }
            }
          }
        }
        """
        
        variables = {"reportCode": report_code, "fightID": fight_id, "playerID": player_id}
        response = self.query_func(query, variables)
        
        return response['data']['reportData']['report']['events']['data']
    
    def _process_resource_events(self, events: List[Dict], character_name: str) -> List[PlayerState]:
        """Process raw resource events into PlayerState objects"""
        states = []
        
        # Initialize primary resource tracking for this character
        if character_name not in self.primary_resource_tracking:
            self.primary_resource_tracking[character_name] = {}
        
        for event in events:
            if event.get('type') != 'resourcechange':
                continue
                
            timestamp = event['timestamp']
            
            # Create resource snapshots from classResources (secondary/hybrid resources)
            resources = {}
            class_resource_types = set()  # Track which types are in classResources
            
            if 'classResources' in event:
                for resource_data in event['classResources']:
                    resource_type = resource_data['type']
                    class_resource_types.add(resource_type)
                    resources[resource_type] = ResourceSnapshot(
                        timestamp=timestamp,
                        amount=resource_data['amount'],
                        max_amount=resource_data['max'],
                        resource_type=resource_type,
                        change=0,  # classResources don't have change info
                        waste=0,
                        is_primary_resource=False
                    )
            
            # Handle primary resource changes (Arcane Charges, Combo Points, Runes, etc.)
            resource_change_type = event.get('resourceChangeType')
            resource_change = event.get('resourceChange', 0)
            max_resource_amount = event.get('maxResourceAmount', 0)
            waste = event.get('waste', 0)
            
            # Apply scaling corrections for specific resource types
            corrected_max_amount = self._apply_resource_scaling(resource_change_type, max_resource_amount)
            
            # Track primary resources
            if resource_change_type is not None and self._is_primary_resource_type(resource_change_type):
                # Map resourceChangeType to our ResourceType enum
                mapped_resource_type = self._map_resource_change_type_to_resource_type(resource_change_type)
                
                if mapped_resource_type is not None:
                    # Check if this resource is HYBRID (appears in both primary and classResources)
                    is_hybrid_resource = mapped_resource_type in class_resource_types
                    
                    if is_hybrid_resource:
                        # For hybrid resources (like Death Knight Runic Power, Hunter Focus), 
                        # classResources is authoritative - just add the change info
                        if mapped_resource_type in resources:
                            resources[mapped_resource_type].change = resource_change
                            resources[mapped_resource_type].waste = waste
                            resources[mapped_resource_type].is_primary_resource = True  # Mark as hybrid
                    else:
                        # For primary-only resources (like Arcane Charges, Runes, Soul Shards)
                        # Track running totals manually
                        if resource_change_type not in self.primary_resource_tracking[character_name]:
                            self.primary_resource_tracking[character_name][resource_change_type] = 0
                        
                        # Apply the change
                        old_amount = self.primary_resource_tracking[character_name][resource_change_type]
                        new_amount = max(0, min(corrected_max_amount, old_amount + resource_change))
                        self.primary_resource_tracking[character_name][resource_change_type] = new_amount
                        
                        # Add primary-only resource to resources dict
                        resources[mapped_resource_type] = ResourceSnapshot(
                            timestamp=timestamp,
                            amount=new_amount,
                            max_amount=corrected_max_amount,
                            resource_type=mapped_resource_type,
                            change=resource_change,
                            waste=waste,
                            is_primary_resource=True
                        )
            
            # Create player state
            state = PlayerState(
                timestamp=timestamp,
                resources=resources,
                hit_points=event.get('hitPoints', 0),
                max_hit_points=event.get('maxHitPoints', 0),
                attack_power=event.get('attackPower', 0),
                spell_power=event.get('spellPower', 0),
                armor=event.get('armor', 0),
                item_level=event.get('itemLevel', 0),
                position=(event.get('x', 0), event.get('y', 0))
            )
            
            states.append(state)
        
        # Sort by timestamp
        states.sort(key=lambda s: s.timestamp)
        return states
    
    def _apply_resource_scaling(self, resource_change_type: int, max_resource_amount: int) -> int:
        """Apply scaling corrections for resources that have API/game discrepancies"""
        # Soul Shards: API reports max 50, but game reality is max 5
        if resource_change_type == 7:  # Soul Shards
            return max_resource_amount // 10  # 50 → 5
        
        # Add other scaling corrections here as discovered
        return max_resource_amount
    
    def _is_primary_resource_type(self, resource_change_type: int) -> bool:
        """Check if a resourceChangeType represents a primary resource that needs tracking"""
        primary_resource_types = {
            2,   # Focus (hybrid - Hunter)
            4,   # Combo Points (primary-only)
            5,   # Runes (primary-only)
            6,   # Runic Power (hybrid - Death Knight)
            7,   # Soul Shards (primary-only)
            8,   # Maelstrom/Astral Power (hybrid - Shaman/Druid)
            9,   # Chi/Holy Power (primary-only, shared ID)
            16,  # Arcane Charges (primary-only)
            17,  # Demon Hunter Fury (hybrid - NEW!)
            # Add more as discovered
        }
        return resource_change_type in primary_resource_types
    
    def _map_resource_change_type_to_resource_type(self, resource_change_type: int) -> Optional[int]:
        """Map resourceChangeType to ResourceType enum value"""
        mapping = {
            0: ResourceType.MANA.value,
            1: ResourceType.RAGE.value,
            2: ResourceType.FOCUS.value,
            3: ResourceType.ENERGY.value,
            4: ResourceType.COMBO_POINTS.value,
            5: ResourceType.RUNES.value,
            6: ResourceType.RUNIC_POWER.value,
            7: ResourceType.SOUL_SHARDS.value,
            8: ResourceType.MAELSTROM.value,  # Note: Also used for Balance Druid Astral Power
            9: ResourceType.CHI.value,  # Note: Also used for Holy Power
            10: ResourceType.INSANITY.value,
            16: ResourceType.ARCANE_CHARGES.value,  # Special case
            17: ResourceType.DEMON_HUNTER_FURY.value,  # NEW: Demon Hunter Fury
        }
        return mapping.get(resource_change_type)
    
    def _get_resource_name(self, resource_type: int) -> str:
        """Get human-readable resource name"""
        try:
            if resource_type == ResourceType.DEMON_HUNTER_FURY.value:
                return "Fury"
            elif resource_type == ResourceType.MAELSTROM.value:
                return "Maelstrom/Astral Power"  # Context-dependent
            else:
                return ResourceType(resource_type).name.replace('_', ' ').title()
        except ValueError:
            return f"Unknown Resource {resource_type}"

# Integration with your GraphQL query function
def create_tracker_with_api(query_func: Callable) -> WarcraftLogsResourceTracker:
    """
    Create a tracker instance with your existing GraphQL query function.
    
    Args:
        query_func: Your function that takes (self, query, variables) and returns response
        
    Returns:
        Configured WarcraftLogsResourceTracker
    """
    
    def wrapper(query: str, variables: dict) -> dict:
        """Wrapper to adapt your query function interface"""
        return query_func("assistant", query, variables)
    
    return WarcraftLogsResourceTracker(wrapper)

# Example usage and helper functions
def example_usage():
    """
    Example of how to use the WarcraftLogsResourceTracker
    """
    
    # You would replace this with your actual GraphQL query function
    def mock_graphql_query(query: str, variables: dict) -> dict:
        # This would make the actual API call to Warcraft Logs
        # return requests.post(GRAPHQL_ENDPOINT, json={'query': query, 'variables': variables}).json()
        pass
    
    # Initialize the tracker
    tracker = WarcraftLogsResourceTracker(mock_graphql_query)
    
    # Track a single player
    report_code = "6HXLzJf2PjFdDCn1"
    fight_id = 15
    character_name = "PlayerName"
    
    try:
        # Get all resource data for the player
        player_data = tracker.track_player_resources(report_code, fight_id, character_name)
        
        # Get resource state at a specific time (30 seconds into fight)
        runes_at_30s = tracker.get_resource_at_time(character_name, 30.0, ResourceType.RUNES.value)
        runic_power_at_30s = tracker.get_resource_at_time(character_name, 30.0, ResourceType.RUNIC_POWER.value)
        
        if runes_at_30s:
            print(f"Runes at 30s: {runes_at_30s.amount}/{runes_at_30s.max_amount} ({runes_at_30s.percentage:.1f}%)")
        
        if runic_power_at_30s:
            print(f"Runic Power at 30s: {runic_power_at_30s.amount}/{runic_power_at_30s.max_amount} ({runic_power_at_30s.percentage:.1f}%)")
        
        # Get complete player state
        player_state = tracker.get_player_state_at_time(character_name, 30.0)
        if player_state:
            print(f"Health at 30s: {player_state.health_percentage:.1f}%")
            print(f"Item Level: {player_state.item_level}")
        
        # Get resource timeline for analysis (now returns fight-relative seconds)
        rune_timeline = tracker.get_resource_timeline(character_name, ResourceType.RUNES.value)
        runic_power_timeline = tracker.get_resource_timeline(character_name, ResourceType.RUNIC_POWER.value)
        
        # Get summary statistics
        summary = tracker.get_resource_summary(character_name)
        print(f"Fight Duration: {summary['fight_duration_seconds']:.1f} seconds")
        
        for resource_type, stats in summary['resources'].items():
            print(f"{stats['resource_name']}: avg {stats['average_percentage']:.1f}%, waste: {stats['total_waste']}")
            
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    example_usage()