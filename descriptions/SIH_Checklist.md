# SIH Codebase — Line-by-Line Explanation Progress

Check a file only after its complete line-by-line explanation has been reviewed.

## Core simulation and schedulers

- [x]  `scan_scheduler_prototype.py`
- [x]  `scan_scheduler_v2.py`
- [x]  `scan_scheduler_v3_pri.py`
- [x]  `scan_scheduler_v4_persistent.py`
- [x]  `scan_scheduler_v5_hedge.py`
- [x]  `spatial_scan_emitter.py`
- [x]  `scan_aware_scheduler.py`

## Whittle-index implementation

- [x]  `whittle_index.py`
- [x]  `whittle_index_optimized_v2.py`
- [ ]  `scan_scheduler_whittle.py`
- [ ]  `scan_scheduler_whittle_scalar.py`
- [ ]  `whittle_equiv_test.py`
- [ ]  `scan_scheduler_whittle_equiv_test.py`

## PDW and data pipeline

- [ ]  `pdw_loader.py`
- [ ]  `pdw_source.py`
- [ ]  `pdw_environment.py`
- [ ]  `prediction_accuracy_metrics.py`
- [ ]  `deinterleave_hdbscan.py`

## Noise and demonstrations

- [ ]  `noise_model.py`
- [ ]  `noise_model_demo.py`
- [ ]  `demo_spatial_scan_emitter.py`

## Main experiment runners

- [ ]  `run_all.py`
- [ ]  `run_on_turing_dataset.py`
- [ ]  `run_real_data.py`
- [ ]  `oracle_ceiling.py`

## Robustness and diagnostics

- [ ]  `multi_seed_robustness.py`
- [ ]  `diagnose_pri_lockon.py`
- [ ]  `diagnose_beacon_regression.py`
- [ ]  `diagnose_fullfile_regression.py`
- [ ]  `settle_fix_interaction.py`

## Validation scripts

- [ ]  `validate_offbyone_fix.py`
- [ ]  `validate_plateau_fix.py`
- [ ]  `validate_pdw_multiseed.py`
- [ ]  `validate_warmup_dwell_fix.py`
- [ ]  `validate_beacon_switchcost_dwell.py`
- [ ]  `validate_scan_aware_mixed.py`
- [ ]  `validate_hedge_blend.py`
- [ ]  `sanity_check_hedge.py`
- [ ]  `multiseed_alpha_default.py`
- [ ]  `multiseed_beacon_v5.py`

## Parameter sweeps

- [ ]  `sweep_class_balance_alpha.py`
- [ ]  `sweep_eta.py`
- [ ]  `switch_cost_comparison.py`
- [ ]  `tune_confidence_threshold.py`