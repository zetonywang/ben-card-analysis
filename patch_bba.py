#!/usr/bin/env python3
"""
Patch Ben's code to disable BBA (Bridge Bidding Analyzer) library
which is Windows-only and not available on Linux.
"""

import os
import re

def create_noop_bba():
    """Create a NoOp BBA module that provides dummy implementations"""
    noop_code = '''# NoOp BBA - provides dummy implementations when BBA library is not available

class NoOpBBA:
    """A no-op BBA that returns empty/neutral values for all methods"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def bid_hand(self, *args, **kwargs):
        """Return empty dict - aceking is a dict structure"""
        return {}
    
    def explain(self, *args, **kwargs):
        """Return empty explanations"""
        return [], False, False
    
    def get_bid(self, *args, **kwargs):
        return None
    
    def get_explanations(self, *args, **kwargs):
        """Return empty dict for explanations"""
        return {}
    
    def get_info(self, *args, **kwargs):
        """Return empty dict for info"""
        return {}
    
    def items(self):
        """Support .items() calls"""
        return {}.items()
    
    def keys(self):
        """Support .keys() calls"""
        return {}.keys()
    
    def values(self):
        """Support .values() calls"""
        return {}.values()
    
    def get(self, key, default=None):
        """Support .get() calls"""
        return default
    
    def __iter__(self):
        """Support iteration"""
        return iter({})
    
    def __len__(self):
        """Support len()"""
        return 0
    
    def __bool__(self):
        """Evaluate to False"""
        return False
    
    def __getitem__(self, key):
        """Support indexing - return None or raise KeyError"""
        return None
    
    def __getattr__(self, name):
        """Return a no-op function for any undefined method"""
        def noop(*args, **kwargs):
            # Return empty dict for all methods to be safe
            return {}
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
    
    # Now do additional replacements for None handling
    content = ''.join(new_lines)
    
    # Handle patterns where .items() is called on potentially None results
    # Pattern: for k, v in something.items():
    # If something could be None, we need to protect it
    
    # Handle common BBA result patterns
    # explanations.items() where explanations might be None
    content = content.replace(
        'explanations.items()',
        '(explanations or {}).items()'
    )
    
    # Handle any .items() call on a variable that might be None from BBA
    # Common variables: explanations, bba_result, bid_info, etc.
    for var in ['explanations', 'bba_result', 'bid_info', 'result', 'info']:
        content = content.replace(
            f'{var}.items()',
            f'({var} or {{}}).items()'
        )
        content = content.replace(
            f'{var}.keys()',
            f'({var} or {{}}).keys()'
        )
        content = content.replace(
            f'{var}.values()',
            f'({var} or {{}}).values()'
        )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath}")


def patch_sample_py():
    """Patch sample.py to handle None values from BBA"""
    filepath = '/app/ben/src/sample.py'
    
    if not os.path.exists(filepath):
        print(f"Skipping {filepath} - file not found")
        return
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add a wrapper function at the top of the file that safely handles aceking
    wrapper = '''
# Patch: Ensure aceking is never None
def _safe_aceking(ak):
    """Convert None aceking to empty dict"""
    return ak if ak is not None else {}

'''
    
    # Add wrapper after imports if not already there
    if '_safe_aceking' not in content:
        # Find the end of imports
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i + 1
            elif line.strip() and not line.startswith('#') and insert_idx > 0:
                break
        
        lines.insert(insert_idx, wrapper)
        content = '\n'.join(lines)
    
    # Now replace all aceking usages with _safe_aceking(aceking)
    # But be careful not to replace the parameter definition
    
    # Replace aceking.items() with _safe_aceking(aceking).items()
    content = content.replace('aceking.items()', '_safe_aceking(aceking).items()')
    content = content.replace('aceking.keys()', '_safe_aceking(aceking).keys()')
    content = content.replace('aceking.values()', '_safe_aceking(aceking).values()')
    
    # Replace len(aceking) with len(_safe_aceking(aceking))
    content = content.replace('len(aceking)', 'len(_safe_aceking(aceking))')
    
    # Replace aceking[x] with _safe_aceking(aceking)[x] - but this is tricky
    # Let's use regex for subscript access
    content = re.sub(r'aceking\[([^\]]+)\]', r'_safe_aceking(aceking)[\1]', content)
    
    # Replace "for x in aceking" with "for x in _safe_aceking(aceking)"
    content = re.sub(r'for (\w+) in aceking:', r'for \1 in _safe_aceking(aceking):', content)
    content = re.sub(r'for (\w+), (\w+) in aceking', r'for \1, \2 in _safe_aceking(aceking)', content)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath} with _safe_aceking wrapper")


def patch_botbidder_aceking():
    """Patch botbidder.py to ensure aceking is never None"""
    filepath = '/app/ben/src/botbidder.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find where aceking is assigned and add "or {}"
    # Common patterns: aceking = something or aceking = self.bbabot.something
    # Pattern: aceking = <something> (but not aceking = {} or aceking = {something})
    # Add "or {}" at the end
    content = re.sub(
        r'(aceking\s*=\s*)([^{\n][^\n]*?)(\n)',
        r'\1(\2) or {}\3',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Patched {filepath} aceking assignments")


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
    
    # Check sample.py - verify _safe_aceking added
    try:
        with open('/app/ben/src/sample.py', 'r') as f:
            content = f.read()
        compile(content, 'sample.py', 'exec')
        if '_safe_aceking' in content:
            print("✅ sample.py patch verified (_safe_aceking wrapper added)")
        else:
            errors.append("sample.py: _safe_aceking not found")
    except SyntaxError as e:
        errors.append(f"sample.py syntax error: {e}")
    
    if errors:
        print("❌ Errors:", errors)
        return False
    return True


if __name__ == '__main__':
    print("Patching Ben to disable BBA...")
    create_noop_bba()
    patch_bba_py()
    patch_botbidder_py()
    patch_botbidder_aceking()
    patch_sample_py()
    patch_config()
    if verify_patches():
        print("✅ All patches applied successfully!")
    else:
        print("❌ Some patches failed!")
    print("Done!")

