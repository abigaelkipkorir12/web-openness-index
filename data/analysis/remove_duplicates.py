
import pandas as pd
path = "/mnt/c/Users/abiga/Downloads/cloudflare-radar_top-1000-domains_20260921-20260928.csv"

df = pd.read_csv(path)

print("Rows:", len(df))
print("Columns:", list(df.columns))

domain_col = next(
    col for col in df.columns
    if col.lower() in {"domain", "hostname", "host"}
)

domains = (
    df[domain_col]
    .astype(str)
    .str.strip()
    .str.lower()
    .str.rstrip(".")
)

print("Unique domains:", domains.nunique())
print("Repeated rows:", len(domains) - domains.nunique())

print("\nDuplicates:")
print(df[domains.duplicated(keep=False)].sort_values(domain_col).to_string(index=False))
