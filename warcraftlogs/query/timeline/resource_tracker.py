"""
Enhanced WarcraftLogs Resource Tracker with Complete Resource Types
"""

import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

class ResourceType(Enum):
    """Complete WoW Resource Types"""
    MANA = 0
    RAGE = 1
    FOCUS = 2
    ENERGY = 3
    COMBO_POINTS = 4
    RUNES = 5
    RUNIC_POWER = 6
    SOUL_SHARDS = 7
    MAELSTROM = 8  # Originally for Enhancement, now also Elemental
    CHI = 9
    INSANITY = 13
    ARCANE_CHARGES = 16
    FURY = 17
    PAIN = 18
    # New resource type found in data
    MAELSTROM_11 = 11  # Alternative Maelstrom type for modern shamans

@dataclass
class ResourceSnapshot:
    """Snapshot of a player's resources at a specific time"""
    timestamp: int
    fight_relative_seconds: float
    hit_points: int = 0
    max_hit_points: int = 0
    absorb: int = 0
    primary_resources: Dict[ResourceType, int] = field(default_factory=dict)
    primary_max: Dict[ResourceType, int] = field(default_factory=dict)
    secondary_resources: Dict[ResourceType, int] = field(default_factory=dict)
    secondary_max: Dict[ResourceType, int] = field(default_factory=dict)
    attack_power: int = 0
    spell_power: int = 0
    armor: int = 0
    item_level: int = 0
    
    def get_resource(self, resource_type: ResourceType) -> Optional[int]:
        """Get current amount of a resource"""
        if resource_type in self.primary_resources:
            return self.primary_resources[resource_type]
        elif resource_type in self.secondary_resources:
            return self.secondary_resources[resource_type]
        return None
    
    def get_resource_max(self, resource_type: ResourceType) -> Optional[int]:
        """Get max amount of a resource"""
        if resource_type in self.primary_max:
            return self.primary_max[resource_type]
        elif resource_type in self.secondary_max:
            return self.secondary_max[resource_type]
        return None
    
    def get_resource_percentage(self, resource_type: ResourceType) -> Optional[float]:
        """Get resource as percentage (0.0 to 100.0)"""
        current = self.get_resource(resource_type)
        maximum = self.get_resource_max(resource_type)
        if current is not None and maximum is not None and maximum > 0:
            return (current / maximum) * 100.0
        return None
    
    def get_health_percentage(self) -> float:
        """Get health as percentage"""
        if self.max_hit_points > 0:
            return (self.hit_points / self.max_hit_points) * 100.0
        return 0.0

