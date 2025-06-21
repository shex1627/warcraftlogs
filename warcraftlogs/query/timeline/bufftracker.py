"""
Fixed WarcraftLogs Buff Tracker - Handling Multiple Buff Instances
Key fix: Track multiple instances of the same buff instead of overwriting
"""

import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json

class BuffEventType(Enum):
    APPLY = "applybuff"
    REMOVE = "removebuff" 
    APPLY_STACK = "applybuffstack"
    REMOVE_STACK = "removebuffstack"
    REFRESH = "refreshbuff"

@dataclass
class BuffInstance:
    """Represents a single instance of a buff application"""
    ability_id: int
    ability_name: str = ""
    applied_timestamp: int = 0
    removed_timestamp: Optional[int] = None
    last_refresh_timestamp: Optional[int] = None
    estimated_duration: Optional[int] = None
    final_stack_count: int = 1
    source_player_id: Optional[int] = None
    
    def is_active_at_time(self, timestamp: int) -> bool:
        """Check if this buff instance is active at a specific timestamp"""
        if timestamp < self.applied_timestamp:
            return False
        
        # If explicitly removed, check against removal time
        if self.removed_timestamp and timestamp >= self.removed_timestamp:
            return False
            
        # If we have duration info, check expiration
        if self.estimated_duration is not None:
            reference_time = self.last_refresh_timestamp or self.applied_timestamp
            elapsed = timestamp - reference_time
            return elapsed <= self.estimated_duration
        
        # No duration info and not explicitly removed - assume active
        return True
    
    def get_remaining_time(self, current_timestamp: int) -> Optional[int]:
        """Calculate remaining time in milliseconds"""
        if not self.is_active_at_time(current_timestamp):
            return 0
            
        if self.estimated_duration is None:
            return None  # Unknown duration
        
        reference_time = self.last_refresh_timestamp or self.applied_timestamp
        elapsed = current_timestamp - reference_time
        remaining = self.estimated_duration - elapsed
        return max(0, remaining)
    
    def get_stack_count_at_time(self, timestamp: int, event_history: List[Dict]) -> int:
        """Get stack count at a specific time by looking at event history"""
        if not self.is_active_at_time(timestamp):
            return 0
            
        # Find the last stack-related event for this instance before the timestamp
        last_stack = 1
        for event in event_history:
            if (event['ability_id'] == self.ability_id and 
                self.applied_timestamp <= event['timestamp'] <= timestamp and
                event.get('stack') is not None):
                
                # Make sure this event belongs to this instance
                # (events between apply and remove timestamps)
                if self.removed_timestamp is None or event['timestamp'] < self.removed_timestamp:
                    last_stack = event['stack']
        
        return last_stack

@dataclass 
class PlayerBuffTracker:
    """Tracks all buff instances for a single player"""
    player_id: int
    player_name: str = ""
    buff_instances: Dict[int, List[BuffInstance]] = field(default_factory=dict)  # ability_id -> [instances]
    buff_history: List[Dict[str, Any]] = field(default_factory=list)
    active_instances: Dict[int, BuffInstance] = field(default_factory=dict)  # ability_id -> current active instance
    
    def apply_buff_event(self, event: Dict[str, Any], ability_name: str = ""):
        """Process a buff event and update buff instances"""
        ability_id = event['abilityGameID']
        timestamp = event['timestamp']
        event_type = BuffEventType(event['type'])
        stack = event.get('stack', 1)
        source_id = event.get('sourceID')
        
        # Store event in history
        self.buff_history.append({
            'timestamp': timestamp,
            'event_type': event_type.value,
            'ability_id': ability_id,
            'ability_name': ability_name,
            'stack': stack,
            'source_id': source_id
        })
        
        if ability_id not in self.buff_instances:
            self.buff_instances[ability_id] = []
        
        if event_type == BuffEventType.APPLY:
            # New buff application - create new instance
            new_instance = BuffInstance(
                ability_id=ability_id,
                ability_name=ability_name,
                applied_timestamp=timestamp,
                final_stack_count=stack,
                source_player_id=source_id
            )
            self.buff_instances[ability_id].append(new_instance)
            self.active_instances[ability_id] = new_instance
            
        elif event_type == BuffEventType.REMOVE:
            # Remove current active instance
            if ability_id in self.active_instances:
                instance = self.active_instances[ability_id]
                instance.removed_timestamp = timestamp
                # Calculate duration
                reference_time = instance.last_refresh_timestamp or instance.applied_timestamp
                instance.estimated_duration = timestamp - reference_time
                del self.active_instances[ability_id]
                
        elif event_type == BuffEventType.APPLY_STACK:
            # Update stack count of current instance
            if ability_id in self.active_instances:
                self.active_instances[ability_id].final_stack_count = stack
            else:
                # Stack application without initial apply - create instance
                new_instance = BuffInstance(
                    ability_id=ability_id,
                    ability_name=ability_name,
                    applied_timestamp=timestamp,
                    final_stack_count=stack,
                    source_player_id=source_id
                )
                self.buff_instances[ability_id].append(new_instance)
                self.active_instances[ability_id] = new_instance
                
        elif event_type == BuffEventType.REMOVE_STACK:
            if ability_id in self.active_instances:
                self.active_instances[ability_id].final_stack_count = stack
                if stack == 0:
                    # Fully removed
                    instance = self.active_instances[ability_id]
                    instance.removed_timestamp = timestamp
                    reference_time = instance.last_refresh_timestamp or instance.applied_timestamp
                    instance.estimated_duration = timestamp - reference_time
                    del self.active_instances[ability_id]
                    
        elif event_type == BuffEventType.REFRESH:
            if ability_id in self.active_instances:
                self.active_instances[ability_id].last_refresh_timestamp = timestamp
    
    def get_all_active_buffs(self, current_timestamp: int) -> List[Tuple[BuffInstance, int]]:
        """Get all active buff instances at a given timestamp with their stack counts"""
        active_buffs = []
        
        for ability_id, instances in self.buff_instances.items():
            for instance in instances:
                if instance.is_active_at_time(current_timestamp):
                    stack_count = instance.get_stack_count_at_time(current_timestamp, self.buff_history)
                    active_buffs.append((instance, stack_count))
        
        return active_buffs

