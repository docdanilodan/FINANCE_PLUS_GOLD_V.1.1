"""FinancePlus Centrale Rischi engine - MASTER integrated edition."""
from .parser import parse_file, parse_text
from .engine import analyze
__all__ = ["parse_file", "parse_text", "analyze"]