class PlayerResourceTracker:
    """Tracks resources for a single player throughout a fight"""
    
    def __init__(self, player_id: int):
        self.player_id = player_id
        self.player_name = ""
        self.player_class = ""
        self.snapshots: List[ResourceSnapshot] = []
        self.current_primary_resources: Dict[ResourceType, int] = {}
        self.current_primary_max: Dict[ResourceType, int] = {}
        self.current_secondary_resources: Dict[ResourceType, int] = {}
        self.current_secondary_max: Dict[ResourceType, int] = {}
        self.detected_resources: set = set()
    
    def process_resource_event(self, event: Dict[str, Any], fight_start_time: int):
        """Process a resource change event with enhanced resource detection"""
        timestamp = event['timestamp']
        fight_relative_seconds = (timestamp - fight_start_time) / 1000.0
        
        snapshot = ResourceSnapshot(
            timestamp=timestamp,
            fight_relative_seconds=fight_relative_seconds,
            hit_points=event.get('hitPoints', 0),
            max_hit_points=event.get('maxHitPoints', 0),
            absorb=event.get('absorb', 0),
            attack_power=event.get('attackPower', 0),
            spell_power=event.get('spellPower', 0),
            armor=event.get('armor', 0),
            item_level=event.get('itemLevel', 0)
        )
        
        # Process primary resource change
        resource_change_type = event.get('resourceChangeType')
        if resource_change_type is not None:
            try:
                resource_type = ResourceType(resource_change_type)
                resource_change = event.get('resourceChange', 0)
                max_resource = event.get('maxResourceAmount', 0)
                
                # Special handling for Soul Shards
                if resource_type == ResourceType.SOUL_SHARDS:
                    max_resource = max_resource // 10
                
                # Update current state with change
                if resource_type not in self.current_primary_resources:
                    self.current_primary_resources[resource_type] = 0
                
                self.current_primary_resources[resource_type] += resource_change
                self.current_primary_resources[resource_type] = max(0, 
                    min(self.current_primary_resources[resource_type], max_resource))
                
                self.current_primary_max[resource_type] = max_resource
                self.detected_resources.add(resource_type)
                
            except ValueError:
                # Handle unknown resource types by creating a dynamic enum entry
                print(f"Unknown primary resource type: {resource_change_type}")
                pass
        
        # Process secondary resources (classResources)
        class_resources = event.get('classResources', [])
        for resource_data in class_resources:
            try:
                resource_type = ResourceType(resource_data['type'])
                amount = resource_data['amount']
                max_amount = resource_data['max']
                
                # Update current state with absolute values
                self.current_secondary_resources[resource_type] = amount
                self.current_secondary_max[resource_type] = max_amount
                self.detected_resources.add(resource_type)
                
            except ValueError:
                # Handle unknown resource types
                print(f"Unknown class resource type: {resource_data['type']}")
                pass
        
        # Prefer classResources over primary tracking when both available
        for resource_type in list(self.current_primary_resources.keys()):
            if resource_type in self.current_secondary_resources:
                snapshot.secondary_resources[resource_type] = self.current_secondary_resources[resource_type]
                snapshot.secondary_max[resource_type] = self.current_secondary_max[resource_type]
            else:
                snapshot.primary_resources[resource_type] = self.current_primary_resources[resource_type]
                snapshot.primary_max[resource_type] = self.current_primary_max[resource_type]
        
        # Add any resources that are only in secondary
        for resource_type in self.current_secondary_resources:
            if resource_type not in snapshot.secondary_resources and resource_type not in snapshot.primary_resources:
                snapshot.secondary_resources[resource_type] = self.current_secondary_resources[resource_type]
                snapshot.secondary_max[resource_type] = self.current_secondary_max[resource_type]
        
        self.snapshots.append(snapshot)
    
    def get_resources_at_time(self, fight_relative_seconds: float) -> Optional[ResourceSnapshot]:
        """Get resource snapshot closest to the specified time"""
        if not self.snapshots:
            return None
        
        closest_snapshot = None
        min_time_diff = float('inf')
        
        for snapshot in self.snapshots:
            time_diff = abs(snapshot.fight_relative_seconds - fight_relative_seconds)
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_snapshot = snapshot
        
        return closest_snapshot

class WarcraftLogsResourceTracker:
    """Enhanced resource tracker with complete class support"""
    
    def __init__(self, report_code: str, fight_id: int):
        self.report_code = report_code
        self.fight_id = fight_id
        self.fight_start_time: Optional[int] = None
        self.fight_end_time: Optional[int] = None
        self.fight_name: str = ""
        self.player_trackers: Dict[int, PlayerResourceTracker] = {}
        self.player_names: Dict[int, str] = {}
        self.player_ids: Dict[str, int] = {}
        self.client = None
    
    def initialize_with_client(self, client):
        """Initialize with WarcraftLogs client"""
        self.client = client
        self._load_fight_info()
        self._load_player_names()
    
    def _load_fight_info(self):
        """Load basic fight information"""
        query = """
        {
          reportData {
            report(code: "%s") {
              fights(fightIDs: [%d]) {
                id
                name
                startTime
                endTime
                friendlyPlayers
              }
            }
          }
        }
        """ % (self.report_code, self.fight_id)
        
        result = self.client.query_public_api(query)
        fight_data = result['data']['reportData']['report']['fights'][0]
        
        self.fight_start_time = fight_data['startTime']
        self.fight_end_time = fight_data['endTime']
        self.fight_name = fight_data['name']
        
        for player_id in fight_data['friendlyPlayers']:
            self.player_trackers[player_id] = PlayerResourceTracker(player_id)
    
    def _load_player_names(self):
        """Load player names from master data"""
        query = """
        {
          reportData {
            report(code: "%s") {
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
        """ % self.report_code
        
        result = self.client.query_public_api(query)
        actors = result['data']['reportData']['report']['masterData']['actors']
        
        for actor in actors:
            player_id = actor['id']
            player_name = actor['name']
            player_class = actor.get('subType', actor.get('type', 'Unknown'))
            
            if player_id in self.player_trackers:
                self.player_names[player_id] = player_name
                self.player_ids[player_name.lower()] = player_id
                
                tracker = self.player_trackers[player_id]
                tracker.player_name = player_name
                tracker.player_class = player_class
    
    def get_all_players_by_class(self) -> Dict[str, List[Tuple[str, int]]]:
        """Get all players grouped by class"""
        players_by_class = {}
        
        for player_id, tracker in self.player_trackers.items():
            player_class = tracker.player_class
            player_name = tracker.player_name
            
            if player_class not in players_by_class:
                players_by_class[player_class] = []
            
            players_by_class[player_class].append((player_name, player_id))
        
        return players_by_class
    
    def _get_player_id(self, player_name: str) -> int:
        """Get player ID by name"""
        player_id = self.player_ids.get(player_name.lower())
        if player_id is None:
            raise ValueError(f"Player '{player_name}' not found")
        return player_id
    
    def load_player_resources(self, player_name: str, sample_interval: int = 1000):
        """Load resource data for a specific player"""
        player_id = self._get_player_id(player_name)
        
        query = """
        {
          reportData {
            report(code: "%s") {
              events(
                dataType: Resources
                fightIDs: [%d]
                sourceID: %d
                startTime: %d
                endTime: %d
                includeResources: true
                limit: 10000
              ) {
                data
              }
            }
          }
        }
        """ % (self.report_code, self.fight_id, player_id, self.fight_start_time, self.fight_end_time)
        
        result = self.client.query_public_api(query)
        events = result['data']['reportData']['report']['events']['data']
        
        tracker = self.player_trackers[player_id]
        last_processed_time = 0
        
        for event in events:
            if event['timestamp'] - last_processed_time >= sample_interval:
                tracker.process_resource_event(event, self.fight_start_time)
                last_processed_time = event['timestamp']
        
        return len(tracker.snapshots)
    
    def get_player_resources_at_time(self, player_name: str, fight_relative_seconds: float) -> Optional[ResourceSnapshot]:
        """Get all resources for a player at a specific time"""
        player_id = self._get_player_id(player_name)
        if player_id not in self.player_trackers:
            return None
        
        return self.player_trackers[player_id].get_resources_at_time(fight_relative_seconds)
    
    def get_player_resource_percentage(self, player_name: str, resource_type: ResourceType, fight_relative_seconds: float) -> Optional[float]:
        """Get specific resource percentage for a player at a specific time"""
        snapshot = self.get_player_resources_at_time(player_name, fight_relative_seconds)
        if snapshot:
            return snapshot.get_resource_percentage(resource_type)
        return None


