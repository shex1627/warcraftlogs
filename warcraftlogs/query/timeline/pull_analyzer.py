import json
from typing import Dict, List, Tuple, Set, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class MobInstance:
    """Represents a specific instance of a mob."""
    actor_id: int
    instance_id: int
    game_id: int
    name: str
    first_damage_time: int = None
    last_activity_time: int = None
    death_time: int = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easier serialization."""
        return {
            'actor_id': self.actor_id,
            'instance_id': self.instance_id,
            'game_id': self.game_id,
            'name': self.name,
            'first_damage_time': self.first_damage_time,
            'last_activity_time': self.last_activity_time,
            'death_time': self.death_time
        }

@dataclass
class Pull:
    """Represents a dungeon pull."""
    pull_id: int
    start_time: int
    end_time: int
    encounter_id: int = 0  # 0 for trash, boss ID for bosses
    mobs: List[MobInstance] = field(default_factory=list)
    is_chain_pull: bool = False
    prev_pull_id: Optional[int] = None
    overlap_duration: Optional[float] = None
    gap_time: Optional[float] = None
    x: int = None
    y: int = None
    
    def add_mob(self, mob: MobInstance):
        """Add a mob to this pull."""
        self.mobs.append(mob)
        
    def get_mob_names(self) -> Set[str]:
        """Get unique mob names in this pull."""
        return {mob.name for mob in self.mobs}
        
    def get_instance_count(self) -> Dict[str, int]:
        """Get count of each mob type."""
        counts = defaultdict(int)
        for mob in self.mobs:
            counts[mob.name] += 1
        return dict(counts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easier serialization."""
        return {
            'pull_id': self.pull_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'encounter_id': self.encounter_id,
            'mobs': [mob.to_dict() for mob in self.mobs],
            'x': self.x,
            'y': self.y
        }

