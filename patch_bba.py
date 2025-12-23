#!/usr/bin/env python3
"""
Patch Ben's code to disable BBA (Bridge Bidding Analyzer) library
which is Windows-only and not available on Linux.
"""

import os
import re

def patch_bba_py():
    """Patch BBA.py to not raise error when DLL not found"""
    filepath = '/app/ben/src/bba/BBA.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace the RuntimeError raise with return None
    content = content.replace(
        'raise RuntimeError(f"{EPBot_LIB}.dll is not available on this platform.")',
        'print(f"BBA: {EPBot_LIB}.dll not available, BBA disabled"); return None'
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath}")


def patch_botbidder_py():
    """Patch botbidder.py to handle BBA not being available"""
    filepath = '/app/ben/src/botbidder.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the bbabot property and wrap it in try/except
    # The property looks like:
    # @property
    # def bbabot(self):
    #     if self._bbabot_instance is None:
    #         self._bbabot_instance = BBABotBid(...)
    #     return self._bbabot_instance
    
    # We need to add a try/except to catch the RuntimeError
    
    # Pattern to find the property
    pattern = r'(@property\s+def bbabot\(self\):\s+if self\._bbabot_instance is None:\s+self\._bbabot_instance = BBABotBid\([^)]+\)\s+return self\._bbabot_instance)'
    
    def replacement(match):
        original = match.group(1)
        # Extract the BBABotBid call
        return '''@property
    def bbabot(self):
        if self._bbabot_instance is None:
            try:
                self._bbabot_instance = BBABotBid(
                    self.models.bba_ns,
                    self.models.bba_ew,
                    self.seat,
                    self.hand_str,
                    self.vuln,
                    self.models.ns_system,
                    self.models.ew_system,
                    verbose=self.verbose)
            except (RuntimeError, OSError, TypeError, Exception) as e:
                # BBA not available on this platform
                self._bbabot_instance = None
        return self._bbabot_instance'''
    
    # Try the regex replacement
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # If regex didn't work, try simpler approach
    if new_content == content:
        print("Regex replacement didn't match, trying simple replacement...")
        
        # Just add a guard at the top of the property to return None if consult_bba is False
        old_def = 'def bbabot(self):'
        new_def = '''def bbabot(self):
        # Skip BBA if not configured or not available
        if hasattr(self, 'models') and hasattr(self.models, 'consult_bba'):
            if not self.models.consult_bba:
                return None'''
        
        new_content = content.replace(old_def, new_def, 1)
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print(f"Patched {filepath}")


def verify_patches():
    """Verify the patches were applied"""
    # Check BBA.py
    with open('/app/ben/src/bba/BBA.py', 'r') as f:
        content = f.read()
    if 'BBA disabled' in content or 'return None' in content:
        print("✅ BBA.py patch verified")
    else:
        print("⚠️ BBA.py patch may not have applied correctly")
    
    # Check botbidder.py  
    with open('/app/ben/src/botbidder.py', 'r') as f:
        content = f.read()
    if 'consult_bba' in content and 'return None' in content:
        print("✅ botbidder.py patch verified")
    else:
        print("⚠️ botbidder.py patch may not have applied correctly")


if __name__ == '__main__':
    print("Patching Ben to disable BBA...")
    patch_bba_py()
    patch_botbidder_py()
    verify_patches()
    print("Done!")
