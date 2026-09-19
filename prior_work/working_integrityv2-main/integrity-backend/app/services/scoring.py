from typing import List, Tuple
from ..models import IntegrityScores, ContentMix, ExternalSpan


class ScoringEngine:
    @staticmethod
    def calculate_trust_score(typed: int, internal: int, external: int) -> int:
        """
        Trust = (typed + internal) / total * 100
        100% external → 0 trust.  0% external → 100 trust.
        """
        total = max(typed + internal + external, 1)
        trusted_chars = typed + internal
        trust = round(100 * trusted_chars / total)
        return max(0, min(100, trust))
    
    @staticmethod
    def calculate_composition_score(typed: int, internal: int, external: int) -> int:
        """
        Calculate composition score (for now, mirrors trust)
        Can be enhanced later with typing pattern analysis
        """
        return ScoringEngine.calculate_trust_score(typed, internal, external)
    
    @staticmethod
    def calculate_mix(typed: int, internal: int, external: int) -> ContentMix:
        """Calculate content mix ratios"""
        total = max(typed + internal + external, 1)
        
        return ContentMix(
            typed=round(typed / total, 3),
            internal=round(internal / total, 3),
            external=round(external / total, 3)
        )
    
    @staticmethod
    def generate_flags(events: List, typed: int, internal: int, external: int, 
                      recent_pastes: List[Tuple[int, float]]) -> List[str]:
        """Generate warning flags based on events and composition"""
        flags = []
        
        # Flag large pastes in the last batch
        for length, ts in recent_pastes:
            if length >= 500:
                # Convert timestamp to readable time
                import time
                time_str = time.strftime('%H:%M', time.localtime(ts))
                flags.append(f"Large insert {length} chars at {time_str}")
        
        # Flag high external content ratio
        total = max(typed + internal + external, 1)
        external_ratio = external / total
        
        if external_ratio > 0.3:
            flags.append(f"High external content: {round(external_ratio * 100)}%")
        elif external_ratio > 0.2:
            flags.append(f"Moderate external content: {round(external_ratio * 100)}%")
        
        # Flag if mostly copy-paste even if internal
        if internal > typed * 2 and typed < total * 0.2:
            flags.append("Heavy internal copy-paste detected")
        
        return flags
    
    @staticmethod
    def format_external_spans(spans: List[Tuple[int, int]]) -> List[ExternalSpan]:
        """Format external spans for response"""
        return [
            ExternalSpan(start=start, end=end) 
            for start, end in spans
        ]
    
    @staticmethod
    def compute_scores(typed: int, internal: int, external: int, 
                      events: List, recent_pastes: List[Tuple[int, float]], 
                      ext_spans: List[Tuple[int, int]]) -> dict:
        """Compute all scoring metrics"""
        trust = ScoringEngine.calculate_trust_score(typed, internal, external)
        composition = ScoringEngine.calculate_composition_score(typed, internal, external)
        mix = ScoringEngine.calculate_mix(typed, internal, external)
        flags = ScoringEngine.generate_flags(events, typed, internal, external, recent_pastes)
        formatted_spans = ScoringEngine.format_external_spans(ext_spans)
        
        return {
            "scores": IntegrityScores(trust=trust, composition=composition),
            "mix": mix,
            "flags": flags,
            "ext_spans": formatted_spans
        }