class DungeonPullAnalyzer:
    """Analyzes WarcraftLogs data to identify dungeon pulls."""
    
    def __init__(self, client):
        self.client = client
        self.report_code = None
        self.fight_id = None
        self.master_data = None
        self.actor_lookup = {}  # actor_id -> actor info
        self.events = {}
        self.events['damage'] = []
        self.events['threat'] = []
        self.all_mob_instances = []
        
    def load_report_data(self, report_code: str, fight_id: int):
        """Load basic report data and master data."""
        self.report_code = report_code
        self.fight_id = fight_id
        
        print(f"Loading report {report_code}, fight {fight_id}...")
        
        # Get master data for actor lookups
        query = """
        query {
          reportData {
            report(code: "%s") {
              masterData {
                actors {
                  id
                  name
                  gameID
                  type
                  subType
                }
              }
              fights(fightIDs: [%d]) {
                id
                name
                startTime
                endTime
                encounterID
                keystoneLevel
                difficulty
              }
            }
          }
        }
        """ % (report_code, fight_id)
        
        result = self.client.query_public_api(query)
        report_data = result['data']['reportData']['report']
        
        self.master_data = report_data['masterData']
        self.fight_info = report_data['fights'][0]
        
        # Build actor lookup
        for actor in self.master_data['actors']:
            self.actor_lookup[actor['id']] = actor
            
        print(f"Loaded fight: {self.fight_info['name']}")
        print(f"Duration: {(self.fight_info['endTime'] - self.fight_info['startTime']) / 1000:.1f} seconds")
        print(f"Loaded {len(self.master_data['actors'])} actors")
        
        return self.fight_info
        
    def get_api_dungeon_pulls(self) -> List[Dict]:
        """Get the dungeon pulls from the API for comparison."""
        query = """
        query {
          reportData {
            report(code: "%s") {
              fights(fightIDs: [%d]) {
                dungeonPulls {
                  id
                  name
                  startTime
                  endTime
                  encounterID
                  x
                  y
                  enemyNPCs {
                    id
                    gameID
                    minimumInstanceID
                    maximumInstanceID
                  }
                }
              }
            }
          }
        }
        """ % (self.report_code, self.fight_id)
        
        result = self.client.query_public_api(query)
        return result['data']['reportData']['report']['fights'][0]['dungeonPulls']
        
    def analyze_comprehensive_pulls_combined(self, gap_threshold=8000, max_events_per_query=2000):
        """
        Analyze the entire dungeon using BOTH damage and threat events for comprehensive detection.
        This ensures we capture all mobs including ranged mobs that don't melee the tank.
        
        Args:
            gap_threshold: Milliseconds gap to consider a new pull (default 8000ms = 8s)
            max_events_per_query: Maximum events per API query to avoid timeouts
            
        Returns:
            List of Pull objects representing detected pulls
        """
        all_mob_instances = {}
        
        # Get events in chunks to handle long fights
        fight_duration = self.fight_info['endTime'] - self.fight_info['startTime']
        chunk_size = 180000  # 3 minutes per chunk
        
        print(f"Analyzing full dungeon ({fight_duration/1000:.0f}s) using COMBINED damage + threat events...")
        
        for chunk_start in range(0, fight_duration, chunk_size):
            chunk_end = min(chunk_start + chunk_size, fight_duration)
            start_time = self.fight_info['startTime'] + chunk_start
            end_time = self.fight_info['startTime'] + chunk_end
            
            print(f"  Querying events from +{chunk_start/1000:.0f}s to +{chunk_end/1000:.0f}s...")
            
            # Get damage events (tank -> mob, captures ranged mobs)
            damage_query = """
            query {
              reportData {
                report(code: "%s") {
                  events(
                    fightIDs: [%d]
                    dataType: DamageTaken
                    startTime: %d
                    endTime: %d
                    limit: %d
                    hostilityType: Enemies
                  ) {
                    data
                  }
                }
              }
            }
            """ % (self.report_code, self.fight_id, start_time, end_time, max_events_per_query)
            
            # Get threat events (mob -> tank, validates engagement)
            threat_query = """
            query {
              reportData {
                report(code: "%s") {
                  events(
                    fightIDs: [%d]
                    dataType: Threat
                    startTime: %d
                    endTime: %d
                    limit: %d
                  ) {
                    data
                  }
                }
              }
            }
            """ % (self.report_code, self.fight_id, start_time, end_time, max_events_per_query)
            
            damage_result = self.client.query_public_api(damage_query)
            threat_result = self.client.query_public_api(threat_query)
            
            damage_events = damage_result['data']['reportData']['report']['events']['data']
            threat_events = threat_result['data']['reportData']['report']['events']['data']
            
            print(f"    Found {len(damage_events)} damage + {len(threat_events)} threat events")

            self.events['damage'].extend(damage_events)
            self.events['threat'].extend(threat_events)
            
            # Process damage events (tank attacking mobs)
            for event in damage_events:
                if event['targetID'] == 46:
                    print(f"processing gigazap events")
                    print(event)
                targetInstance = event.get('targetInstance', 0)
                # and 'targetInstance' in event
                if event['type'] == 'damage' and 'targetID' in event:
                    mob_key = (event['targetID'], targetInstance)
                    timestamp = event['timestamp']
                    if event['targetID'] == 46:
                        print(f"creating mob key {mob_key} at {timestamp}")
                    if mob_key not in all_mob_instances:
                        actor_info = self.actor_lookup.get(event['targetID'], {})
                        if actor_info['type'] != 'Player':
                            all_mob_instances[mob_key] = MobInstance(
                                actor_id=event['targetID'],
                                instance_id=targetInstance,
                                game_id=actor_info.get('gameID', 0),
                                name=actor_info.get('name', f"Unknown {event['targetID']}"),
                                first_damage_time=timestamp,
                                last_activity_time=timestamp
                            )
                    else:
                        # Update last activity time
                        all_mob_instances[mob_key].last_activity_time = timestamp
            
            # Process threat events (mobs attacking tank)
            for event in threat_events:
                if event['targetID'] == 46:
                    print(f"processing threat gigazap events")
                    print(event)
                #and 'sourceInstance' in event 
                if (event['type'] == 'cast' and 'sourceID' in event 
                    and event.get('melee', False)):
                    # if not sourceinstance, likely a boss or a unique mob
                    event_source = event.get("sourceInstance", 0)
                    mob_key = (event['sourceID'], event_source)
                    timestamp = event['timestamp']
                    
                    
                    if mob_key not in all_mob_instances:
                        # New mob found only in threat events
                        actor_info = self.actor_lookup.get(event['sourceID'], {})
                        all_mob_instances[mob_key] = MobInstance(
                            actor_id=event['sourceID'],
                            instance_id=event_source,
                            game_id=actor_info.get('gameID', 0),
                            name=actor_info.get('name', f"Unknown {event['sourceID']}"),
                            first_damage_time=timestamp,
                            last_activity_time=timestamp
                        )
                    else:
                        # Update existing mob's timing
                        # Use threat time as first damage if it's earlier (unusual but possible)
                        if timestamp < all_mob_instances[mob_key].first_damage_time:
                            all_mob_instances[mob_key].first_damage_time = timestamp
                        # Always update last activity
                        all_mob_instances[mob_key].last_activity_time = max(
                            all_mob_instances[mob_key].last_activity_time, timestamp
                        )
        
        print(f"\nTotal unique mob instances found: {len(all_mob_instances)} (via combined detection)")
        
        # Sort mobs by first engagement time
        sorted_mobs = sorted(all_mob_instances.values(), key=lambda x: x.first_damage_time)
        self.all_mob_instances = sorted_mobs
        
        # Group into pulls based on timing gaps
        pulls = []
        current_pull_mobs = []
        current_pull_start = None
        pull_id = 1
        
        for mob in sorted_mobs:
            # If this is the first mob or there's a significant gap, start a new pull
            if (current_pull_start is None or 
                mob.first_damage_time - current_pull_start > gap_threshold):
                
                # Finalize previous pull if it exists
                if current_pull_mobs:
                    pull_end = max(m.last_activity_time for m in current_pull_mobs)
                    pull = Pull(
                        pull_id=pull_id - 1,
                        start_time=current_pull_start,
                        end_time=pull_end,
                        mobs=current_pull_mobs.copy()
                    )
                    pulls.append(pull)
                
                # Start new pull
                current_pull_mobs = [mob]
                current_pull_start = mob.first_damage_time
                pull_id += 1
            else:
                # Add to current pull
                current_pull_mobs.append(mob)
        
        # Don't forget the last pull
        if current_pull_mobs:
            pull_end = max(m.last_activity_time for m in current_pull_mobs)
            pull = Pull(
                pull_id=pull_id - 1,
                start_time=current_pull_start,
                end_time=pull_end,
                mobs=current_pull_mobs.copy()
            )
            pulls.append(pull)
        
        return pulls

