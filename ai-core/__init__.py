"""
UX-Ghost ZeroBaran — __init__ for ai-core package
"""
from .ux_analyzer import UXBrain, PageAggregates, analyze_and_save
from . import prompt_templates

__all__ = ["UXBrain", "PageAggregates", "analyze_and_save", "prompt_templates"]
__version__ = "1.0.0"
__author__  = "Baran Avisat <Baranavisat@gmail.com>"
