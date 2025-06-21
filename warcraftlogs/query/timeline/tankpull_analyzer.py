import json
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
import warcraftlogs
from warcraftlogs.constants import TOKEN_DIR
from warcraftlogs import WarcraftLogsClient
from warcraftlogs.query.timeline.pull_analyzer import Pull, MobInstance

@dataclass
class TargetInfo:
    """Target information for cast events"""
    target_id: Optional[int] = None
    target_instance: Optional[int] = None
    target_name: Optional[str] = None
    target_game_id: Optional[int] = None

@dataclass
class CastEvent:
    timestamp: float
    ability_name: str
    ability_id: int
    ability_icon: str
    cast_duration: float
    seconds_from_pull_start: float
    pull_context: str  # "before_pull", "during_pull", "after_pull"
    # New target information
    target_info: Optional[TargetInfo] = None

@dataclass
class TankPullAnalysis:
    tank_name: str
    tank_id: int
    tank_spec: str
    tank_type: str
    pull_info: Pull
    cast_events: List[CastEvent]
    pre_pull_window_seconds: float
    post_pull_window_seconds: float
    fight_id: int
    report_code: str

class TankPullAnalyzer:
    """Tank pull analyzer with WarcraftLogs API integration"""
    
    def __init__(self, report_code: str, fight_id: int, client: WarcraftLogsClient = None, 
                 game_id_to_name: Dict[int, str] = None):
        self.report_code = report_code
        self.fight_id = fight_id
        self.client = client or WarcraftLogsClient(token_dir=TOKEN_DIR)
        self.tank_info = None
        self.abilities_cache = {}
        self.game_id_to_name = game_id_to_name or {}  # Dictionary of game_id to name
        self.actors_cache = {}  # Cache for actor information
        
    def get_tank_info(self) -> Dict[str, Any]:
        """Get tank information from the fight using WarcraftLogs API"""
        query = """
        query getTankInfo($reportCode: String!, $fightID: Int!) {
          reportData {
            report(code: $reportCode) {
              fights(fightIDs: [$fightID]) {
                startTime
                endTime
                name
              }
              playerDetails(fightIDs: [$fightID])
            }
          }
        }
        """
        
        result = self.client.query_public_api(query, {
            "reportCode": self.report_code, 
            "fightID": self.fight_id
        })
        
        # Parse tank info
        player_details = result['data']['reportData']['report']['playerDetails']['data']['playerDetails']
        tanks = player_details['tanks']
        
        if not tanks:
            raise ValueError("No tank found in the fight")
        
        tank = tanks[0]  # Assume first tank
        fight_data = result['data']['reportData']['report']['fights'][0]
        
        tank_info = {
            "tank_name": tank['name'],
            "tank_id": tank['id'],
            "tank_spec": tank['specs'][0]['spec'],
            "tank_type": tank['type'],
            "fight_start_time": fight_data['startTime'],
            "fight_end_time": fight_data['endTime'],
            "fight_name": fight_data['name']
        }
        
        return tank_info
    
    def get_abilities_info(self) -> Dict[int, Dict[str, str]]:
        """Get ability information from master data"""
        if self.abilities_cache:
            return self.abilities_cache
            
        query = """
        query getMasterData($reportCode: String!) {
          reportData {
            report(code: $reportCode) {
              masterData(translate: true) {
                abilities {
                  gameID
                  name
                  icon
                }
              }
            }
          }
        }
        """
        
        result = self.client.query_public_api(query, {"reportCode": self.report_code})
        abilities = result['data']['reportData']['report']['masterData']['abilities']
        
        # Cache abilities by gameID
        for ability in abilities:
            self.abilities_cache[ability['gameID']] = {
                "name": ability['name'],
                "icon": ability['icon']
            }
        
        return self.abilities_cache
    
    def get_actors_info(self) -> Dict[int, Dict[str, Any]]:
        """Get actor information from master data"""
        if self.actors_cache:
            return self.actors_cache
            
        query = """
        query getMasterData($reportCode: String!) {
          reportData {
            report(code: $reportCode) {
              masterData(translate: true) {
                actors {
                  id
                  name
                  gameID
                  type
                  subType
                }
              }
            }
          }
        }
        """
        
        result = self.client.query_public_api(query, {"reportCode": self.report_code})
        actors = result['data']['reportData']['report']['masterData']['actors']
        
        # Cache actors by ID
        for actor in actors:
            self.actors_cache[actor['id']] = {
                "name": actor['name'],
                "gameID": actor.get('gameID'),
                "type": actor.get('type'),
                "subType": actor.get('subType')
            }
        
        return self.actors_cache
    
    def create_pull_info(self, pull_data: Dict, chain_pull_info: List[Dict] = None) -> Pull:
        """Create PullInfo object from pull data and chain pull information"""
        pull_id = pull_data['pull_id']
        
        # Check if this is a chain pull
        is_chain = False
        prev_pull_id = None
        overlap_duration = None
        gap_time = None
        
        if chain_pull_info:
            for chain_info in chain_pull_info:
                if chain_info['pull_id'] == pull_id:
                    is_chain = True
                    prev_pull_id = chain_info['prev_pull_id']
                    overlap_duration = chain_info['overlap_duration']
                    gap_time = chain_info['gap_time']
                    break
        
        # Create MobInstance objects if mob data is provided
        mobs = None
        if 'mobs' in pull_data:
            mobs = []
            for mob_data in pull_data['mobs']:
                mob = MobInstance(
                    actor_id=mob_data['actor_id'],
                    instance_id=mob_data['instance_id'],
                    game_id=mob_data['game_id'],
                    name=mob_data['name'],
                    first_damage_time=mob_data.get('first_damage_time'),
                    last_activity_time=mob_data.get('last_activity_time'),
                    death_time=mob_data.get('death_time')
                )
                mobs.append(mob)
        
        return Pull(
            pull_id=pull_id,
            start_time=pull_data['start_time'],
            end_time=pull_data['end_time'],
            encounter_id=pull_data['encounter_id'],
            is_chain_pull=is_chain,
            prev_pull_id=prev_pull_id,
            overlap_duration=overlap_duration,
            gap_time=gap_time,
            mobs=mobs,
            x=pull_data.get('x'),
            y=pull_data.get('y')
        )
    
    def get_tank_casts_around_pull(self, pull_info: Pull, 
                                   pre_pull_seconds: float = 10, 
                                   post_pull_seconds: float = 5) -> List[CastEvent]:
        """Get tank casting events X seconds before and Y seconds after a pull"""
        
        # Calculate time windows (API uses milliseconds)
        window_start = pull_info.start_time - (pre_pull_seconds * 1000)
        window_end = pull_info.end_time + (post_pull_seconds * 1000)
        
        # Get cast events from API
        query = """
        query getCastEvents($reportCode: String!, $fightID: Int!, $tankID: Int!, $startTime: Float!, $endTime: Float!) {
          reportData {
            report(code: $reportCode) {
              events(
                fightIDs: [$fightID]
                dataType: Casts
                sourceID: $tankID
                startTime: $startTime
                endTime: $endTime
                limit: 1000
              ) {
                data
              }
            }
          }
        }
        """
        
        result = self.client.query_public_api(query, {
            "reportCode": self.report_code,
            "fightID": self.fight_id,
            "tankID": self.tank_info["tank_id"],
            "startTime": window_start,
            "endTime": window_end
        })
        
        # Get ability info
        abilities = self.get_abilities_info()
        
        # Get actor info for target resolution
        actors = self.get_actors_info()
        
        # Process events
        cast_events = []
        events_data = result['data']['reportData']['report']['events']['data']
        
        for event in events_data:
            if event.get('type') != 'cast':
                continue
                
            ability_id = event.get('abilityGameID', 0)
            ability_info = abilities.get(ability_id, {"name": "Unknown Ability", "icon": "inv_axe_02.jpg"})
            
            # Determine context
            timestamp = event['timestamp']
            if timestamp < pull_info.start_time:
                context = "before_pull"
            elif timestamp > pull_info.end_time:
                context = "after_pull"
            else:
                context = "during_pull"
            
            # Calculate seconds from pull start
            seconds_from_start = (timestamp - pull_info.start_time) / 1000
            
            # Skip if outside our analysis window
            if seconds_from_start < -pre_pull_seconds or seconds_from_start > post_pull_seconds:
                continue
            
            # Extract target information
            target_info = None
            target_id = event.get('targetID')
            target_instance = event.get('targetInstance')
            
            if target_id is not None:
                target_name = None
                target_game_id = None
                
                # Look up target name from actors
                if target_id in actors:
                    target_name = actors[target_id]['name']
                    target_game_id = actors[target_id].get('gameID')
                elif target_id == -1:
                    target_name = "Area/Self"
                    target_game_id = -1
                else:
                    # Try to get name from game_id_to_name mapping if available
                    if target_game_id and target_game_id in self.game_id_to_name:
                        target_name = self.game_id_to_name[target_game_id]
                    else:
                        target_name = f"Unknown Target ({target_id})"
                
                target_info = TargetInfo(
                    target_id=target_id,
                    target_instance=target_instance,
                    target_name=target_name,
                    target_game_id=target_game_id
                )
            
            cast_event = CastEvent(
                timestamp=timestamp,
                ability_name=ability_info["name"],
                ability_id=ability_id,
                ability_icon=ability_info["icon"],
                cast_duration=0,  # Could calculate from event duration if needed
                seconds_from_pull_start=seconds_from_start,
                pull_context=context,
                target_info=target_info
            )
            cast_events.append(cast_event)
        
        # Sort by timestamp
        cast_events.sort(key=lambda x: x.timestamp)
        
        return cast_events
    
    def analyze_pull(self, pull_data: Dict, chain_pull_info: List[Dict] = None,
                     pre_pull_seconds: float = 10, post_pull_seconds: float = 5) -> TankPullAnalysis:
        """Complete analysis of tank behavior around a specific pull"""
        
        # Get tank info if not already loaded
        if not self.tank_info:
            self.tank_info = self.get_tank_info()
        
        # Create pull info
        pull_info = self.create_pull_info(pull_data, chain_pull_info)
        pull_target_ids = [mob.actor_id for mob in pull_info.mobs]
        
        # Get cast events
        cast_events = self.get_tank_casts_around_pull(pull_info, pre_pull_seconds, post_pull_seconds)

        # filter cast events, make sure target are in pull_target_ids, it will still match different instance id
        # <to-do> filter out pull_target_ids and instance id combo, but the dungeon end time may not be correct
        cast_events = list(filter(lambda x: x.target_info.target_id in pull_target_ids if x.target_info and x.target_info.target_id is not -1 else True, cast_events))
        
        # Create analysis result
        analysis = TankPullAnalysis(
            tank_name=self.tank_info["tank_name"],
            tank_id=self.tank_info["tank_id"],
            tank_spec=self.tank_info["tank_spec"],
            tank_type=self.tank_info["tank_type"],
            pull_info=pull_info,
            cast_events=cast_events,
            pre_pull_window_seconds=pre_pull_seconds,
            post_pull_window_seconds=post_pull_seconds,
            fight_id=self.fight_id,
            report_code=self.report_code
        )
        
        return analysis
    
    def analyze_multiple_pulls(self, pulls_data: List[Dict], chain_pull_info: List[Dict] = None,
                              pre_pull_seconds: float = 10, post_pull_seconds: float = 5) -> List[TankPullAnalysis]:
        """Analyze tank behavior for multiple pulls"""
        
        analyses = []
        pre_defined_pre_pull_seconds = pre_pull_seconds
        for idx in range(len(pulls_data)):
            pull_data = pulls_data[idx]
            prev_pull_data = pulls_data[idx - 1] if idx > 0 else None
            if prev_pull_data:
                # adjust pre_pull_seconds based on previous pull end time if necessary
                pull_time_diff = (pull_data['start_time'] - prev_pull_data['end_time']) / 1000
                #print(f"Pull {pull_data['pull_id']} time diff from previous pull: {pull_time_diff:.1f} seconds")
                if pull_time_diff < 0:
                    continue  # Skip if pull starts before previous ends (chain pull)
                pre_pull_seconds = min(pre_defined_pre_pull_seconds, pull_time_diff)
                #print(f"Adjusted pre_pull_seconds for pull {pull_data['pull_id']}: {pre_pull_seconds:.1f} seconds")

            analysis = self.analyze_pull(pull_data, chain_pull_info, pre_pull_seconds, post_pull_seconds)
            analyses.append(analysis)
        
        return analyses
    
    def to_dict(self, analysis: TankPullAnalysis) -> Dict[str, Any]:
        """Convert analysis to dictionary for JSON serialization"""
        return asdict(analysis)
    
    def print_analysis_summary(self, analysis: TankPullAnalysis) -> None:
        """Print a formatted summary of the pull analysis"""
        print(f"\n{'='*60}")
        print(f"PULL {analysis.pull_info.pull_id} ANALYSIS")
        print(f"{'='*60}")
        print(f"Tank: {analysis.tank_name} ({analysis.tank_spec} {analysis.tank_type})")
        print(f"Report: {analysis.report_code} | Fight: {analysis.fight_id}")
        
        pull_duration = (analysis.pull_info.end_time - analysis.pull_info.start_time) / 1000
        print(f"Pull Duration: {pull_duration:.1f} seconds")
        
        if analysis.pull_info.is_chain_pull:
            print(f"⛓️  CHAIN PULL (follows pull {analysis.pull_info.prev_pull_id})")
            print(f"   Overlap: {analysis.pull_info.overlap_duration:.1f}s | Gap: {analysis.pull_info.gap_time:.1f}s")
        else:
            print(f"🎯 STANDARD PULL")
        
        print(f"Analysis Window: -{analysis.pre_pull_window_seconds}s to +{analysis.post_pull_window_seconds}s")
        
        # Group events by context
        pre_pull_events = [e for e in analysis.cast_events if e.pull_context == "before_pull"]
        during_pull_events = [e for e in analysis.cast_events if e.pull_context == "during_pull"]
        after_pull_events = [e for e in analysis.cast_events if e.pull_context == "after_pull"]
        
        if pre_pull_events:
            print(f"\n📋 PRE-PULL PREPARATION ({len(pre_pull_events)} casts):")
            for event in pre_pull_events:
                target_str = ""
                if event.target_info and event.target_info.target_name:
                    if event.target_info.target_instance:
                        target_str = f" → {event.target_info.target_name}#{event.target_info.target_instance}"
                    else:
                        target_str = f" → {event.target_info.target_name}"
                print(f"   {event.seconds_from_pull_start:+6.1f}s: {event.ability_name}{target_str}")
        
        if during_pull_events:
            print(f"\n⚔️  PULL EXECUTION ({len(during_pull_events)} casts):")
            # Show first 10 casts to avoid clutter
            for event in during_pull_events[:10]:
                target_str = ""
                if event.target_info and event.target_info.target_name:
                    if event.target_info.target_instance:
                        target_str = f" → {event.target_info.target_name}#{event.target_info.target_instance}"
                    else:
                        target_str = f" → {event.target_info.target_name}"
                print(f"   {event.seconds_from_pull_start:+6.1f}s: {event.ability_name}{target_str}")
            if len(during_pull_events) > 10:
                print(f"   ... and {len(during_pull_events) - 10} more casts during pull")
        
        if after_pull_events:
            print(f"\n🏁 POST-PULL ACTIONS ({len(after_pull_events)} casts):")
            for event in after_pull_events:
                target_str = ""
                if event.target_info and event.target_info.target_name:
                    if event.target_info.target_instance:
                        target_str = f" → {event.target_info.target_name}#{event.target_info.target_instance}"
                    else:
                        target_str = f" → {event.target_info.target_name}"
                print(f"   {event.seconds_from_pull_start:+6.1f}s: {event.ability_name}{target_str}")