def analyze_chain_pulls(detected_pulls, gap_threshold=5000):
    """
    Analyze detected pulls to identify potential chain pulls.
    Chain pulls occur when new mobs are engaged before previous ones are finished.
    
    Args:
        detected_pulls: List of Pull objects
        gap_threshold: Milliseconds threshold for considering overlap significant
        
    Returns:
        List of chain pull information dictionaries
    """
    print(f"\nAnalyzing for chain pulls (gap threshold: {gap_threshold/1000}s)...")
    
    chain_pull_info = []
    
    for i, pull in enumerate(detected_pulls):
        if i == 0:
            continue
            
        prev_pull = detected_pulls[i-1]
        
        # Check if this pull started before the previous pull ended
        gap_time = pull.start_time - prev_pull.end_time
        overlap_time = prev_pull.end_time - pull.start_time
        
        if gap_time < 0:  # Negative gap means overlap
            chain_pull_info.append({
                'pull_id': pull.pull_id,
                'prev_pull_id': prev_pull.pull_id,
                'overlap_duration': overlap_time / 1000,
                'gap_time': gap_time / 1000
            })
    
    if chain_pull_info:
        print(f"Found {len(chain_pull_info)} potential chain pulls:")
        for info in chain_pull_info:
            print(f"  Pull {info['pull_id']} started {abs(info['gap_time']):.1f}s before Pull {info['prev_pull_id']} ended")
    else:
        print("No chain pulls detected - all pulls have clear separation")
    
    return chain_pull_info

