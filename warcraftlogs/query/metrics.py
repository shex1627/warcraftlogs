from enum import Enum, auto

class Role(str, Enum):
    TANK = "tanks"
    HEALER = "healers"
    DPS = "dps"

class DataType(str, Enum):
    DAMAGE = "DamageDone"
    HEALING = "Healing"

class MetricType(str, Enum):
    DPS = "dps"
    HPS = "hps"

def get_primary_metric_for_role(role: str) -> MetricType:
    role = Role(role)
    if role == Role.TANK:
        return MetricType.DPS
    elif role == Role.HEALER:
        return MetricType.HPS
    else:
        return MetricType.DPS
    
def get_data_type_for_role(role: str) -> DataType:
    role = Role(role)
    if role == Role.TANK:
        return DataType.DAMAGE
    elif role == Role.HEALER:
        return DataType.HEALING
    else:
        return DataType.DAMAGE