def test_enhanced_tracker():
    """Test the enhanced tracker with complete resource support"""
    import warcraftlogs
    from warcraftlogs.constants import TOKEN_DIR
    from warcraftlogs import WarcraftLogsClient
    
    client = WarcraftLogsClient(token_dir=TOKEN_DIR)
    
    report_code = "6HXLzJf2PjFdDCn1"
    fight_id = 15
    
    tracker = WarcraftLogsResourceTracker(report_code, fight_id)
    tracker.initialize_with_client(client)
    
    players_by_class = tracker.get_all_players_by_class()
    
    print("=== ENHANCED RESOURCE TRACKER TEST ===")
    print(f"Total classes: {len(players_by_class)}\n")
    
    # Test the problematic classes specifically
    test_cases = [
        ('Shaman', 'Dinglesquirt', ['MANA', 'MAELSTROM_11']),
        ('Monk', 'Shungmo', ['MANA']),
        ('Paladin', 'Cellystanis', ['MANA', 'CHI']),  # CHI = Holy Power for Paladin
        ('DeathKnight', 'Jomammadk', ['RUNES', 'RUNIC_POWER']),  # Verify our fix still works
    ]
    
    for class_name, player_name, expected_resources in test_cases:
        print(f"--- {class_name.upper()}: {player_name} ---")
        print(f"Expected: {expected_resources}")
        
        try:
            snapshot_count = tracker.load_player_resources(player_name, sample_interval=500)
            player_id = tracker._get_player_id(player_name)
            player_tracker = tracker.player_trackers[player_id]
            detected = [r.name for r in player_tracker.detected_resources]
            
            print(f"Detected: {detected}")
            print(f"Snapshots: {snapshot_count}")
            
            # Test at 10 seconds
            snapshot = tracker.get_player_resources_at_time(player_name, 10.0)
            if snapshot:
                print(f"At 10s:")
                print(f"  Health: {snapshot.get_health_percentage():.1f}%")
                
                for resource_type in player_tracker.detected_resources:
                    current = snapshot.get_resource(resource_type)
                    maximum = snapshot.get_resource_max(resource_type)
                    percentage = snapshot.get_resource_percentage(resource_type)
                    
                    if current is not None and maximum is not None:
                        print(f"  {resource_type.name}: {current}/{maximum} ({percentage:.1f}%)")
            
            # Check if we found expected resources
            missing = []
            for expected in expected_resources:
                if expected not in detected:
                    missing.append(expected)
            
            if missing:
                print(f"❌ STILL MISSING: {missing}")
            else:
                print("✅ All expected resources found!")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()

if __name__ == "__main__":
    test_enhanced_tracker()
