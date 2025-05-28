"""This script goes through the results of the best class match and generates a report, spreadsheet with the
summary of the results.
"""
import ast
from pathlib import Path
from collections import defaultdict
import pandas as pd
import json
from cognite.neat._issues.warnings import MultiClassFoundWarning, PartialClassFoundWarning

def create_report(issue_csv_file: Path, output_excel_file: Path) -> None:
    """Create report from the issue CSV file."""
    df = pd.read_csv(issue_csv_file)
    is_multi_class = df["NeatIssue"] == 'MultiClassFoundWarning'
    multi_df = df[is_multi_class].copy()
    partial_df = df[~is_multi_class].copy()
    multi_df["alternatives"] = multi_df["alternatives"].apply(ast.literal_eval)
    partial_df["missingProperties"] = partial_df["missingProperties"].apply(ast.literal_eval)

    multi_issues = [
        MultiClassFoundWarning.load(record) for record in multi_df.to_dict(orient="records")
    ]
    partial_issues = [
        PartialClassFoundWarning.load(record) for record in partial_df.to_dict(orient="records")
    ]

    multi_issue_by_alternatives = defaultdict(list)
    for multi_issue in multi_issues:
        multi_issue_by_alternatives[frozenset(multi_issue.alternatives | {multi_issue.selected_class})].append(multi_issue.instance)

    instances_by_class_missing_pair = defaultdict(list)
    for partial_issue in partial_issues:
        instances_by_class_missing_pair[(partial_issue.best_class, partial_issue.missing_properties)].append(partial_issue.instance)

    df = pd.DataFrame()
    counter = 0
    for no, (alternatives, instances) in enumerate(multi_issue_by_alternatives.items(), 1):
        df[f"Alternatives_{no}"] = pd.Series(sorted(alternatives))
        if len(instances) > len(df):
            df = df.reindex(range(len(instances)))
        df[f"Instances_{no}({len(instances)})"] = pd.Series(instances)
        counter = no

    for no, ((class_name, missing_properties), instances) in enumerate(instances_by_class_missing_pair.items(), counter+1):
        df[f"Case_{no}_{class_name}"] = pd.Series(sorted(missing_properties))
        if len(instances) > len(df):
            df = df.reindex(range(len(instances)))
        df[f"Instances_{no}({len(instances)})"] = pd.Series(instances)

    df.to_excel(output_excel_file, index=False)
    print(f"Report created: {output_excel_file.as_posix()!r}")
