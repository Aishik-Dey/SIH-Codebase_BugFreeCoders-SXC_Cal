import argparse
import subprocess
import sys
import time
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

# Real TSRD .h5 file to validate the PDW-capable scripts against,
# resolved relative to THIS file's directory (so it doesn't depend on
# the directory the runner is launched from). Set to None to run
# everything against the synthetic stand-in only.
H5_PATH = "Datasets/Turing datasets/Validation/config_169.h5"

# Used only when no --h5 is given on the command line. Command-line paths
# replace it entirely (they are NOT appended), so a multi-file run never
# silently includes config_169.h5 unless you list it.

# Scripts that accept --h5, and the extra args to pass alongside it.
# Deliberately NOT extended to the controlled synthetic-regression
# suites below (diagnose_*, validate_offbyone_fix.py,
# validate_plateau_fix.py, validate_warmup_dwell_fix.py,
# validate_beacon_switchcost_dwell.py, validate_scan_aware_mixed.py,
# switch_cost_comparison.py, settle_fix_interaction.py) -- those assert
# against DECLARED synthetic ground truth (an exact beacon period, a
# known scan/burst structure) that an arbitrary real .h5 doesn't carry,
# so pointing them at one wouldn't validate them, it would just
# silently change what they measure. See pdw_source.py's module
# docstring for the full reasoning (metadata-derived truth, seed
# semantics, why a load failure here is fatal rather than a silent
# fallback).
H5_CAPABLE = {
    "run_on_turing_dataset.py": ["--dwell-us", "20"],
    "multi_seed_robustness.py": ["--seeds", "10"],
    "validate_pdw_multiseed.py": ["--seeds", "20", "--dwell-us", "20"],
    "tune_confidence_threshold.py": [],
    "prediction_accuracy_metrics.py": ["--seeds", "20", "--dwell-us", "20"],
    # These take only --h5 (no other flags); each had "config_169.h5"
    # hardcoded as a bare filename before, which only resolved if the
    # file was flattened next to the script.
    "deinterleave_hdbscan.py": [],
    "diagnose_fullfile_regression.py": [],
    "oracle_ceiling.py": [],
    "sanity_check_hedge.py": [],
    "sweep_class_balance_alpha.py": [],
    "sweep_eta.py": [],
    "validate_hedge_blend.py": [],
}

SCRIPTS = [
    "scan_scheduler_prototype.py",
    "scan_scheduler_v2.py",
    "scan_scheduler_v3_pri.py",
    "scan_scheduler_v4_persistent.py",
    "scan_aware_scheduler.py",
    "demo_spatial_scan_emitter.py",

    "diagnose_beacon_regression.py",
    "diagnose_pri_lockon.py",

    "multi_seed_robustness.py",

    "tune_confidence_threshold.py",

    "validate_offbyone_fix.py",
    "validate_plateau_fix.py",
    "validate_warmup_dwell_fix.py",
    "validate_beacon_switchcost_dwell.py",
    "validate_scan_aware_mixed.py",
    "switch_cost_comparison.py",
    "settle_fix_interaction.py",

    "validate_pdw_multiseed.py",
    "prediction_accuracy_metrics.py",

    # Hedge blend, ceiling and deinterleaving suites
    "sanity_check_hedge.py",
    "validate_hedge_blend.py",
    "sweep_eta.py",
    "sweep_class_balance_alpha.py",
    "multiseed_alpha_default.py",
    "multiseed_beacon_v5.py",
    "diagnose_fullfile_regression.py",
    "oracle_ceiling.py",
    "deinterleave_hdbscan.py",

    # Whittle index (synthetic) and noise model (synthetic)
    "whittle_index.py",
    "scan_scheduler_whittle.py",
    "noise_model_demo.py",

    "run_on_turing_dataset.py",
]


# ============================================================
# Main runner
# ============================================================

def run_script(script_name, extra_args=None, log_path=None):
    print("\n" + "=" * 80)
    label = script_name + (" " + " ".join(extra_args) if extra_args else "")
    print(f"STARTING: {label}")
    print("=" * 80)

    start_time = time.time()

    if log_path is None:
        result_code = subprocess.run(
            [sys.executable, script_name] + (extra_args or []),
            cwd=Path(__file__).parent,
        ).returncode
    else:
        # Tee: stream to the console AND keep a per-script log so each
        # file's results can be collected afterwards.
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as log:
            log.write(f"# {label}\n")
            proc = subprocess.Popen(
                [sys.executable, script_name] + (extra_args or []),
                cwd=Path(__file__).parent,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace",
            )
            for line in proc.stdout:
                sys.stdout.write(line)
                log.write(line)
            proc.wait()
            result_code = proc.returncode

    elapsed = time.time() - start_time

    print("\n" + "-" * 80)
    print(f"FINISHED: {label}")
    print(f"Exit code: {result_code}")
    print(f"Time: {elapsed:.1f} seconds")
    print("-" * 80)

    return result_code


