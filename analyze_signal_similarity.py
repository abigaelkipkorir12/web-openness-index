import json
from pathlib import Path

import pandas as pd


INPUT = Path(
    "data/analysis/top1000-2026-09-28/observations.csv"
)

OUTPUT = Path(
    "data/analysis/top1000-2026-09-28/signal_similarity.csv"
)


def normalize(value):
    #values in a consistent format so that they can be compared
    try:
        value = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return str(value)

    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)

    return str(value)#otherwise just convert to text


df = pd.read_csv(INPUT)

results = []

for signal, group in df.groupby("signal"):#group rows by signal
    observed = group[group["outcome"] == "observed"].copy()

    counts = group["outcome"].value_counts()

    if observed.empty:#if no similarity use default values
        similarity = None
        most_common_value = None
        most_common_count = 0
        unique_values = 0
    else:
        observed["value"] = observed["value_json"].map(normalize)#normalize every value
        value_counts = observed["value"].value_counts()

        most_common_value = value_counts.index[0]
        most_common_count = value_counts.iloc[0]
        unique_values = len(value_counts)
        similarity = most_common_count / len(observed)

    results.append(
        {
            "signal": signal,#name of signal
            "domain_count": group["domain"].nunique(),#how many domains had this row
            "observed_count": counts.get("observed", 0),#scanner found evidence to make a conclusion
            "no_evidence_count": counts.get("no_evidence", 0),#scanner couldnt find any evidence
            "skipped_count": counts.get("skipped", 0),#measurement stopped because of policy or scanner constraints
            "error_count": counts.get("error", 0),# failing of scanner(truncated esp)
            "unique_values": unique_values,#outliers
            "most_common_value": most_common_value,
            "most_common_count": most_common_count,
            "similarity_score": similarity,
        }
    )

output = pd.DataFrame(results).sort_values(
    #most similar values(1.0 or closer come first)
    "similarity_score",
    na_position="last",
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
output.to_csv(OUTPUT, index=False)

print(f"Wrote {OUTPUT}")