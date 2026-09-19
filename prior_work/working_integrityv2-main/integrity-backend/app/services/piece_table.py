from typing import List, Optional, Tuple
from ..models import Piece, Event
import time


class PieceTableManager:
    def __init__(self, pieces: List[Piece] = None):
        self.pieces: List[Piece] = pieces or []
        self.text_len = sum(p.end - p.start for p in self.pieces) if pieces else 0
        self.last_copy_source: Optional[Tuple[int, int, List[Piece]]] = None
    
    def _find_piece_at_position(self, pos: int) -> Tuple[Optional[Piece], int]:
        """Find piece containing position and its index"""
        for i, piece in enumerate(self.pieces):
            if piece.start <= pos < piece.end:
                return piece, i
            if pos < piece.start:
                return None, i
        return None, len(self.pieces)
    
    def _split_piece(self, piece: Piece, at: int) -> Tuple[Piece, Piece]:
        """Split a piece at position (relative to piece start)"""
        abs_pos = piece.start + at
        left = Piece(
            start=piece.start,
            end=abs_pos,
            origin=piece.origin,
            source_id=piece.source_id,
            ts_created=piece.ts_created
        )
        right = Piece(
            start=abs_pos,
            end=piece.end,
            origin=piece.origin,
            source_id=piece.source_id,
            ts_created=piece.ts_created
        )
        return left, right
    
    def _merge_adjacent_pieces(self):
        """Merge adjacent pieces with same origin and source_id"""
        if len(self.pieces) < 2:
            return
        
        merged = []
        current = self.pieces[0]
        
        for piece in self.pieces[1:]:
            if (current.end == piece.start and 
                current.origin == piece.origin and 
                current.source_id == piece.source_id):
                # Merge
                current = Piece(
                    start=current.start,
                    end=piece.end,
                    origin=current.origin,
                    source_id=current.source_id,
                    ts_created=current.ts_created
                )
            else:
                merged.append(current)
                current = piece
        
        merged.append(current)
        self.pieces = merged
    
    def insert_typed(self, pos: int, length: int, ts: float) -> None:
        """Insert typed characters at position"""
        if length <= 0:
            return
        
        piece, idx = self._find_piece_at_position(pos)
        
        new_piece = Piece(
            start=pos,
            end=pos + length,
            origin="T",
            source_id=None,
            ts_created=ts
        )
        
        if piece and piece.start < pos < piece.end:
            # Split existing piece
            left, right = self._split_piece(piece, pos - piece.start)
            right.start = pos + length
            right.end += length
            self.pieces[idx:idx+1] = [left, new_piece, right]
        else:
            # Insert between pieces
            self.pieces.insert(idx, new_piece)
        
        # Shift all subsequent pieces
        for i in range(idx + 1 if not piece else idx + 2, len(self.pieces)):
            self.pieces[i].start += length
            self.pieces[i].end += length
        
        self.text_len += length
        self._merge_adjacent_pieces()
    
    def insert_paste(self, pos: int, length: int, origin: str, source_id: str, ts: float) -> None:
        """Insert pasted content at position"""
        if length <= 0:
            return
        
        piece, idx = self._find_piece_at_position(pos)
        
        new_piece = Piece(
            start=pos,
            end=pos + length,
            origin=origin,
            source_id=source_id,
            ts_created=ts
        )
        
        if piece and piece.start < pos < piece.end:
            # Split existing piece
            left, right = self._split_piece(piece, pos - piece.start)
            right.start = pos + length
            right.end += length
            self.pieces[idx:idx+1] = [left, new_piece, right]
        else:
            # Insert between pieces
            self.pieces.insert(idx, new_piece)
        
        # Shift all subsequent pieces
        for i in range(idx + 1 if not piece else idx + 2, len(self.pieces)):
            self.pieces[i].start += length
            self.pieces[i].end += length
        
        self.text_len += length
        self._merge_adjacent_pieces()
    
    def delete_range(self, start: int, end: int) -> None:
        """Delete content in range [start, end)"""
        if start >= end:
            return
        
        length = end - start
        new_pieces = []
        
        for piece in self.pieces:
            if piece.end <= start:
                # Before deletion
                new_pieces.append(piece)
            elif piece.start >= end:
                # After deletion - shift left
                piece.start -= length
                piece.end -= length
                new_pieces.append(piece)
            elif piece.start < start and piece.end > end:
                # Piece spans deletion - split
                left = Piece(
                    start=piece.start,
                    end=start,
                    origin=piece.origin,
                    source_id=piece.source_id,
                    ts_created=piece.ts_created
                )
                right = Piece(
                    start=start,
                    end=piece.end - length,
                    origin=piece.origin,
                    source_id=piece.source_id,
                    ts_created=piece.ts_created
                )
                new_pieces.extend([left, right])
            elif piece.start >= start and piece.end <= end:
                # Piece entirely within deletion - remove
                pass
            elif piece.start < start:
                # Piece partially before deletion
                piece.end = start
                new_pieces.append(piece)
            else:
                # Piece partially after deletion
                piece.start = start
                piece.end -= length
                new_pieces.append(piece)
        
        self.pieces = new_pieces
        self.text_len -= length
        self._merge_adjacent_pieces()
    
    def replace_range(self, start: int, end: int, length: int, ts: float) -> None:
        """Replace range with typed content"""
        self.delete_range(start, end)
        self.insert_typed(start, length, ts)
    
    def record_copy(self, start: int, end: int) -> None:
        """Record a copy operation for later paste classification"""
        # Extract pieces in the copied range
        copied_pieces = []
        for piece in self.pieces:
            if piece.start < end and piece.end > start:
                # Piece overlaps with copy range
                copy_start = max(piece.start, start)
                copy_end = min(piece.end, end)
                copied_pieces.append(Piece(
                    start=copy_start - start,  # Relative to copy start
                    end=copy_end - start,
                    origin=piece.origin,
                    source_id=piece.source_id,
                    ts_created=piece.ts_created
                ))
        self.last_copy_source = (start, end, copied_pieces)
    
    def is_last_copy_internal(self) -> bool:
        """Check if last copy was from typed/internal content"""
        if not self.last_copy_source:
            return False
        _, _, pieces = self.last_copy_source
        return all(p.origin in ("T", "INT") for p in pieces)
    
    def get_composition(self) -> Tuple[int, int, int]:
        """Get character counts by origin (typed, internal, external)"""
        typed = 0
        internal = 0
        external = 0
        
        for piece in self.pieces:
            length = piece.end - piece.start
            if piece.origin == "T":
                typed += length
            elif piece.origin == "INT":
                internal += length
            else:  # EXT
                external += length
        
        return typed, internal, external
    
    def get_external_spans(self) -> List[Tuple[int, int]]:
        """Get ranges of external content"""
        spans = []
        for piece in self.pieces:
            if piece.origin == "EXT":
                spans.append((piece.start, piece.end))
        return spans
    
    def handle_backspace(self, pos: int, ts: float) -> None:
        """Handle backspace at position"""
        if pos > 0:
            self.delete_range(pos - 1, pos)
    
    def handle_delete(self, pos: int, ts: float) -> None:
        """Handle delete key at position"""
        if pos < self.text_len:
            self.delete_range(pos, pos + 1)

