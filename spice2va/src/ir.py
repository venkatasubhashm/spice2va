from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Node:
    name: str

@dataclass
class Component:
    name: str
    type: str  # e.g., 'R', 'C', 'L', 'V', 'I'
    nodes: List[str]
    value_str: str
    value: Optional[float] = None
    ac_amplitude: Optional[float] = None
    model_name: Optional[str] = None

@dataclass
class SpiceModel:
    name: str
    model_type: str
    params: Dict[str, float]

@dataclass
class Directive:
    type: str # e.g., 'ac', 'tran'
    params: List[str]

@dataclass
class Circuit:
    title: str = "Untitled Circuit"
    components: List[Component] = field(default_factory=list)
    directives: List[Directive] = field(default_factory=list)
    models: List[SpiceModel] = field(default_factory=list)

    def get_components_by_type(self, comp_type: str) -> List[Component]:
        return [c for c in self.components if c.type.upper() == comp_type.upper()]