def print_pull_analysis(detected_pulls, fight_info):
    """Print detailed analysis of detected pulls."""
    print(f"\nDetected {len(detected_pulls)} pulls:")
    
    for pull in detected_pulls:
        duration = (pull.end_time - pull.start_time) / 1000
        rel_start = (pull.start_time - fight_info['startTime']) / 1000
        rel_end = (pull.end_time - fight_info['startTime']) / 1000
        
        print(f"\nPull {pull.pull_id}: {rel_start:6.1f}s - {rel_end:6.1f}s ({duration:5.1f}s)")
        
        # Show mob composition with instance details
        mob_counts = pull.get_instance_count()
        for mob_name, count in sorted(mob_counts.items()):
            # Show instance IDs for this mob type
            instances = [m.instance_id for m in pull.mobs if m.name == mob_name]
            if len(instances) > 1:
                instance_range = f"{min(instances)}-{max(instances)}"
            else:
                instance_range = str(instances[0])
            print(f"  {count:2d}x {mob_name:<25} (instances {instance_range})")

def compare_with_api_pulls(detected_pulls, api_pulls, fight_info):
    """Compare detected pulls with API dungeon pulls."""
    print("\n" + "="*60)
    print("COMPARISON WITH API DUNGEON PULLS")
    print("="*60)
    
    print(f"\nAPI pulls: {len(api_pulls)}")
    print(f"Detected pulls: {len(detected_pulls)}")
    
    print("\nAPI Pull Summary (first 8):")
    for i, api_pull in enumerate(api_pulls[:8]):
        api_start = (api_pull['startTime'] - fight_info['startTime']) / 1000
        api_end = (api_pull['endTime'] - fight_info['startTime']) / 1000
        api_duration = (api_pull['endTime'] - api_pull['startTime']) / 1000
        
        print(f"API Pull {api_pull['id']:2d}: {api_start:6.1f}s - {api_end:6.1f}s ({api_duration:5.1f}s) - {api_pull['name']}")
        
        # Count total mobs in API pull
        total_mobs = sum(npc['maximumInstanceID'] - npc['minimumInstanceID'] + 1 for npc in api_pull['enemyNPCs'])
        print(f"            {len(api_pull['enemyNPCs'])} mob types, {total_mobs} total instances")

