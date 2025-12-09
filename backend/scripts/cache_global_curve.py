"""Pre-compute and cache global curve for faster service initialization.

Run once:
    cd backend
    source venv/bin/activate
    python scripts/cache_global_curve.py
"""

from pathlib import Path
import json
import sys

# Add predictor to path
project_root = Path(__file__).resolve().parents[2]
predictor_path = project_root / "data_analysis" / "predictor"
sys.path.insert(0, str(predictor_path))

from predictor import build_global_curve


def main():
    processed_root = project_root / "data_analysis" / "data" / "processed"
    output_path = predictor_path / "global_curve.json"

    if not processed_root.exists():
        print(f"ERROR: Processed data not found at {processed_root}")
        print("Please run the preprocessing pipeline first:")
        print("  cd data_analysis")
        print("  python preprocessing/convert_to_si.py")
        sys.exit(1)

    print(f"Building global curve from {processed_root}...")
    print("This may take 30-60 seconds...")

    curve = build_global_curve(processed_root)

    # Convert to JSON-serializable format
    curve_dict = {
        'grade': curve['grade'].tolist(),
        'median': curve['median'].tolist(),
        'p25': curve['p25'].tolist() if 'p25' in curve.columns else [],
        'p75': curve['p75'].tolist() if 'p75' in curve.columns else [],
        'count': curve['count'].tolist() if 'count' in curve.columns else []
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(curve_dict, f, indent=2)

    print(f"✓ Saved global curve to {output_path}")
    print(f"✓ Server startup will now be ~30s faster!")


if __name__ == "__main__":
    main()
