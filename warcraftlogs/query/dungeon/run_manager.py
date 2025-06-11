import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pickle

# recursively convert defaultdict to regular dict
def convert_defaultdict_to_dict(d):
    """
    Recursively convert defaultdict to regular dict.
    
    Args:
        d: The defaultdict to convert
    
    Returns:
        Regular dict with same structure
    """
    if isinstance(d, defaultdict):
        d = {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    return d

class MythicPlusRunManager:
    """
    Manages mythic+ run data with efficient storage and retrieval.
    
    Stores run records organized by dungeon, keystone level, class, spec, and item level bracket.
    Each report record contains only the data for the specific player matching the criteria.
    """
    
    def __init__(self):
        """Initialize the run manager with empty data structures."""
        # Structure: {dungeon: {key_level: {class_name: {spec_name: {ilvl_bracket: [run_records]}}}}}
        self.runs_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))))
        
        # Keep track of unique reports to avoid duplicates
        # Structure: {(report_id, fight_id): {dungeon, key_level, players_added}}
        self.report_tracking = {}
        
        # Statistics tracking
        self.stats = {
            'total_runs': 0,
            'total_reports': 0,
            'players_by_class': defaultdict(int),
            'players_by_spec': defaultdict(int),
            'runs_by_dungeon': defaultdict(int)
        }
    
    def add_runs(self, runs: List[Dict], target_class: str = None, target_spec: str = None) -> int:
        """
        Add multiple runs to the repository.
        
        Args:
            runs: List of run dictionaries from get_mythic_plus_runs()
            target_class: Optional class filter - only store players of this class
            target_spec: Optional spec filter - only store players of this spec
            
        Returns:
            Integer: Number of new player records added
        """
        added_count = 0
        
        for run in runs:
            added_count += self.add_run(run, target_class, target_spec)
            
        return added_count
    
    def add_run(self, run: Dict, target_class: str = None, target_spec: str = None) -> int:
        """
        Add a single run to the repository.
        
        Args:
            run: Run dictionary from get_mythic_plus_runs()
            target_class: Optional class filter - only store players of this class
            target_spec: Optional spec filter - only store players of this spec
            
        Returns:
            Integer: Number of new player records added
        """
        report_key = (run['report_id'], run['fight_id'])
        dungeon = self._get_dungeon_from_encounter(run.get('encounter_id', ''))
        
        # If we don't know the dungeon, try to infer it or skip
        if not dungeon:
            # Could add logic here to infer dungeon from other data
            return 0
        
        added_count = 0
        
        # Track this report
        if report_key not in self.report_tracking:
            self.report_tracking[report_key] = {
                'dungeon': dungeon,
                'key_level': run['bracket'],
                'players_added': set()
            }
            self.stats['total_reports'] += 1
        
        # Process each player in the run
        for player in run['players']:
            player_class = player['class']
            player_spec = player['spec']
            ilvl_bracket = player['item_level_bracket']
            
            # Apply filters if specified
            if target_class and player_class != target_class:
                continue
            if target_spec and player_spec != target_spec:
                continue
            
            # Check if we've already added this player from this report
            player_key = f"{player['character_name']}_{player_class}_{player_spec}"
            if player_key in self.report_tracking[report_key]['players_added']:
                continue
            
            # Create the run record for this specific player
            run_record = {
                'report_id': run['report_id'],
                'fight_id': run['fight_id'],
                'bracket': run['bracket'],
                'datetime': run['datetime'],
                'player': player.copy()  # Store only this player's data
            }
            
            # Store the run record
            self.runs_data[dungeon][run['bracket']][player_class][player_spec][ilvl_bracket].append(run_record)
            
            # Track that we've added this player
            self.report_tracking[report_key]['players_added'].add(player_key)
            
            # Update statistics
            self.stats['total_runs'] += 1
            self.stats['players_by_class'][player_class] += 1
            self.stats['players_by_spec'][f"{player_class}_{player_spec}"] += 1
            self.stats['runs_by_dungeon'][dungeon] += 1
            
            added_count += 1
        
        return added_count
    
    def get_runs(self, dungeon: str, keystone_level: int, class_name: str = None, 
                 spec_name: str = None, ilvl_bracket: int = None) -> List[Dict]:
        """
        Retrieve runs matching the specified criteria.
        
        Args:
            dungeon: Dungeon name
            keystone_level: Keystone level
            class_name: Optional class filter
            spec_name: Optional spec filter  
            ilvl_bracket: Optional item level bracket filter
            
        Returns:
            List of run records matching criteria
        """
        results = []
        
        if dungeon not in self.runs_data:
            return results
        
        if keystone_level not in self.runs_data[dungeon]:
            return results
        
        # If class is specified, filter to that class
        if class_name:
            if class_name not in self.runs_data[dungeon][keystone_level]:
                return results
            class_data = {class_name: self.runs_data[dungeon][keystone_level][class_name]}
        else:
            class_data = self.runs_data[dungeon][keystone_level]
        
        # Iterate through classes
        for cls, specs_data in class_data.items():
            # If spec is specified, filter to that spec
            if spec_name:
                if spec_name not in specs_data:
                    continue
                spec_data = {spec_name: specs_data[spec_name]}
            else:
                spec_data = specs_data
            
            # Iterate through specs
            for spec, ilvl_data in spec_data.items():
                # If ilvl_bracket is specified, filter to that bracket
                if ilvl_bracket is not None:
                    if ilvl_bracket not in ilvl_data:
                        continue
                    bracket_data = {ilvl_bracket: ilvl_data[ilvl_bracket]}
                else:
                    bracket_data = ilvl_data
                
                # Collect all runs from matching brackets
                for bracket, runs in bracket_data.items():
                    results.extend(runs)
        
        # Sort by datetime (most recent first)
        results.sort(key=lambda x: x['datetime'], reverse=True)
        return results
    
    def get_available_dungeons(self) -> List[str]:
        """Get list of available dungeons."""
        return list(self.runs_data.keys())
    
    def get_available_key_levels(self, dungeon: str) -> List[int]:
        """Get list of available keystone levels for a dungeon."""
        if dungeon not in self.runs_data:
            return []
        return sorted(self.runs_data[dungeon].keys())
    
    def get_available_classes(self, dungeon: str = None, keystone_level: int = None) -> List[str]:
        """Get list of available classes, optionally filtered by dungeon/key level."""
        classes = set()
        
        if dungeon and keystone_level:
            if dungeon in self.runs_data and keystone_level in self.runs_data[dungeon]:
                classes.update(self.runs_data[dungeon][keystone_level].keys())
        elif dungeon:
            if dungeon in self.runs_data:
                for key_data in self.runs_data[dungeon].values():
                    classes.update(key_data.keys())
        else:
            for dungeon_data in self.runs_data.values():
                for key_data in dungeon_data.values():
                    classes.update(key_data.keys())
        
        return sorted(classes)
    
    def get_available_specs(self, dungeon: str = None, keystone_level: int = None, 
                           class_name: str = None) -> List[str]:
        """Get list of available specs, optionally filtered by dungeon/key level/class."""
        specs = set()
        
        def collect_specs_from_class_data(class_data):
            if class_name:
                if class_name in class_data:
                    specs.update(class_data[class_name].keys())
            else:
                for spec_data in class_data.values():
                    specs.update(spec_data.keys())
        
        if dungeon and keystone_level:
            if dungeon in self.runs_data and keystone_level in self.runs_data[dungeon]:
                collect_specs_from_class_data(self.runs_data[dungeon][keystone_level])
        elif dungeon:
            if dungeon in self.runs_data:
                for key_data in self.runs_data[dungeon].values():
                    collect_specs_from_class_data(key_data)
        else:
            for dungeon_data in self.runs_data.values():
                for key_data in dungeon_data.values():
                    collect_specs_from_class_data(key_data)
        
        return sorted(specs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the stored data."""
        stats = self.stats.copy()
        stats['available_dungeons'] = len(self.runs_data)
        stats['unique_reports'] = len(self.report_tracking)
        
        # Calculate average runs per report
        if stats['unique_reports'] > 0:
            stats['avg_players_per_report'] = stats['total_runs'] / stats['unique_reports']
        else:
            stats['avg_players_per_report'] = 0
        
        return stats
    
    def clear_data(self):
        """Clear all stored data."""
        self.runs_data.clear()
        self.report_tracking.clear()
        self.stats = {
            'total_runs': 0,
            'total_reports': 0,
            'players_by_class': defaultdict(int),
            'players_by_spec': defaultdict(int),
            'runs_by_dungeon': defaultdict(int)
        }
    
    def save_to_file(self, filepath: str):
        """Save the manager state to a file."""
        # create a copy of data and convert defaultdicts to regular dicts
        runs_data = convert_defaultdict_to_dict(self.runs_data.copy())
        report_tracking = convert_defaultdict_to_dict(self.report_tracking.copy())
        #stats = convert_defaultdict_to_dict(self.stats.copy())

        data = {
            'runs_data': dict(runs_data),
            'report_tracking': dict(report_tracking),
            #'stats': dict(stats)
        }
        
        if filepath.endswith('.json'):
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        else:  # Default to pickle
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
    
    def load_from_file(self, filepath: str):
        """Load the manager state from a file."""
        if filepath.endswith('.json'):
            with open(filepath, 'r') as f:
                data = json.load(f)
        else:  # Default to pickle
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
        
        # Reconstruct defaultdicts
        self.runs_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))))
        for dungeon, key_data in data['runs_data'].items():
            for key_level, class_data in key_data.items():
                for class_name, spec_data in class_data.items():
                    for spec_name, ilvl_data in spec_data.items():
                        for ilvl_bracket, runs in ilvl_data.items():
                            self.runs_data[dungeon][int(key_level)][class_name][spec_name][int(ilvl_bracket)] = runs
        
        self.report_tracking = data['report_tracking']
        #self.stats = defaultdict(int, data['stats'])
        #self.stats['players_by_class'] = defaultdict(int, data['stats'].get('players_by_class', {}))
        #self.stats['players_by_spec'] = defaultdict(int, data['stats'].get('players_by_spec', {}))
        #self.stats['runs_by_dungeon'] = defaultdict(int, data['stats'].get('runs_by_dungeon', {}))
    
    def add_from_file(self, filepath: str) -> Dict[str, int]:
        """
        Add data from file to existing data.
        
        Args:
            filepath: Path to .pkl or .json file containing run data
            
        Returns:
            Dict with statistics about merged data:
                - new_runs: Number of new runs added
                - new_reports: Number of new reports added
        """
        # Load data from file
        if filepath.endswith('.json'):
            with open(filepath, 'r') as f:
                data = json.load(f)
        else:  # Default to pickle
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
                
        stats = {'new_runs': 0, 'new_reports': 0}
        
        # Merge runs_data
        for dungeon, key_data in data['runs_data'].items():
            for key_level, class_data in key_data.items():
                for class_name, spec_data in class_data.items():
                    for spec_name, ilvl_data in spec_data.items():
                        for ilvl_bracket, runs in ilvl_data.items():
                            key_level = int(key_level)
                            ilvl_bracket = int(ilvl_bracket)
                            
                            # Add each run if not already present
                            for run in runs:
                                report_key = (run['report_id'], run['fight_id'])
                                player_key = f"{run['player']['character_name']}_{run['player']['class']}_{run['player']['spec']}"
                                
                                # Check if run already exists
                                if (report_key in self.report_tracking and 
                                    player_key in self.report_tracking[report_key]['players_added']):
                                    continue
                                    
                                # Add run
                                self.runs_data[dungeon][key_level][class_name][spec_name][ilvl_bracket].append(run)
                                
                                # Update tracking
                                if report_key not in self.report_tracking:
                                    self.report_tracking[report_key] = {
                                        'dungeon': dungeon,
                                        'key_level': key_level,
                                        'players_added': {player_key}
                                    }
                                    stats['new_reports'] += 1
                                else:
                                    self.report_tracking[report_key]['players_added'].add(player_key)
                                
                                # Update statistics
                                self.stats['total_runs'] += 1
                                self.stats['players_by_class'][class_name] += 1
                                self.stats['players_by_spec'][f"{class_name}_{spec_name}"] += 1
                                self.stats['runs_by_dungeon'][dungeon] += 1
                                stats['new_runs'] += 1
        return stats

    def _get_dungeon_from_encounter(self, encounter_id: str) -> str:
        """Map encounter ID to dungeon name (helper method)."""
        # You might want to store this mapping or infer it from the data
        encounter_to_dungeon = {
            '12661': 'Cinderbrew Meadery',
            '12651': 'Darkflame Cleft', 
            '12773': 'Operation: Floodgate',
            '112098': 'Operation: Mechagon - Workshop',
            '12649': 'Priory of the Sacred Flame',
            '61594': 'The MOTHERLODE!!',
            '12648': 'The Rookery',
            '62293': 'Theater of Pain'
        }
        return encounter_to_dungeon.get(str(encounter_id), '')
    
    def get_summary(self, dungeon: str = None, keystone_level: int = None) -> Dict[str, Any]:
        """Get a summary of runs for specified criteria."""
        runs = self.get_runs(dungeon or '', keystone_level or 0) if dungeon and keystone_level else []
        
        if not runs:
            return {'total_runs': 0}
        
        # Analyze the runs
        classes = defaultdict(int)
        specs = defaultdict(int)
        ilvl_brackets = defaultdict(int)
        dates = []
        
        for run in runs:
            player = run['player']
            classes[player['class']] += 1
            specs[f"{player['class']}_{player['spec']}"] += 1
            ilvl_brackets[player['item_level_bracket']] += 1
            dates.append(run['datetime'])
        
        return {
            'total_runs': len(runs),
            'classes': dict(classes),
            'specs': dict(specs),
            'ilvl_brackets': dict(ilvl_brackets),
            'date_range': {
                'earliest': min(dates) if dates else None,
                'latest': max(dates) if dates else None
            }
        }