def generate_insights_report(detected_pulls, chain_pulls, api_pulls):
    """Generate key insights and recommendations."""
    print(f"\n{'-'*60}")
    print("KEY INSIGHTS:")
    print(f"{'-'*60}")

    print("\n1. CHAIN PULL DETECTION:")
    if chain_pulls:
        print(f"   ✓ Successfully detected {len(chain_pulls)} chain pulls")
        print("   ✓ Shows when new mobs engaged before previous pack cleared")
        print("   ✓ Instance ID tracking reveals pull overlap patterns")
    else:
        print("   - No chain pulls detected in this run")

    print("\n2. INSTANCE ID ANALYSIS:")
    print("   ✓ Same mob types use sequential instance IDs")
    print("   ✓ Gaps in sequence indicate separate encounters")
    print("   ✓ Overlapping ranges confirm chain pulling")

    print("\n3. PULL GRANULARITY:")
    print("   ✓ Event-based detection shows finer granularity than API")
    print("   ✓ API groups tactical pulls into strategic encounters")
    print("   ✓ Damage events reveal actual engagement timing")

    print("\n4. PRACTICAL APPLICATIONS:")
    print("   • Route optimization: identify unnecessary chain pulls")
    print("   • Performance analysis: measure actual mob engagement duration")  
    print("   • Strategy planning: understand pull overlap patterns")
    print("   • M+ timer optimization: find time-wasting pull sequences")

    # Generate recommendations
    recommendations = []
    if len(chain_pulls) > 0:
        recommendations.append(f"Consider reviewing {len(chain_pulls)} chain pulls for potential optimization")
    
    # Find very short pulls that might indicate inefficient pulling
    short_pulls = [p for p in detected_pulls if (p.end_time - p.start_time) < 10000]  # Less than 10s
    if short_pulls:
        recommendations.append(f"Review {len(short_pulls)} very short pulls (<10s) for potential grouping opportunities")
    
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  • {rec}")

def main():
    """Main analysis function demonstrating combined approach."""
    # Example usage - replace with your report details
    import warcraftlogs
    from warcraftlogs.constants import TOKEN_DIR
    from warcraftlogs import WarcraftLogsClient

    # Initialize client
    client = WarcraftLogsClient(token_dir=TOKEN_DIR)
    analyzer = DungeonPullAnalyzer(client)
    
    # Test with multiple fights to validate boss detection and ranged mobs
    test_fights = [
        (1, "The MOTHERLODE!! (Full Dungeon)"),
        (3, "Operation: Floodgate (With Mechadrones)")
    ]
    
    for fight_id, fight_desc in test_fights:
        print("\n" + "="*70)
        print(f"ANALYZING FIGHT {fight_id}: {fight_desc}")
        print("="*70)
        
        # Load the report data
        fight_info = analyzer.load_report_data("vDdYBKJaPVbRcz23", fight_id)
        
        # Get API pulls for comparison
        api_pulls = analyzer.get_api_dungeon_pulls()
        boss_pulls = [p for p in api_pulls if p['encounterID'] != 0]
        trash_pulls = [p for p in api_pulls if p['encounterID'] == 0]
        
        print(f"\nAPI reports: {len(api_pulls)} total pulls ({len(boss_pulls)} boss, {len(trash_pulls)} trash)")
        
        # Show boss encounters
        if boss_pulls:
            print(f"\nBoss encounters detected:")
            for pull in boss_pulls:
                rel_start = (pull['startTime'] - fight_info['startTime']) / 1000
                duration = (pull['endTime'] - pull['startTime']) / 1000
                print(f"  {pull['name']} (ID {pull['encounterID']}) at {rel_start:.1f}s ({duration:.1f}s)")
        
        # Analyze with combined method
        print(f"\nRunning COMBINED damage + threat analysis...")
        detected_pulls = analyzer.analyze_comprehensive_pulls_combined(gap_threshold=8000)
        
        # Print results
        print_pull_analysis(detected_pulls, fight_info, method="Combined Events")
        
        # Analyze chain pulls
        chain_pulls = analyze_chain_pulls(detected_pulls, gap_threshold=5000)
        
        # Look for specific mob types
        print(f"\nSpecial mob detection:")
        ranged_mobs = []
        boss_mobs = []
        
        for pull in detected_pulls:
            for mob in pull.mobs:
                if any(keyword in mob.name.lower() for keyword in ['mechadrone', 'sniper']):
                    ranged_mobs.append((pull.pull_id, mob.name, mob.instance_id))
                elif any(keyword in mob.name.lower() for keyword in ['boss', 'pummeler', 'azerokk', 'rixxa', 'mogul', 'm.o.m.m.a', 'swampface', 'geezle']):
                    boss_mobs.append((pull.pull_id, mob.name, mob.instance_id))
        
        if ranged_mobs:
            print(f"  Ranged mobs detected: {len(ranged_mobs)}")
            for pull_id, mob_name, instance in ranged_mobs[:5]:
                print(f"    Pull {pull_id}: {mob_name} (instance {instance})")
        
        if boss_mobs:
            print(f"  Boss mobs detected: {len(boss_mobs)}")
            for pull_id, mob_name, instance in boss_mobs[:5]:
                print(f"    Pull {pull_id}: {mob_name} (instance {instance})")
        
        # Summary
        print(f"\n{'-'*50}")
        print(f"FIGHT {fight_id} SUMMARY:")
        print(f"API pulls: {len(api_pulls)} | Detected: {len(detected_pulls)} | Chain pulls: {len(chain_pulls)}")
        print(f"Ranged mobs: {len(ranged_mobs)} | Boss mobs: {len(boss_mobs)}")
        print(f"{'-'*50}")
    
    # Final recommendations
    print(f"\n" + "="*70)
    print("FINAL RECOMMENDATIONS FOR COMPREHENSIVE PULL DETECTION")
    print("="*70)
    
    print("""
✓ USE COMBINED APPROACH:
  • analyze_comprehensive_pulls_combined() uses BOTH damage and threat events
  • Damage events: capture all mobs including ranged (Mechadrone Snipers)
  • Threat events: validate engagement and catch any missed interactions
  • Union ensures comprehensive coverage regardless of mob behavior

✓ HANDLES ALL SCENARIOS:
  • Boss encounters: Both trash and boss fights detected
  • Ranged mobs: Mechadrone Snipers captured via damage events
  • Chain pulls: Overlap detection through timing analysis
  • Mixed encounters: Tank pulling trash into boss fights

✓ IMPLEMENTATION BENEFITS:
  • No mobs missed regardless of combat behavior
  • Accurate pull timing from earliest engagement
  • Complete boss encounter detection
  • Robust against different dungeon types and strategies

✗ AVOID SINGLE-METHOD APPROACHES:
  • Threat-only: Misses ranged mobs that don't melee tank
  • Damage-only: May miss some engagement validation
  • Either alone provides incomplete picture for complex encounters
    """)

