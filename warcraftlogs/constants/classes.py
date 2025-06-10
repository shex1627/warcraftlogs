specs_by_role = {
    "Tank": [
        {"class": "DeathKnight", "spec": "Blood"},
        {"class": "Druid", "spec": "Guardian"},
        {"class": "Monk", "spec": "Brewmaster"},
        {"class": "Paladin", "spec": "Protection"},
        {"class": "Warrior", "spec": "Protection"},
        {"class": "DemonHunter", "spec": "Vengeance"}
    ],
    "Healer": [
        {"class": "Druid", "spec": "Restoration"},
        {"class": "Monk", "spec": "Mistweaver"},
        {"class": "Paladin", "spec": "Holy"},
        {"class": "Priest", "spec": "Discipline"},
        {"class": "Priest", "spec": "Holy"},
        {"class": "Shaman", "spec": "Restoration"},
        {"class": "Evoker", "spec": "Preservation"}
    ],
    "Melee DPS": [
        {"class": "DeathKnight", "spec": "Frost"},
        {"class": "DeathKnight", "spec": "Unholy"},
        {"class": "Druid", "spec": "Feral"},
        {"class": "Hunter", "spec": "Survival"},
        {"class": "Monk", "spec": "Windwalker"},
        {"class": "Paladin", "spec": "Retribution"},
        {"class": "Rogue", "spec": "Assassination"},
        {"class": "Rogue", "spec": "Outlaw"},
        {"class": "Rogue", "spec": "Subtlety"},
        {"class": "Shaman", "spec": "Enhancement"},
        {"class": "Warrior", "spec": "Arms"},
        {"class": "Warrior", "spec": "Fury"},
        {"class": "DemonHunter", "spec": "Havoc"}
    ],
    "Ranged DPS": [
        {"class": "Druid", "spec": "Balance"},
        {"class": "Hunter", "spec": "BeastMastery"},
        {"class": "Hunter", "spec": "Marksmanship"},
        {"class": "Mage", "spec": "Arcane"},
        {"class": "Mage", "spec": "Fire"},
        {"class": "Mage", "spec": "Frost"},
        {"class": "Priest", "spec": "Shadow"},
        {"class": "Shaman", "spec": "Elemental"},
        {"class": "Warlock", "spec": "Affliction"},
        {"class": "Warlock", "spec": "Demonology"},
        {"class": "Warlock", "spec": "Destruction"},
        {"class": "Evoker", "spec": "Devastation"}
    ],
    "Support DPS": [
        {"class": "Evoker", "spec": "Augmentation"}
    ]
}

warcraft_classes_specs = [
{"class": "Death Knight", "spec": "Blood", "role": "Tank"},
{"class": "Death Knight", "spec": "Frost", "role": "Melee DPS"},
{"class": "Death Knight", "spec": "Unholy", "role": "Melee DPS"},
{"class": "Druid", "spec": "Balance", "role": "Ranged DPS"},
{"class": "Druid", "spec": "Feral", "role": "Melee DPS"},
{"class": "Druid", "spec": "Guardian", "role": "Tank"},
{"class": "Druid", "spec": "Restoration", "role": "Healer"},

{"class": "Hunter", "spec": "Beast Mastery", "role": "Ranged DPS"},
{"class": "Hunter", "spec": "Marksmanship", "role": "Ranged DPS"},
{"class": "Hunter", "spec": "Survival", "role": "Melee DPS"},

{"class": "Mage", "spec": "Arcane", "role": "Ranged DPS"},
{"class": "Mage", "spec": "Fire", "role": "Ranged DPS"},
{"class": "Mage", "spec": "Frost", "role": "Ranged DPS"},

{"class": "Monk", "spec": "Brewmaster", "role": "Tank"},
{"class": "Monk", "spec": "Mistweaver", "role": "Healer"},
{"class": "Monk", "spec": "Windwalker", "role": "Melee DPS"},

{"class": "Paladin", "spec": "Holy", "role": "Healer"},
{"class": "Paladin", "spec": "Protection", "role": "Tank"},
{"class": "Paladin", "spec": "Retribution", "role": "Melee DPS"},

{"class": "Priest", "spec": "Discipline", "role": "Healer"},
{"class": "Priest", "spec": "Holy", "role": "Healer"},
{"class": "Priest", "spec": "Shadow", "role": "Ranged DPS"},

{"class": "Rogue", "spec": "Assassination", "role": "Melee DPS"},
{"class": "Rogue", "spec": "Outlaw", "role": "Melee DPS"},
{"class": "Rogue", "spec": "Subtlety", "role": "Melee DPS"},

{"class": "Shaman", "spec": "Elemental", "role": "Ranged DPS"},
{"class": "Shaman", "spec": "Enhancement", "role": "Melee DPS"},
{"class": "Shaman", "spec": "Restoration", "role": "Healer"},

{"class": "Warlock", "spec": "Affliction", "role": "Ranged DPS"},
{"class": "Warlock", "spec": "Demonology", "role": "Ranged DPS"},
{"class": "Warlock", "spec": "Destruction", "role": "Ranged DPS"},

{"class": "Warrior", "spec": "Arms", "role": "Melee DPS"},
{"class": "Warrior", "spec": "Fury", "role": "Melee DPS"},
{"class": "Warrior", "spec": "Protection", "role": "Tank"},

{"class": "Demon Hunter", "spec": "Havoc", "role": "Melee DPS"},
{"class": "Demon Hunter", "spec": "Vengeance", "role": "Tank"},

{"class": "Evoker", "spec": "Devastation", "role": "Ranged DPS"},
{"class": "Evoker", "spec": "Preservation", "role": "Healer"},
{"class": "Evoker", "spec": "Augmentation", "role": "Support DPS"}
]

tww_season2_dungeons = [
    {"name": "Cinderbrew Meadery", "encounter_id": 12661},
    {"name": "Darkflame Cleft", "encounter_id": 12651},
    {"name": "Operation: Floodgate", "encounter_id": 12773},
    {"name": "Operation: Mechagon - Workshop", "encounter_id": 112098},
    {"name": "Priory of the Sacred Flame", "encounter_id": 12649},
    {"name": "The MOTHERLODE!!", "encounter_id": 61594},
    {"name": "The Rookery", "encounter_id": 12648},
    {"name": "Theater of Pain", "encounter_id": 62293}
]