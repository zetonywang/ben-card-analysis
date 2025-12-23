#!/usr/bin/env python3
"""
Patch Ben's code to disable BBA (Bridge Bidding Analyzer) library
which is Windows-only and not available on Linux.
"""

import os

def create_noop_bba():
    """Create a NoOp BBA module that provides dummy implementations"""
    noop_code = '''# NoOp BBA - provides dummy implementations when BBA library is not available

class NoOpBBA:
    """A no-op BBA that returns empty/neutral values for all methods"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def bid_hand(self, *args, **kwargs):
        """Return None - no BBA bid available"""
        return None
    
    def explain(self, *args, **kwargs):
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

def get_noop_bba(*args, **kwargs):
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
    
    # Add import for NoOpBBA at the very top
    if 'from bba.noop_bba import' not in content:
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
        lines = f.readlines()
    
    new_lines = []
    i = 0
    
    # Add import at the top (after other imports)
    import_added = False
    
    while i < len(lines):
        line = lines[i]
        
        # Add our import after the last 'from' or 'import' line at the top
        if not import_added and line.strip() and not line.startswith('import ') and not line.startswith('from ') and not line.startswith('#'):
            new_lines.append('from bba.noop_bba import get_noop_bba\n')
            import_added = True
        
        # Find the bbabot property and add guard
        if line.strip() == 'def bbabot(self):':
            new_lines.append(line)
            i += 1
            # Add our guard right after the def line
            # Find the indentation of the next line
            if i < len(lines):
                next_line = lines[i]
                # Get the indentation
                indent = len(next_line) - len(next_line.lstrip())
                indent_str = ' ' * indent
                # Add our guard code with proper indentation
                new_lines.append(f'{indent_str}# Return NoOpBBA if BBA is not available\n')
                new_lines.append(f'{indent_str}if hasattr(self, "models") and hasattr(self.models, "consult_bba"):\n')
                new_lines.append(f'{indent_str}    if not self.models.consult_bba:\n')
                new_lines.append(f'{indent_str}        return get_noop_bba()\n')
            continue
        
        new_lines.append(line)
        i += 1
    
    with open(filepath, 'w') as f:
        f.writelines(new_lines)
    
    print(f"Patched {filepath}")


def patch_config():
    """Ensure consult_bba is False in config"""
    filepath = '/app/ben/src/config/default.conf'
    
    if not os.path.exists(filepath):
        print(f"Skipping {filepath} - file not found")
        return
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Set consult_bba default to False
    content = content.replace('consult_bba = True', 'consult_bba = False')
    content = content.replace('consult_bba=True', 'consult_bba=False')
    
    # Also add it explicitly at the end
    if 'consult_bba' not in content:
        content += '\nconsult_bba = False\n'
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath}")


def verify_patches():
    """Verify the patches were applied"""
    errors = []
    
    # Check noop_bba.py exists
    if os.path.exists('/app/ben/src/bba/noop_bba.py'):
        print("✅ noop_bba.py created")
    else:
        errors.append("noop_bba.py not found")
    
    # Check BBA.py
    with open('/app/ben/src/bba/BBA.py', 'r') as f:
        content = f.read()
    if 'NoOpBBA' in content:
        print("✅ BBA.py patch verified")
    else:
        errors.append("BBA.py patch failed")
    
    # Check botbidder.py - verify no syntax errors
    try:
        with open('/app/ben/src/botbidder.py', 'r') as f:
            content = f.read()
        compile(content, 'botbidder.py', 'exec')
        print("✅ botbidder.py syntax OK")
    except SyntaxError as e:
        errors.append(f"botbidder.py syntax error: {e}")
    
    if errors:
        print("❌ Errors:", errors)
        return False
    return True


if __name__ == '__main__':
    print("Patching Ben to disable BBA...")
    create_noop_bba()
    patch_bba_py()
    patch_botbidder_py()
    patch_config()
    if verify_patches():
        print("✅ All patches applied successfully!")
    else:
        print("❌ Some patches failed!")
    print("Done!")