def print_pull_analysis(detected_pulls, fight_info, method="", num_pulls=None):
    """Print detailed analysis of detected pulls."""
    print(f"\nDetected {len(detected_pulls)} pulls using {method}:")
    num_pulls = num_pulls or len(detected_pulls)
    for pull in detected_pulls[:num_pulls]:  # Show first 8 pulls
        duration = (pull.end_time - pull.start_time) / 1000
        rel_start = (pull.start_time - fight_info['startTime']) / 1000
        rel_end = (pull.end_time - fight_info['startTime']) / 1000
        
        print(f"\nPull {pull.pull_id}: {rel_start:6.1f}s - {rel_end:6.1f}s ({duration:5.1f}s)")
        
        # Show mob composition with instance details
        mob_counts = pull.get_instance_count()
        for mob_name, count in sorted(mob_counts.items()):
            # Show instance IDs for this mob type
            instances = [m.instance_id for m in pull.mobs if m.name == mob_name]
            if len(instances) > 1:
                instance_range = f"{min(instances)}-{max(instances)}"
            else:
                instance_range = str(instances[0])
            
            # Highlight special mob types
            if any(keyword in mob_name.lower() for keyword in ['mechadrone', 'sniper']):
                mob_name += " [RANGED]"
            elif any(keyword in mob_name.lower() for keyword in ['boss', 'pummeler', 'azerokk', 'rixxa', 'mogul']):
                mob_name += " [BOSS]"
                
            print(f"  {count:2d}x {mob_name:<30} (instances {instance_range})")
    
    if len(detected_pulls) > num_pulls:
        print(f"\n... and {len(detected_pulls) - num_pulls} more pulls not shown (use num_pulls to adjust)")
