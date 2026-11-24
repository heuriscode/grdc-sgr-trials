"""Investment (benefit-cost) analysis of trial systems for a cropping farmer.

Plugs into the pipeline after the crop-sequence gross margin step. See README.md.
"""

from .run import (RunOptions, adoption_sensitivity_table, convention_variant_table, run_comparisons,
                  run_convention_comparison, run_investment_analysis)

__all__ = ["RunOptions", "run_investment_analysis", "run_comparisons", "adoption_sensitivity_table",
           "convention_variant_table", "run_convention_comparison"]
