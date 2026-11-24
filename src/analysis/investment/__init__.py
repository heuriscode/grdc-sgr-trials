"""Investment (benefit-cost) analysis of trial systems for a cropping farmer.

Plugs into the pipeline after the crop-sequence gross margin step. See README.md.
"""

from .run import RunOptions, run_investment_analysis

__all__ = ["RunOptions", "run_investment_analysis"]
