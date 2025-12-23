#!/usr/bin/env python3
"""
Patch Ben's code to disable BBA (Bridge Bidding Analyzer) library
which is Windows-only and not available on Linux.
"""

import os
import re

def create_noop_bba():
    """Create a NoOp BBA module that provides dummy implementations"""
    noop_code = '''
# NoOp BBA - provides dummy implementations when BBA library is not available

class NoOpBBA:
    """A no-op BBA that returns empty/neutral values for all methods"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def bid_hand(self, auction):
        """Return None - no BBA bid available"""
        return None
    
    def explain(self, auction):
        """Return empty explanations"""
        return [], False, False
    
    def get_bid(self, *args, **kwargs):
        return None
    
    def __getattr__(self, name):
        """Return a no-op function for any undefined method"""
        def noop(*args, **kwargs):
            return None
        return noop

# Singleton instance
_noop_instance = None

def get_noop_bba():
    global _noop_instance
    if _noop_instance is None:
        _noop_instance = NoOpBBA()
    return _noop_instance
'''
    
    filepath = '/app/ben/src/bba/noop_bba.py'
    with open(filepath, 'w') as f:
        f.write(noop_code)
    
    print(f"Created {filepath}")


def patch_bba_py():
    """Patch BBA.py to return NoOpBBA instead of raising error"""
    filepath = '/app/ben/src/bba/BBA.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add import for NoOpBBA at the top
    if 'from bba.noop_bba import' not in content:
        # Find the imports section and add our import
        content = 'from bba.noop_bba import get_noop_bba, NoOpBBA\n' + content
    
    # Replace the RuntimeError raise with return NoOpBBA
    content = content.replace(
        'raise RuntimeError(f"{EPBot_LIB}.dll is not available on this platform.")',
        'print(f"BBA: {EPBot_LIB}.dll not available, using NoOpBBA"); return NoOpBBA'
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath}")


def patch_botbidder_py():
    """Patch botbidder.py to handle BBA not being available"""
    filepath = '/app/ben/src/botbidder.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add import for NoOpBBA
    if 'from bba.noop_bba import' not in content:
        # Add import after existing imports
        import_line = 'from bba.noop_bba import get_noop_bba, NoOpBBA\n'
        # Find a good place to insert - after other bba imports
        if 'from bba.' in content:
            content = content.replace('from bba.', import_line + 'from bba.', 1)
        else:
            # Just add at the top after other imports
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    continue
                else:
                    lines.insert(i, import_line)
                    break
            content = '\n'.join(lines)
    
    # 1. Add a guard at the top of the bbabot property to return NoOpBBA if consult_bba is False
    old_def = 'def bbabot(self):'
    new_def = '''def bbabot(self):
        # Skip BBA if not configured or not available - return NoOpBBA
        if hasattr(self, 'models') and hasattr(self.models, 'consult_bba'):
            if not self.models.consult_bba:
                return get_noop_bba()'''
    
    content = content.replace(old_def, new_def, 1)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath}")


def patch_config():
    """Ensure consult_bba is False in the Models class default"""
    filepath = '/app/ben/src/nn/models.py'
    
    if not os.path.exists(filepath):
        print(f"Skipping {filepath} - file not found")
        return
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Set consult_bba default to False
    content = content.replace('consult_bba = True', 'consult_bba = False')
    content = content.replace('consult_bba=True', 'consult_bba=False')
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath}")


def verify_patches():
    """Verify the patches were applied"""
    # Check noop_bba.py exists
    if os.path.exists('/app/ben/src/bba/noop_bba.py'):
        print("✅ noop_bba.py created")
    else:
        print("⚠️ noop_bba.py not found")
    
    # Check BBA.py
    with open('/app/ben/src/bba/BBA.py', 'r') as f:
        content = f.read()
    if 'NoOpBBA' in content:
        print("✅ BBA.py patch verified")
    else:
        print("⚠️ BBA.py patch may not have applied correctly")
    
    # Check botbidder.py  
    with open('/app/ben/src/botbidder.py', 'r') as f:
        content = f.read()
    if 'get_noop_bba' in content or 'consult_bba' in content:
        print("✅ botbidder.py patch verified")
    else:
        print("⚠️ botbidder.py patch may not have applied correctly")


if __name__ == '__main__':
    print("Patching Ben to disable BBA...")
    create_noop_bba()
    patch_bba_py()
    patch_botbidder_py()
    patch_config()
    verify_patches()
    print("Done!")
