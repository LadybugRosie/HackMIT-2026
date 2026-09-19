from typing import Dict, List, Set, Optional
import hashlib


class ContentClassifier:
    def __init__(self, ngram_size: int = 16):
        self.ngram_size = ngram_size
        self.typed_ngrams: Dict[str, List[int]] = {}  # ngram -> positions
        self.internal_ngrams: Dict[str, List[int]] = {}  # includes INT content
    
    def _extract_ngrams(self, text: str, start_pos: int = 0) -> List[tuple[str, int]]:
        """Extract n-grams from text with positions"""
        ngrams = []
        for i in range(len(text) - self.ngram_size + 1):
            ngram = text[i:i + self.ngram_size]
            if len(ngram) == self.ngram_size:  # Ensure full ngram
                ngrams.append((ngram, start_pos + i))
        return ngrams
    
    def add_typed_content(self, text: str, start_pos: int) -> None:
        """Add typed content to ngram index"""
        for ngram, pos in self._extract_ngrams(text, start_pos):
            if ngram not in self.typed_ngrams:
                self.typed_ngrams[ngram] = []
            self.typed_ngrams[ngram].append(pos)
            
            if ngram not in self.internal_ngrams:
                self.internal_ngrams[ngram] = []
            self.internal_ngrams[ngram].append(pos)
    
    def add_internal_content(self, text: str, start_pos: int) -> None:
        """Add internal content to ngram index"""
        for ngram, pos in self._extract_ngrams(text, start_pos):
            if ngram not in self.internal_ngrams:
                self.internal_ngrams[ngram] = []
            self.internal_ngrams[ngram].append(pos)
    
    def remove_content_range(self, start: int, end: int) -> None:
        """Remove positions from ngram indices when content is deleted"""
        # Update typed ngrams
        for ngram in list(self.typed_ngrams.keys()):
            positions = self.typed_ngrams[ngram]
            new_positions = []
            for pos in positions:
                if pos < start:
                    new_positions.append(pos)
                elif pos >= end:
                    new_positions.append(pos - (end - start))
            if new_positions:
                self.typed_ngrams[ngram] = new_positions
            else:
                del self.typed_ngrams[ngram]
        
        # Update internal ngrams
        for ngram in list(self.internal_ngrams.keys()):
            positions = self.internal_ngrams[ngram]
            new_positions = []
            for pos in positions:
                if pos < start:
                    new_positions.append(pos)
                elif pos >= end:
                    new_positions.append(pos - (end - start))
            if new_positions:
                self.internal_ngrams[ngram] = new_positions
            else:
                del self.internal_ngrams[ngram]
    
    def classify_paste(self, snippet: str, is_from_copy: bool = False, 
                      copy_is_internal: bool = False) -> str:
        """
        Classify pasted content as INT (internal) or EXT (external)
        
        Returns:
            "INT" if content matches typed/internal content
            "EXT" if content is from external source
        """
        # If it's from a recent copy of typed/internal content
        if is_from_copy and copy_is_internal:
            return "INT"
        
        # If snippet is too short for ngram analysis
        if len(snippet) < self.ngram_size:
            return "EXT"
        
        # Sample evenly spaced ngrams from the snippet
        sample_count = min(8, len(snippet) // self.ngram_size)
        if sample_count == 0:
            return "EXT"
        
        step = max(1, (len(snippet) - self.ngram_size) // sample_count)
        sampled_ngrams = []
        
        for i in range(0, len(snippet) - self.ngram_size + 1, step):
            ngram = snippet[i:i + self.ngram_size]
            if len(ngram) == self.ngram_size:
                sampled_ngrams.append(ngram)
            if len(sampled_ngrams) >= sample_count:
                break
        
        # Check how many ngrams match typed/internal content
        matches = 0
        matched_positions: Set[int] = set()
        
        for ngram in sampled_ngrams:
            if ngram in self.internal_ngrams:
                matches += 1
                matched_positions.update(self.internal_ngrams[ngram])
        
        # If >= 70% of sampled ngrams match and they cluster in a reasonable window
        match_ratio = matches / len(sampled_ngrams) if sampled_ngrams else 0
        
        if match_ratio >= 0.7:
            # Check if matches cluster (within a reasonable span)
            if matched_positions:
                min_pos = min(matched_positions)
                max_pos = max(matched_positions)
                span = max_pos - min_pos
                # If matches are within a reasonable window (e.g., 2x snippet length)
                if span <= len(snippet) * 2:
                    return "INT"
        
        return "EXT"
    
    def classify_large_insert(self, text: str) -> str:
        """
        Classify a large insert (no paste event detected)
        Uses same logic as classify_paste
        """
        return self.classify_paste(text, is_from_copy=False)
    
    def rebuild_index(self, pieces: List, full_text: Optional[str] = None) -> None:
        """Rebuild ngram indices from piece table"""
        self.typed_ngrams.clear()
        self.internal_ngrams.clear()
        
        if not full_text:
            return
        
        for piece in pieces:
            text_segment = full_text[piece.start:piece.end]
            if piece.origin == "T":
                self.add_typed_content(text_segment, piece.start)
            elif piece.origin == "INT":
                self.add_internal_content(text_segment, piece.start)

