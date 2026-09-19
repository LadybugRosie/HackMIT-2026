"""Cryptographic event chain for tamper-evident logging"""
import hashlib
import json
import time
from typing import List, Dict, Any, Optional, Tuple


class EventChain:
    """Immutable cryptographic chain of events"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: List[Dict[str, Any]] = []
        self.created_at = time.time()
    
    def add_event(self, event: Dict[str, Any]) -> str:
        """Add an event to the chain and return its hash"""
        # Get previous hash (or genesis hash)
        prev_hash = self.events[-1]['hash'] if self.events else '0' * 64
        
        # Create event data with previous hash
        event_data = {
            **event,
            'prev_hash': prev_hash,
            'timestamp': time.time(),
            'sequence': len(self.events)
        }
        
        # Calculate hash: SHA256(JSON(event_data) + prev_hash)
        event_json = json.dumps(event_data, sort_keys=True, separators=(',', ':'))
        chain_string = event_json + prev_hash
        event_hash = hashlib.sha256(chain_string.encode('utf-8')).hexdigest()
        
        # Store event with hash
        event_data['hash'] = event_hash
        self.events.append(event_data)
        
        return event_hash
    
    def verify(self) -> Tuple[bool, Optional[str]]:
        """Verify chain integrity - returns (is_valid, error_message)"""
        if len(self.events) == 0:
            return True, None
        
        # Check genesis event
        if self.events[0]['prev_hash'] != '0' * 64:
            return False, "Genesis event has invalid prev_hash"
        
        # Verify each link in the chain
        for i in range(1, len(self.events)):
            prev_event = self.events[i - 1]
            curr_event = self.events[i]
            
            # Recalculate hash
            event_data = {k: v for k, v in curr_event.items() if k != 'hash'}
            event_json = json.dumps(event_data, sort_keys=True, separators=(',', ':'))
            chain_string = event_json + prev_event['hash']
            expected_hash = hashlib.sha256(chain_string.encode('utf-8')).hexdigest()
            
            if curr_event['hash'] != expected_hash:
                return False, f"Chain broken at event {i}: hash mismatch"
        
        return True, None
    
    def get_head_hash(self) -> Optional[str]:
        """Get the hash of the most recent event"""
        return self.events[-1]['hash'] if self.events else None
    
    def get_chain_summary(self) -> Dict[str, Any]:
        """Get summary of chain for verification"""
        return {
            'session_id': self.session_id,
            'event_count': len(self.events),
            'head_hash': self.get_head_hash(),
            'is_valid': self.verify()[0],
            'created_at': self.created_at
        }
    
    def get_recent_hashes(self, count: int = 10) -> List[str]:
        """Get the last N event hashes for display"""
        return [e['hash'] for e in self.events[-count:]]

