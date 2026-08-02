"""Compatibility entrypoint for deployments configured as handler.py."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_source = Path(__file__).parent / "src" / "main.py"
_spec = spec_from_file_location("market_api_src_handler", _source)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Unable to load Appwrite handler at {_source}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)
main = _module.main

__all__ = ["main"]
