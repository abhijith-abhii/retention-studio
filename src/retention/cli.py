import argparse
import json
from pathlib import Path
from .paths import ROOT

def main():
    parser = argparse.ArgumentParser(description="Retention Studio · simulation only")
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("train", help="Train, select and evaluate; never part of routine scoring")
    sub.add_parser("bootstrap", help="Prepare model and run the demonstration pipeline")
    score = sub.add_parser("score", help="Validate, score, recommend and export atomically")
    score.add_argument("--input", type=Path)
    serve = sub.add_parser("serve", help="Serve the local dashboard")
    serve.add_argument("--port",type=int,default=8765)
    sub.add_parser("report", help="Regenerate readable reports from saved metrics")
    args = parser.parse_args()
    try:
        if args.command in ["train","bootstrap"]:
            from .model import train
            ready = False
            if (ROOT/"artifacts/current.json").exists():
                version = json.loads((ROOT/"artifacts/current.json").read_text())["version"]
                ready = all(p.exists() for p in [ROOT/"artifacts"/version/"model.joblib",
                    ROOT/"data/scoring/active_customers.csv", ROOT/"data/training/holdout.csv"])
            if args.command == "train" or not ready:
                train()
            from .report import write_reports
            write_reports()
        if args.command in ["score","bootstrap"]:
            from .pipeline import run_pipeline
            print(json.dumps(run_pipeline(getattr(args,"input",None)),indent=2))
        if args.command == "report":
            from .report import write_reports
            write_reports()
        if args.command == "serve":
            from .web import create_app
            create_app().run(host="127.0.0.1",port=args.port,debug=False,threaded=True)
    except Exception as exc:
        parser.exit(1,f"Failed: {exc}\n")

if __name__ == "__main__": main()
