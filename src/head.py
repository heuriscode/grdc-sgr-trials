### Head function for the main operational scripts/functions of the pipeline

# use this to run the pipeline while it remains as a codebase
# any changes to this or other scripts MUST be undertaken using an approved branch-pull-merge process


### Imports
from src.basic_data_processing.validation.validate import process_raw_formatted_data
from src.basic_data_processing.final_processing.prices_and_costs import integratePricesAndCosts
from src.analysis.gross_margin.grossmargin import getAnnualGrossMargin
from src.analysis.gross_margin.grossmargin import getCropSequenceGrossMargin
from src.analysis.gross_margin.grossmargin import getCropSequenceGrossMarginWithPrices
from src.analysis.reporting.system_baseline_comparisons import gen_system_baseline_comparison_results
from src.analysis.investment import run_comparisons, run_investment_analysis

# To do:
#from src.basic_data_processing.final_processing.remote_sense_data import integrateRemoteSenseData
#from src.basic_data_processing.final_processing.field_measures import integrateFieldMeasures

##### Data processing and validation

# to do
# pre_process_tor_data_files() - locate this in 'pre-processing'

#
process_raw_formatted_data()

##### Final processing

# integrate price series
# integrate remote sensed data, e.g. rainfal, temp, etc. (TBD)
# integrate other field measures, e.g. soil moisture (TBD)
# saves .csv files to '.../src/sgr_data/processed_data/*today_date.csv*
integratePricesAndCosts()

# to do
# integrateRemoteSenseData()
# integrateFieldMeasures()

##### Analysis (e.g. gross margins, simulations, etc.)

getCropSequenceGrossMargin()
#getAnnualGrossMargin()

# crop-sequence gross margins with editable reference prices + urea qty/cost (for workshop price updates)
# writes to '.../data/outputs/gross_margins/<date>_priced/'
getCropSequenceGrossMarginWithPrices()

# investment (benefit-cost) analysis of each system for a cropping farmer, by zone, plus the
# industry and project-level analysis. Reads the newest gross-margin output (prefers the
# '_priced' folder, which carries urea quantities). Assumptions (all cited):
# data/reference_data/investment_assumptions.yaml. Writes to data/outputs/investment/<date>/
# (git-ignored). Options: see src/analysis/investment/README.md, e.g.
#   run_investment_analysis(baseline_rule={'HART': 'Baseline (SDP N)'}, input_shock=True)
run_investment_analysis()

# comparison tables: lower (15%, 10%) and slower adoption; and the same project under the
# assumptions common in published RDC impact assessments (comparison only, not our view)
run_comparisons()

# calculate and generate comparisons of gms between systems and baselines for reporting
# NOTE: this function does not run as written (undefined variable, wrong column name,
# DataFrame.append removed in pandas 2). The investment analysis writes a replacement:
# trial_evidence_gain_vs_baseline.csv (bootstrap over years and replicates, by zone).
gen_system_baseline_comparison_results()


##### Detailed reporting (e.g. formatted reports)
# to do 2025