def analyze_tank_pulls_for_fight(report_code: str, fight_id: int, pulls_data: List[Dict], 
                                 chain_pull_info: List[Dict] = None,
                                 pre_pull_seconds: float = 10, post_pull_seconds: float = 5,
                                 client: WarcraftLogsClient = None,
                                 game_id_to_name: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """
    Main function to analyze tank casting behavior around pulls
    
    Args:
        report_code: WarcraftLogs report code
        fight_id: Fight ID 
        pulls_data: List of pull dictionaries with pull_id, start_time, end_time, encounter_id
        chain_pull_info: List of chain pull information with overlap data
        pre_pull_seconds: Seconds before pull start to analyze
        post_pull_seconds: Seconds after pull end to analyze
        client: WarcraftLogs client instance
        game_id_to_name: Dictionary mapping game IDs to mob names
    
    Returns:
        List of tank pull analysis dictionaries
    """
    
    analyzer = TankPullAnalyzer(report_code, fight_id, client, game_id_to_name)
    
    analyses = analyzer.analyze_multiple_pulls(
        pulls_data, chain_pull_info, pre_pull_seconds, post_pull_seconds
    )
    
    # Convert to dictionaries for JSON serialization
    return [analyzer.to_dict(analysis) for analysis in analyses]


def print_tank_pull_report(report_code: str, fight_id: int, pulls_data: List[Dict], 
                          chain_pull_info: List[Dict] = None,
                          pre_pull_seconds: float = 10, post_pull_seconds: float = 5,
                          client: WarcraftLogsClient = None,
                          game_id_to_name: Dict[int, str] = None) -> None:
    """
    Print a formatted report of tank pull analysis
    """
    
    analyzer = TankPullAnalyzer(report_code, fight_id, client, game_id_to_name)
    
    analyses = analyzer.analyze_multiple_pulls(
        pulls_data, chain_pull_info, pre_pull_seconds, post_pull_seconds
    )
    
    print(f"{'='*80}")
    print(f"TANK PULL ANALYSIS REPORT")
    print(f"{'='*80}")
    print(f"Report: {report_code} | Fight: {fight_id}")
    
    if analyses:
        first_analysis = analyses[0]
        print(f"Tank: {first_analysis.tank_name} ({first_analysis.tank_spec} {first_analysis.tank_type})")
    
    print(f"Analyzed Pulls: {len(analyses)}")
    
    chain_pulls = [a for a in analyses if a.pull_info.is_chain_pull]
    if chain_pulls:
        print(f"Chain Pulls: {len(chain_pulls)} ({[a.pull_info.pull_id for a in chain_pulls]})")
    
    for analysis in analyses:
        analyzer.print_analysis_summary(analysis)


# Example usage
if __name__ == "__main__":
    # Sample data using your MobInstance structure
    pulls_data = [
        {
            'pull_id': 1,
            'start_time': 9654647,
            'end_time': 9695371,
            'encounter_id': 0,
            'mobs': [
                {
                    'actor_id': 7,
                    'instance_id': 1,
                    'game_id': 228144,
                    'name': 'Darkfuse Soldier',
                    'first_damage_time': 9654647,
                    'last_activity_time': 9691166,
                    'death_time': None
                },
                {
                    'actor_id': 8,
                    'instance_id': 1,
                    'game_id': 229250,
                    'name': 'Venture Co. Contractor',
                    'first_damage_time': 9656000,
                    'last_activity_time': 9689294,
                    'death_time': None
                }
            ],
            'x': None,
            'y': None
        }
    ]
    
    chain_pull_info = [
        {'pull_id': 8, 'prev_pull_id': 7, 'overlap_duration': 27.575, 'gap_time': -27.575},
        {'pull_id': 9, 'prev_pull_id': 8, 'overlap_duration': 2.984, 'gap_time': -2.984},
        {'pull_id': 13, 'prev_pull_id': 12, 'overlap_duration': 27.734, 'gap_time': -27.734}
    ]
    
    game_id_to_name = {
        228144: 'Darkfuse Soldier',
        229250: 'Venture Co. Contractor',
        230740: 'Shreddinator 3000',
        231014: 'Loaderbot',
        229686: 'Venture Co. Surveyor'
    }
    
    try:
        print_tank_pull_report(
            "XCWdVDKTnkAhrZzB", 1, pulls_data, 
            chain_pull_info=chain_pull_info,
            pre_pull_seconds=15, 
            post_pull_seconds=8,
            game_id_to_name=game_id_to_name
        )
        
        print(f"\n{'='*80}")
        print("Tank Pull Analyzer v11 - Implementation Complete")
        print("="*80)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Note: Requires valid WarcraftLogs API token.")

from typing import Dict, List, Any, Optional
from datetime import datetime

def format_tank_pull_analysis(analysis: TankPullAnalysis, 
                             show_all_casts: bool = False,
                             max_during_pull_casts: int = 15) -> str:
    """
    Format TankPullAnalysis into human-readable text
    
    Args:
        analysis: TankPullAnalysis object
        show_all_casts: If True, show all cast events. If False, limit during-pull casts
        max_during_pull_casts: Maximum number of during-pull casts to show
    
    Returns:
        Formatted string suitable for console output or Streamlit
    """
    
    # Header
    lines = []
    lines.append("═" * 80)
    lines.append(f"🛡️  TANK PULL ANALYSIS - PULL {analysis.pull_info.pull_id}")
    lines.append("═" * 80)
    
    # Tank Information
    lines.append(f"👤 Tank: {analysis.tank_name} ({analysis.tank_spec} {analysis.tank_type})")
    lines.append(f"📊 Report: {analysis.report_code} | Fight: {analysis.fight_id}")
    
    # Pull Duration and Type
    pull_duration = (analysis.pull_info.end_time - analysis.pull_info.start_time) / 1000
    lines.append(f"⏱️  Pull Duration: {pull_duration:.1f} seconds")
    
    if analysis.pull_info.is_chain_pull:
        lines.append(f"⛓️  CHAIN PULL (continues from pull {analysis.pull_info.prev_pull_id})")
        lines.append(f"   📏 Overlap: {analysis.pull_info.overlap_duration:.1f}s | Gap: {analysis.pull_info.gap_time:+.1f}s")
    else:
        lines.append(f"🎯 STANDARD PULL")
    
    # Analysis Window
    lines.append(f"🔍 Analysis Window: -{analysis.pre_pull_window_seconds}s to +{analysis.post_pull_window_seconds}s from pull start")
    
    # Mob Information
    if analysis.pull_info.mobs:
        lines.append(f"\n🏹 MOBS IN PULL ({len(analysis.pull_info.mobs)} total):")
        
        # Group mobs by type for cleaner display
        mob_groups = {}
        for mob in analysis.pull_info.mobs:
            mob_key = f"{mob.name} (ID: {mob.game_id})"
            if mob_key not in mob_groups:
                mob_groups[mob_key] = []
            mob_groups[mob_key].append(mob)
        
        for mob_type, instances in mob_groups.items():
            if len(instances) == 1:
                mob = instances[0]
                lines.append(f"   • {mob_type} - Instance #{mob.instance_id}")
            else:
                instance_nums = [str(mob.instance_id) for mob in instances]
                lines.append(f"   • {mob_type} - Instances: {', '.join(instance_nums)}")
    
    # Group cast events by context
    pre_pull_events = [e for e in analysis.cast_events if e.pull_context == "before_pull"]
    during_pull_events = [e for e in analysis.cast_events if e.pull_context == "during_pull"]
    after_pull_events = [e for e in analysis.cast_events if e.pull_context == "after_pull"]
    
    # Pre-pull behavior
    if pre_pull_events:
        lines.append(f"\n📋 PRE-PULL PREPARATION ({len(pre_pull_events)} casts):")
        for event in pre_pull_events:
            target_str = format_target_info(event.target_info)
            lines.append(f"   {event.seconds_from_pull_start:+6.1f}s: {event.ability_name}{target_str}")
    else:
        lines.append(f"\n📋 PRE-PULL PREPARATION: No casts detected")
    
    # During pull execution
    if during_pull_events:
        total_during = len(during_pull_events)
        showing = min(total_during, max_during_pull_casts) if not show_all_casts else total_during
        
        lines.append(f"\n⚔️  PULL EXECUTION ({total_during} total casts):")
        
        events_to_show = during_pull_events if show_all_casts else during_pull_events[:max_during_pull_casts]
        
        for event in events_to_show:
            target_str = format_target_info(event.target_info)
            lines.append(f"   {event.seconds_from_pull_start:+6.1f}s: {event.ability_name}{target_str}")
        
        if not show_all_casts and total_during > max_during_pull_casts:
            lines.append(f"   ... and {total_during - max_during_pull_casts} more casts")
    else:
        lines.append(f"\n⚔️  PULL EXECUTION: No casts detected")
    
    # Post-pull actions
    if after_pull_events:
        lines.append(f"\n🏁 POST-PULL ACTIONS ({len(after_pull_events)} casts):")
        for event in after_pull_events:
            target_str = format_target_info(event.target_info)
            lines.append(f"   {event.seconds_from_pull_start:+6.1f}s: {event.ability_name}{target_str}")
    
    # Analysis Summary
    lines.append(f"\n📈 SUMMARY:")
    lines.append(f"   • Pre-pull casts: {len(pre_pull_events)}")
    lines.append(f"   • During-pull casts: {len(during_pull_events)}")
    lines.append(f"   • Post-pull casts: {len(after_pull_events)}")
    lines.append(f"   • Total analyzed: {len(analysis.cast_events)} casts")
    
    # Key insights
    if pre_pull_events or during_pull_events:
        lines.append(f"\n🔍 KEY INSIGHTS:")
        
        if pre_pull_events:
            first_pre_pull = pre_pull_events[0]
            lines.append(f"   • Pre-pull preparation: {first_pre_pull.ability_name} at {first_pre_pull.seconds_from_pull_start:+.1f}s")
        
        if during_pull_events:
            first_cast = during_pull_events[0]
            lines.append(f"   • Pull initiation: {first_cast.ability_name} at {first_cast.seconds_from_pull_start:+.1f}s")
            
            # Find first targeted ability
            first_targeted = next((e for e in during_pull_events 
                                 if e.target_info and e.target_info.target_id and e.target_info.target_id != -1), None)
            if first_targeted:
                lines.append(f"   • First target: {first_targeted.target_info.target_name} with {first_targeted.ability_name}")
        
        # Ability frequency analysis
        ability_counts = {}
        for event in during_pull_events[:10]:  # First 10 casts
            ability_counts[event.ability_name] = ability_counts.get(event.ability_name, 0) + 1
        
        if ability_counts:
            most_used = max(ability_counts.items(), key=lambda x: x[1])
            if most_used[1] > 1:
                lines.append(f"   • Most used early ability: {most_used[0]} ({most_used[1]} times)")
    
    lines.append("═" * 80)
    
    return "\n".join(lines)


def format_target_info(target_info: Optional[TargetInfo]) -> str:
    """Helper function to format target information"""
    if not target_info or not target_info.target_name:
        return ""
    
    if target_info.target_name in ["Area/Self", "Environment"]:
        return " → Area/Self"
    elif target_info.target_instance:
        return f" → {target_info.target_name}#{target_info.target_instance}"
    else:
        return f" → {target_info.target_name}"


def print_tank_pull_analysis(analysis: TankPullAnalysis, 
                            show_all_casts: bool = False,
                            max_during_pull_casts: int = 15) -> str:
    """
    Print tank pull analysis to console and return formatted string
    
    Args:
        analysis: TankPullAnalysis object
        show_all_casts: If True, show all cast events
        max_during_pull_casts: Maximum during-pull casts to show
    
    Returns:
        Formatted string for Streamlit or other display
    """
    formatted_text = format_tank_pull_analysis(analysis, show_all_casts, max_during_pull_casts)
    print(formatted_text)
    return formatted_text


# Streamlit-specific formatting function
def format_for_streamlit(analysis: TankPullAnalysis, 
                        show_all_casts: bool = False,
                        max_during_pull_casts: int = 15) -> str:
    """
    Format tank pull analysis specifically for Streamlit display
    Uses markdown formatting for better rendering
    """
    
    lines = []
    
    # Header with markdown
    lines.append("# 🛡️ Tank Pull Analysis")
    lines.append(f"## Pull {analysis.pull_info.pull_id}")
    
    # Tank info in a nice format
    pull_duration = (analysis.pull_info.end_time - analysis.pull_info.start_time) / 1000
    
    lines.append("### 📊 Basic Information")
    lines.append(f"- **Tank:** {analysis.tank_name} ({analysis.tank_spec} {analysis.tank_type})")
    lines.append(f"- **Report:** `{analysis.report_code}` | **Fight:** {analysis.fight_id}")
    lines.append(f"- **Duration:** {pull_duration:.1f} seconds")
    
    if analysis.pull_info.is_chain_pull:
        lines.append(f"- **Type:** ⛓️ Chain Pull (from pull {analysis.pull_info.prev_pull_id})")
        lines.append(f"- **Overlap:** {analysis.pull_info.overlap_duration:.1f}s | **Gap:** {analysis.pull_info.gap_time:+.1f}s")
    else:
        lines.append(f"- **Type:** 🎯 Standard Pull")
    
    # Mobs section
    if analysis.pull_info.mobs:
        lines.append(f"### 🏹 Mobs ({len(analysis.pull_info.mobs)} total)")
        
        mob_groups = {}
        for mob in analysis.pull_info.mobs:
            if mob.name not in mob_groups:
                mob_groups[mob.name] = []
            mob_groups[mob.name].append(mob.instance_id)
        
        for mob_name, instances in mob_groups.items():
            if len(instances) == 1:
                lines.append(f"- {mob_name} (#{instances[0]})")
            else:
                lines.append(f"- {mob_name} (#{', #'.join(map(str, sorted(instances)))})")
    
    # Cast events
    pre_pull_events = [e for e in analysis.cast_events if e.pull_context == "before_pull"]
    during_pull_events = [e for e in analysis.cast_events if e.pull_context == "during_pull"]
    after_pull_events = [e for e in analysis.cast_events if e.pull_context == "after_pull"]
    
    if pre_pull_events:
        lines.append("### 📋 Pre-Pull Preparation")
        for event in pre_pull_events:
            target_str = format_target_info(event.target_info)
            lines.append(f"- `{event.seconds_from_pull_start:+6.1f}s` **{event.ability_name}**{target_str}")
    
    if during_pull_events:
        total_during = len(during_pull_events)
        lines.append(f"### ⚔️ Pull Execution ({total_during} casts)")
        
        events_to_show = during_pull_events if show_all_casts else during_pull_events[:max_during_pull_casts]
        
        for event in events_to_show:
            target_str = format_target_info(event.target_info)
            lines.append(f"- `{event.seconds_from_pull_start:+6.1f}s` **{event.ability_name}**{target_str}")
        
        if not show_all_casts and total_during > max_during_pull_casts:
            lines.append(f"- *...and {total_during - max_during_pull_casts} more casts*")
    
    if after_pull_events:
        lines.append("### 🏁 Post-Pull Actions")
        for event in after_pull_events:
            target_str = format_target_info(event.target_info)
            lines.append(f"- `{event.seconds_from_pull_start:+6.1f}s` **{event.ability_name}**{target_str}")
    
    # Summary
    lines.append("### 📈 Summary")
    lines.append(f"- **Pre-pull:** {len(pre_pull_events)} casts")
    lines.append(f"- **During pull:** {len(during_pull_events)} casts") 
    lines.append(f"- **Post-pull:** {len(after_pull_events)} casts")
    lines.append(f"- **Total analyzed:** {len(analysis.cast_events)} casts")
    
    return "\n".join(lines)
