"""
Operators for LoL League Tools V2
"""

# Import modules with error handling
_import_errors = {}

try:
    from . import import_skl_skn
except ImportError as e:
    _import_errors['import_skl_skn'] = str(e)
    import_skl_skn = None

try:
    from . import export_skl_skn
except ImportError as e:
    _import_errors['export_skl_skn'] = str(e)
    export_skl_skn = None

try:
    from . import import_anm
except ImportError as e:
    _import_errors['import_anm'] = str(e)
    import_anm = None

try:
    from . import export_anm
except ImportError as e:
    _import_errors['export_anm'] = str(e)
    export_anm = None

try:
    from . import uv_corners
except ImportError as e:
    _import_errors['uv_corners'] = str(e)
    uv_corners = None

try:
    from . import import_scb
except ImportError as e:
    _import_errors['import_scb'] = str(e)
    import_scb = None

try:
    from . import export_scb
except ImportError as e:
    _import_errors['export_scb'] = str(e)
    export_scb = None

try:
    from . import import_sco
except ImportError as e:
    _import_errors['import_sco'] = str(e)
    import_sco = None

try:
    from . import export_sco
except ImportError as e:
    _import_errors['export_sco'] = str(e)
    export_sco = None

try:
    from . import limit_influences
except ImportError as e:
    _import_errors['limit_influences'] = str(e)
    limit_influences = None

# Print any import errors for debugging
if _import_errors:
    print("[lol_league_v4.operators] Import errors:")
    for module_name, error in _import_errors.items():
        print(f"  - {module_name}: {error}")

__all__ = ['import_skl_skn', 'export_skl_skn', 'import_anm', 'export_anm', 'uv_corners', 'import_scb', 'export_scb', 'import_sco', 'export_sco', 'limit_influences']