class WarcraftLogsBuffTracker:
    """Main class for tracking buffs and debuffs for players in a WoW raid fight"""
    
    def __init__(self, report_code: str, fight_id: int):
        self.report_code = report_code
        self.fight_id = fight_id
        self.fight_start_time: Optional[int] = None
        self.fight_end_time: Optional[int] = None
        self.fight_name: str = ""
        self.player_trackers: Dict[int, PlayerBuffTracker] = {}
        self.ability_names: Dict[int, str] = {}
        self.player_names: Dict[int, str] = {}
        self.player_ids: Dict[str, int] = {}
        self.client = None
    
    def initialize_with_client(self, client):
        """Initialize with WarcraftLogs client"""
        self.client = client
        self._load_fight_info()
        self._load_master_data()
    
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
        if 'errors' in result:
            raise ValueError(f"GraphQL errors: {result['errors']}")
            
        fight_data = result['data']['reportData']['report']['fights'][0]
        
        self.fight_start_time = fight_data['startTime']
        self.fight_end_time = fight_data['endTime']
        self.fight_name = fight_data['name']
        
        # Initialize player trackers
        for player_id in fight_data['friendlyPlayers']:
            self.player_trackers[player_id] = PlayerBuffTracker(player_id)
    
    def _load_master_data(self):
        """Load player names and ability names"""
        query = """
        {
          reportData {
            report(code: "%s") {
              masterData {
                actors(type: "Player") {
                  id
                  name
                }
                abilities {
                  gameID
                  name
                }
              }
            }
          }
        }
        """ % self.report_code
        
        result = self.client.query_public_api(query)
        master_data = result['data']['reportData']['report']['masterData']
        
        # Store player names
        for actor in master_data['actors']:
            player_id = actor['id']
            player_name = actor['name']
            if player_id in self.player_trackers:
                self.player_trackers[player_id].player_name = player_name
                self.player_names[player_id] = player_name
                self.player_ids[player_name.lower()] = player_id
        
        # Store ability names
        for ability in master_data['abilities']:
            self.ability_names[ability['gameID']] = ability['name']
    
    def _get_player_id(self, player_name: str) -> int:
        """Get player ID by name"""
        player_id = self.player_ids.get(player_name.lower())
        if player_id is None:
            raise ValueError(f"Player '{player_name}' not found")
        return player_id
    
    def get_fight_duration_seconds(self) -> float:
        """Get fight duration in seconds"""
        return (self.fight_end_time - self.fight_start_time) / 1000.0
    
    def seconds_to_timestamp(self, fight_relative_seconds: float) -> int:
        """Convert fight-relative seconds to absolute timestamp"""
        return int(self.fight_start_time + (fight_relative_seconds * 1000))
    
    def load_player_buffs(self, player_name: str):
        """Load all buff events for a specific player"""
        player_id = self._get_player_id(player_name)
        
        query = """
        {
          reportData {
            report(code: "%s") {
              events(
                dataType: Buffs
                fightIDs: [%d]
                targetID: %d
                startTime: %d
                endTime: %d
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
        
        # Process all buff events
        tracker = self.player_trackers[player_id]
        for event in events:
            ability_id = event['abilityGameID']
            ability_name = self.ability_names.get(ability_id, f"Unknown ({ability_id})")
            tracker.apply_buff_event(event, ability_name)
        
        print(f"Loaded {len(events)} buff events for {player_name}")
        print(f"Tracked {sum(len(instances) for instances in tracker.buff_instances.values())} total buff instances")
        return len(events)
    
    def get_player_buffs_at_time(self, player_name: str, fight_relative_seconds: float) -> List[Dict[str, Any]]:
        """Get all active buffs for a player at a specific time"""
        player_id = self._get_player_id(player_name)
        if player_id not in self.player_trackers:
            return []
        
        timestamp = self.seconds_to_timestamp(fight_relative_seconds)
        active_buffs = self.player_trackers[player_id].get_all_active_buffs(timestamp)
        
        # Convert to more usable format
        result = []
        for instance, stack_count in active_buffs:
            remaining = instance.get_remaining_time(timestamp)
            result.append({
                'ability_name': instance.ability_name,
                'ability_id': instance.ability_id,
                'stack_count': stack_count,
                'remaining_time_ms': remaining,
                'remaining_time_s': remaining / 1000.0 if remaining else None,
                'applied_at_s': (instance.applied_timestamp - self.fight_start_time) / 1000.0,
                'source_player_id': instance.source_player_id
            })
        
        return result
    
    def get_buff_remaining_time(self, player_name: str, ability_name: str, fight_relative_seconds: float) -> Optional[float]:
        """Get remaining time for a specific buff"""
        buffs = self.get_player_buffs_at_time(player_name, fight_relative_seconds)
        for buff in buffs:
            if buff['ability_name'].lower() == ability_name.lower():
                return buff['remaining_time_s']
        return None
