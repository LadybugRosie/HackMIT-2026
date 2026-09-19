"""
Simple content tracker that stores text with origin classification
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time


@dataclass
class ContentSegment:
    """Represents a segment of content with its origin"""
    text: str
    origin: str  # 'typed', 'internal', 'external'
    position: int
    timestamp: float
    
    
class ContentTracker:
    """Tracks all content in document with origin classification"""
    
    def __init__(self):
        # Store segments in order they appear in document
        self.segments: List[ContentSegment] = []
        # Current document text for comparison
        self.current_text = ""
        
    def insert_typed(self, text: str, position: int) -> None:
        """Add typed content at position"""
        self.current_text = (
            self.current_text[:position] + 
            text + 
            self.current_text[position:]
        )
        
        # Insert new segment
        segment = ContentSegment(
            text=text,
            origin='typed',
            position=position,
            timestamp=time.time()
        )
        self._insert_segment_at_position(segment, position)
        
    def insert_paste(self, text: str, position: int, source: str) -> None:
        """Add pasted content at position
        source: 'internal' or 'external'
        """
        self.current_text = (
            self.current_text[:position] + 
            text + 
            self.current_text[position:]
        )
        
        segment = ContentSegment(
            text=text,
            origin=source,
            position=position,
            timestamp=time.time()
        )
        self._insert_segment_at_position(segment, position)
        
    def delete_range(self, start: int, end: int) -> None:
        """Delete content from start to end position"""
        if start >= end:
            return
            
        # Remove from current text
        self.current_text = (
            self.current_text[:start] + 
            self.current_text[end:]
        )
        
        # Update segments - remove or trim affected segments
        new_segments = []
        for segment in self.segments:
            seg_end = segment.position + len(segment.text)
            
            # Segment is before deletion
            if seg_end <= start:
                new_segments.append(segment)
                
            # Segment is after deletion - shift position
            elif segment.position >= end:
                segment.position -= (end - start)
                new_segments.append(segment)
                
            # Segment overlaps with deletion
            else:
                # Calculate what part of segment remains
                if segment.position < start and seg_end > end:
                    # Deletion is inside segment - split it
                    before_text = segment.text[:start - segment.position]
                    after_text = segment.text[end - segment.position:]
                    
                    # Keep before part
                    if before_text:
                        before_seg = ContentSegment(
                            text=before_text,
                            origin=segment.origin,
                            position=segment.position,
                            timestamp=segment.timestamp
                        )
                        new_segments.append(before_seg)
                    
                    # Keep after part
                    if after_text:
                        after_seg = ContentSegment(
                            text=after_text,
                            origin=segment.origin,
                            position=start,
                            timestamp=segment.timestamp
                        )
                        new_segments.append(after_seg)
                        
                elif segment.position < start and seg_end > start:
                    # Keep part before deletion
                    kept_text = segment.text[:start - segment.position]
                    if kept_text:
                        segment.text = kept_text
                        new_segments.append(segment)
                        
                elif segment.position < end and seg_end > end:
                    # Keep part after deletion
                    kept_text = segment.text[end - segment.position:]
                    if kept_text:
                        segment.text = kept_text
                        segment.position = start
                        new_segments.append(segment)
                # else: segment is entirely within deletion range, remove it
                
        self.segments = new_segments
        
    def _insert_segment_at_position(self, segment: ContentSegment, position: int) -> None:
        """Insert segment and update positions of following segments"""
        text_len = len(segment.text)
        
        # Update positions of segments after this insertion
        for seg in self.segments:
            if seg.position >= position:
                seg.position += text_len
                
        # Add the new segment
        self.segments.append(segment)
        
        # Keep segments sorted by position
        self.segments.sort(key=lambda s: s.position)
        
    def get_composition(self) -> Dict[str, float]:
        """Calculate current document composition by origin"""
        if not self.current_text:
            return {'typed': 1.0, 'internal': 0.0, 'external': 0.0}
            
        total_len = len(self.current_text)
        typed_len = 0
        internal_len = 0
        external_len = 0
        
        for segment in self.segments:
            seg_len = len(segment.text)
            if segment.origin == 'typed':
                typed_len += seg_len
            elif segment.origin == 'internal':
                internal_len += seg_len
            elif segment.origin == 'external':
                external_len += seg_len
                
        # Normalize to proportions
        if total_len > 0:
            return {
                'typed': typed_len / total_len,
                'internal': internal_len / total_len,
                'external': external_len / total_len
            }
        else:
            return {'typed': 1.0, 'internal': 0.0, 'external': 0.0}
            
    def get_external_spans(self) -> List[Tuple[int, int]]:
        """Get position ranges of external content"""
        spans = []
        for segment in self.segments:
            if segment.origin == 'external':
                start = segment.position
                end = segment.position + len(segment.text)
                spans.append((start, end))
        return spans
        
    def clear(self) -> None:
        """Clear all tracked content"""
        self.segments = []
        self.current_text = ""
        
    def rebuild_from_text(self, text: str, origin: str = 'typed') -> None:
        """Rebuild tracker with new text (used for initialization)"""
        self.clear()
        self.current_text = text
        if text:
            self.segments = [ContentSegment(
                text=text,
                origin=origin,
                position=0,
                timestamp=time.time()
            )]

