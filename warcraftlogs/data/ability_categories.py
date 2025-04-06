ABILITY_CATEGORIES = {
    "basic_rotation": [
        "Soul Fragment", "Fracture", "Starfire", "Pyroblast", "Shadowy Apparition",
        "Soul Cleave", "Fire Blast", "Tiger Palm", "Wrath", "Void Blast", "Scorch",
        "Mind Blast", "Flamestrike", "Devouring Plague", "Rising Sun Kick",
        "Starsurge", "Phoenix Flames", "Blackout Kick", "Starfall", "Vampiric Touch",
        "Shadow Word: Death", "Fireball", "Mind Flay: Insanity", "Reaver's Glaive",
        "Mind Flay", "Moonfire", "Spinning Crane Kick", "Sunfire", "Crackling Jade Lightning",
        "Shadow Crash", "Jadefire Stomp"
    ],
    
    "offensive_cooldowns": [
        "The Hunt", "Fury of Elune", "Dark Ascension", "Combustion", 
        "Incarnation: Chosen of Elune", "Touch of Death", "Metamorphosis",
        "Power Infusion", "Shifting Power", "Void Torrent"
    ],
    
    "defensive_cooldowns": [
        "Demon Spikes", "Blazing Barrier", "Fiery Brand", "Barkskin",
        "Desperate Prayer", "Vampiric Embrace", "Fortifying Brew", "Darkness",
        "Dispersion", "Mass Barrier"
    ],
    
    "healing_cooldowns": [
        "Sheilun's Gift", "Life Cocoon", "Revival", "Soothing Mist",
        "Mana Tea"
    ],
    
    "kicks_and_interrupts": [
        "Disrupt", "Spear Hand Strike", "Counterspell", "Solar Beam"
    ],
    
    "crowd_control": [
        "Imprison", "Paralysis", "Polymorph", "Ring of Peace", "Psychic Scream",
        "Incapacitating Roar", "Mind Soothe", "Sigil of Misery", "Chaos Nova",
        "Leg Sweep"
    ],
    
    "dispels": [
        "Detox", "Remove Curse", "Mass Dispel", "Remove Corruption", "Soothe"
    ],
    
    "consumables": [
        "Tempered Potion", "Algari Healing Potion", "Flask of Alchemical Chaos"
    ],
    
    "trinkets": [
        "House of Cards", "Chromebustible Bomb Suit", "Hyperthread Wristwraps",
        "Bursting Lightshard", "Stylish Black Parasol", "Stormrooks Favor"
    ],
    
    "utility": [
        "Power Word: Shield", "Thunder Focus Tea", "Fade", "Mirror Image",
        "Torment", "Sigil of Flame", "Sigil of Spite", "Sigil of Silence",
        "Sigil of Chains", "Power Word: Fortitude", "Shadow Word: Pain",
        "Arcane Intellect", "Mark of the Wild", "Time Warp"
    ],
    
    "movement": [
        "Roll", "Wild Charge", "Glide", "Vengeful Retreat", "Tiger's Lust",
        "Angelic Feather", "Shimmer", 
        "Transcendence", "Transcendence: Transfer", "Alter Time", "Prowl"
    ],
    
    "forms_and_stances": [
        "Moonkin Form", "Bear Form", "Cat Form", "Travel Form"
    ]
}

ABILITY_TO_CATEGORY = {
    ability: category
    for category, abilities in ABILITY_CATEGORIES.items()
    for ability in abilities
}