def parse_args():
    ap = argparse.ArgumentParser(description="SIH master experiment runner")
    ap.add_argument("--h5", nargs="+", default=None, metavar="FILE",
                    help="one or more real TSRD .h5 files. Every H5-capable "
                         "script runs once per file. Replaces the H5_PATH "
                         "default. Relative paths resolve against the current "
                         "directory first, then this script's directory.")
    ap.add_argument("--only-h5", action="store_true",
                    help="run only the H5-capable scripts (skip the synthetic "
                         "suites, which do not depend on the file)")
    ap.add_argument("--scripts", default=None, metavar="A.py,B.py",
                    help="comma-separated subset of scripts to run")
    ap.add_argument("--log-dir", default="results",
                    help="per-file, per-script logs go to <log-dir>/<h5 stem>/ "
                         "(synthetic scripts go to <log-dir>/synthetic/). "
                         "Default: results. Use '' to disable logging.")
    return ap.parse_args()


def resolve_h5_paths(args, project_dir):
    raw = args.h5 if args.h5 else ([H5_PATH] if H5_PATH else [])
    resolved, missing = [], []
    for item in raw:
        p = Path(item)
        cands = [p] if p.is_absolute() else [Path.cwd() / p, project_dir / p]
        hit = next((c for c in cands if c.exists()), None)
        if hit is None:
            missing.append(item)
        else:
            resolved.append(hit.resolve())
    return resolved, missing


def main():
    args = parse_args()
    project_dir = Path(__file__).parent

    h5_files, h5_missing = resolve_h5_paths(args, project_dir)
    for item in h5_missing:
        print(f"NOTE: .h5 file not found: {item} -- every H5-capable script "
              f"for it is recorded as FAILED (a missing file is fatal by "
              f"design, not a silent fallback to synthetic data).")

    only = None
    if args.scripts:
        only = {s.strip() for s in args.scripts.split(",") if s.strip()}
    log_root = Path(args.log_dir) if args.log_dir else None
    if log_root is not None and not log_root.is_absolute():
        log_root = project_dir / log_root

    # Build the job list: (script, extra_args, file_label, log_path)
    jobs = []
    for script in SCRIPTS:
        if only is not None and script not in only:
            continue
        h5_capable = script in H5_CAPABLE
        if h5_capable and (h5_files or h5_missing):
            for f in h5_files:
                jobs.append((script, ["--h5", str(f)] + H5_CAPABLE[script], f.name,
                             log_root / f.stem / f"{Path(script).stem}.log" if log_root else None))
            for item in h5_missing:
                jobs.append((script, None, Path(item).name, "MISSING"))
        elif not args.only_h5:
            jobs.append((script, None, "synthetic",
                         log_root / "synthetic" / f"{Path(script).stem}.log" if log_root else None))

    print("=" * 80)
    print("SIH MASTER EXPERIMENT RUNNER")
    print("=" * 80)
    print(f"Project directory: {project_dir}")
    print(f"Python executable: {sys.executable}")
    print(f"Jobs to run: {len(jobs)}")
    if h5_files:
        print(f"Real TSRD files ({len(h5_files)}):")
        for f in h5_files:
            print(f"  - {f}")
        print(f"  H5-capable scripts run once per file: {', '.join(H5_CAPABLE)}")
    if args.only_h5:
        print("  --only-h5: synthetic suites skipped.")
    else:
        print("  Everything else runs against the synthetic stand-in / its own "
              "controlled synthetic scenario, unchanged.")
    if log_root is not None:
        print(f"Logs: {log_root}")

    overall_start = time.time()

    successful = []
    failed = []

    for number, (script, extra_args, label, log_path) in enumerate(jobs, start=1):
        tag = f"{script} [{label}]"

        print("\n")
        print("#" * 80)
        print(f"EXPERIMENT {number}/{len(jobs)}  ({label})")
        print("#" * 80)

        if log_path == "MISSING":
            failed.append((tag, "h5 file not found"))
            continue

        script_path = project_dir / script
        if not script_path.exists():
            print(f"SKIPPING: {script}")
            print("Reason: file not found.")
            failed.append((tag, "file not found"))
            continue

        try:
            exit_code = run_script(script, extra_args, log_path)

            if exit_code == 0:
                successful.append(tag)
            else:
                failed.append((tag, f"exit code {exit_code}"))

        except KeyboardInterrupt:
            print("\n\nRunner interrupted by user.")
            print("Stopping all remaining experiments.")
            break

        except Exception as exc:
            print(f"ERROR while running {script}: {exc}")
            failed.append((tag, str(exc)))

    total_time = time.time() - overall_start

    # ========================================================
    # Final report
    # ========================================================

    print("\n\n")
    print("=" * 80)
    print("ALL EXPERIMENTS FINISHED")
    print("=" * 80)

    print(f"Total time: {total_time / 60:.2f} minutes")

    print("\nSuccessful:")
    if successful:
        for tag in successful:
            print(f"  [OK] {tag}")
    else:
        print("  None")

    print("\nFailed / skipped:")
    if failed:
        for tag, reason in failed:
            print(f"  [FAILED] {tag}")
            print(f"           {reason}")
    else:
        print("  None")

    print("\n" + "=" * 80)
    print("RUN COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()