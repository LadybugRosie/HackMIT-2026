"""
Simple scoring engine that works with composition dictionaries
"""
from typing import Dict


class ScoringEngine:
    def __init__(self, strict: bool = False):
        self.strict = strict
    
    def calculate_scores(self, composition: Dict[str, float]) -> Dict[str, int]:
        """Calculate trust and composition scores from content mix"""
        typed_ratio = composition.get('typed', 0)
        internal_ratio = composition.get('internal', 0) 
        external_ratio = composition.get('external', 0)
        
        # Trust score: penalize external content
        # 0% external -> 100 trust
        # 10% external -> 90 trust
        # 20% external -> 80 trust
        # 40%+ external -> 60 trust (capped)
        penalty = min(40, round(100 * external_ratio))
        trust_score = 100 - penalty
        
        # In strict mode, also penalize low typed content
        if self.strict and typed_ratio < 0.7:
            additional_penalty = round((0.7 - typed_ratio) * 30)
            trust_score = max(0, trust_score - additional_penalty)
        
        # Composition score: rewards typed content
        composition_score = round(typed_ratio * 100)
        
        return {
            'trust': trust_score,
            'composition': composition_score
        }

