"""Compatibility entrypoint for Appwrite deployments configured as main.py."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_handler_path = Path(__file__).with_name("handler.py")
_handler_spec = spec_from_file_location("market_api_handler", _handler_path)
if _handler_spec is None or _handler_spec.loader is None:
    raise RuntimeError(f"Unable to load Appwrite handler at {_handler_path}")

_handler_module = module_from_spec(_handler_spec)
_handler_spec.loader.exec_module(_handler_module)
main = _handler_module.main

__all__ = ["main"]
