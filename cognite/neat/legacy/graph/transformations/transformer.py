"""Methods to transform Domain Knowledge Graph to App Knowledge Graph"""

import logging
import time
import traceback
from typing import Any

import pandas as pd
from cognite.client import CogniteClient
from prometheus_client import Gauge
from pydantic import BaseModel
from rdflib import RDF, Graph
from rdflib.term import Literal, Node

from cognite.neat.legacy.graph.exceptions import NamespaceRequired
from cognite.neat.legacy.graph.transformations.query_generator.sparql import build_sparql_query
from cognite.neat.legacy.rules.models._base import EntityTypes
from cognite.neat.legacy.rules.models.rdfpath import (
    AllProperties,
    AllReferences,
    Query,
    RawLookup,
    Traversal,
    parse_rule,
)
from cognite.neat.legacy.rules.models.rules import Rules
from cognite.neat.utils.utils import remove_namespace

prom_total_proc_rules_g = Gauge("neat_total_processed_rules", "Number of processed rules", ["state"])
rules_processing_timing_metric = Gauge(
    "neat_rules_processing_timing", "Transformation rules processing timing metrics", ["aggregation"]
)


COMMIT_BATCH_SIZE = 10000


class RuleProcessingReportRec(BaseModel):
    """Report record for rule processing"""

    row_id: str | None = None
    rule_name: str | None = None
    rule_type: str | None = None
    rule_expression: Any | None = None
    status: str | None = None
    error_message: str | None = None
    elapsed_time: float = 0
    rows_in_response: int = 0


class RuleProcessingReport(BaseModel):
    """Report for rule processing"""

    total_rules: int = 0
    total_success: int = 0
    total_success_no_results: int = 0
    total_failed: int = 0
    records: list[RuleProcessingReportRec] = []
    elapsed_time: float = 0


def source2solution_graph(
    source_knowledge_graph: Graph,
    transformation_rules: Rules,
    solution_knowledge_graph: Graph | None = None,
    client: CogniteClient | None = None,
    cdf_lookup_database: str | None = None,
    extra_triples: list[tuple[Node, Node, Node]] | None = None,
    stop_on_exception: bool = False,
    missing_raw_lookup_value: str = "NaN",
    processing_report: RuleProcessingReport | None = None,
) -> Graph:
    """Transforms solution knowledge graph based on Domain Knowledge Graph

    Args:
        source_knowledge_graph: Domain Knowledge Graph which represents the source graph being
                                transformed to app/solution specific graph
        transformation_rules: Transformation rules holding data model definition and rules to
                              transform source/domain graph to app/solution specific graph
        solution_knowledge_graph: Graph to store app/solution specific graph.
                            Defaults to None (i.e., empty graph).
        client: CogniteClient. Defaults to None.
        cdf_lookup_database: CDF RAW database name to use for `rawlookup` rules. Defaults to None.
        extra_triples: Additional triples to add to app/solution knowledge graph. Defaults to None.
        stop_on_exception: To stop on exception. Defaults to False.
        missing_raw_lookup_value: If no value is find for `rawlookup` default value to use. Defaults to "NaN".
        processing_report: Processing report to store results to. Defaults to None.

    Returns:
        Transformed knowledge graph based on transformation rules
    """

    # TODO: This is to be improved and slowly sunset domain2app_knowledge_graph

    return domain2app_knowledge_graph(
        domain_knowledge_graph=source_knowledge_graph,
        transformation_rules=transformation_rules,
        app_instance_graph=solution_knowledge_graph,
        client=client,
        cdf_lookup_database=cdf_lookup_database,
        extra_triples=extra_triples,
        stop_on_exception=stop_on_exception,
        missing_raw_lookup_value=missing_raw_lookup_value,
        processing_report=processing_report,
    )


def domain2app_knowledge_graph(
    domain_knowledge_graph: Graph,
    transformation_rules: Rules,
    app_instance_graph: Graph | None = None,
    client: CogniteClient | None = None,
    cdf_lookup_database: str | None = None,
    extra_triples: list[tuple[Node, Node, Node]] | None = None,
    stop_on_exception: bool = False,
    missing_raw_lookup_value: str = "NaN",
    processing_report: RuleProcessingReport | None = None,
) -> Graph:
    """Generates application/solution specific knowledge graph based on Domain Knowledge Graph

    Args:
        domain_knowledge_graph: Domain Knowledge Graph which represent the source graph being
                                transformed to app/solution specific graph
        transformation_rules: Transformation rules holding data model definition and rules
                              to transform source/domain graph to app/solution specific graph
        app_instance_graph: Graph to store app/solution specific graph. Defaults to None (i.e., empty graph).
        client: CogniteClient. Defaults to None.
        cdf_lookup_database: CDF RAW database name to use for `rawlookup` rules. Defaults to None.
        extra_triples: Additional triples to add to app/solution knowledge graph. Defaults to None.
        stop_on_exception: To stop on exception. Defaults to False.
        missing_raw_lookup_value: If no value is find for `rawlookup` default value to use. Defaults to "NaN".
        processing_report: Processing report to store results to. Defaults to None.

    Returns:
        Transformed knowledge graph based on transformation rules
    """
    if transformation_rules.metadata.namespace is None:
        raise NamespaceRequired("Transform domain to app knowledge graph")
    rule_namespace = transformation_rules.metadata.namespace

    if app_instance_graph is None:
        app_instance_graph = Graph()
        # Bind App namespace and prefix
        app_instance_graph.bind(transformation_rules.metadata.prefix, rule_namespace)
        # Bind other prefixes and namespaces
        for prefix, namespace in transformation_rules.prefixes.items():
            app_instance_graph.bind(prefix, namespace)

    tables_by_name = {}
    if cdf_lookup_database and client:
        for table_name in transformation_rules.raw_tables:
            logging.debug(f"Loading {table_name} table from database {cdf_lookup_database}")
            table = client.raw.rows.retrieve_dataframe(cdf_lookup_database, table_name, limit=-1)
            tables_by_name[table_name] = table

    # Add references with their type first
    types = []
    success = 0
    success_no_results = 0
    failed = 0
    commit_counter = 0
    timing_traces = []
    prom_total_proc_rules_g.labels(state="success_no_results").set(0)
    prom_total_proc_rules_g.labels(state="success").set(0)
    prom_total_proc_rules_g.labels(state="failed").set(0)

    def check_commit(force_commit: bool = False):
        """'Commit nodes to the graph if batch counter is reached or if force_commit is True"""

        if force_commit:
            logging.debug("Committing nodes")
            app_instance_graph.commit()
            logging.debug("Nodes committed")
            return
        nonlocal commit_counter
        commit_counter += 1
        if commit_counter >= COMMIT_BATCH_SIZE:
            logging.info(f"Committing {COMMIT_BATCH_SIZE} nodes")
            app_instance_graph.commit()
            logging.info(f" {COMMIT_BATCH_SIZE} nodes committed")
            commit_counter = 0

    proc_start_time = time.perf_counter()
    for sheet_row, rule_definition in transformation_rules.properties.items():
        if not rule_definition.rule or rule_definition.skip_rule:
            continue
        msg = f"Processing {sheet_row}: class <{rule_definition.class_id}> "
        msg += f"property <{rule_definition.property_name}> rule <{rule_definition.rule}>"

        processing_report_rec = RuleProcessingReportRec(
            row_id=sheet_row,
            rule_name=f"{rule_definition.class_id}_{rule_definition.property_name}",
            rule_type=rule_definition.rule_type,
            rule_expression=rule_definition.rule,
        )
        logging.info(msg)
        try:
            start_time = time.perf_counter()
            # Parse rule:
            rule = parse_rule(rule_definition.rule, rule_definition.rule_type)  # type: ignore[arg-type]

            # Build SPARQL if needed:
            if isinstance(rule.traversal, Query) and rule_definition.rule_type == "sparql":
                query = rule.traversal.query
            elif isinstance(rule.traversal, Traversal | str):
                query = build_sparql_query(domain_knowledge_graph, rule.traversal, transformation_rules.prefixes)
            else:
                raise ValueError(f"Unknown traversal type {type(rule.traversal)}")
            logging.debug(f"Query: {query}")

            if query_results := list(domain_knowledge_graph.query(query)):
                # Generate URI for class and property in target namespace
                class_URI = rule_namespace[rule_definition.class_id]
                property_URI = rule_namespace[rule_definition.property_name]  # type: ignore[index]

                # Turn query results into dataframe
                instance_df = pd.DataFrame(
                    query_results, columns=[EntityTypes.subject, EntityTypes.predicate, EntityTypes.object]
                )

                # If we are not grabbing all properties for class instances
                # then we are able to replace source property URI with target property URI
                # otherwise we should keep source property URI
                if not isinstance(rule.traversal, AllProperties):
                    instance_df[EntityTypes.predicate] = property_URI

                # If we are storing object from the source graph as literal value(propety type being Datatype Property)
                # in the target graph then we should remove namespace from the object URI and store it as literal
                if isinstance(rule.traversal, AllReferences) and rule_definition.property_type == "DatatypeProperty":
                    instance_df[EntityTypes.object] = instance_df[EntityTypes.object].apply(
                        lambda x: Literal(remove_namespace(x))
                    )

                if isinstance(rule, RawLookup):
                    lookup_map = tables_by_name[rule.table.name].set_index(rule.table.key)[rule.table.value].to_dict()

                    def lookup(
                        literal: Literal, lookup_table=lookup_map, missing_raw_lookup_value=missing_raw_lookup_value
                    ):
                        if new_value := lookup_table.get(literal.value):
                            return Literal(new_value, literal.language, literal.datatype, bool(literal.normalize))
                        elif missing_raw_lookup_value:
                            return Literal(
                                missing_raw_lookup_value, literal.language, literal.datatype, bool(literal.normalize)
                            )
                        else:
                            return literal

                    instance_df[EntityTypes.object] = instance_df[EntityTypes.object].apply(lookup)

                # Add instances
                for _, triple in instance_df.iterrows():
                    app_instance_graph.add(triple.values)  # type: ignore[arg-type]
                    check_commit()
                # Setting instances type and merging them with df containing instance - type relations
                instance_df[EntityTypes.predicate] = RDF.type
                instance_df[EntityTypes.object] = class_URI
                types.append(instance_df)
                success += 1
                prom_total_proc_rules_g.labels(state="success").inc()
                elapsed_time = time.perf_counter() - start_time
                timing_traces.append(elapsed_time)
                processing_report_rec.elapsed_time = elapsed_time
                processing_report_rec.status = "success"
                processing_report_rec.rows_in_response = len(instance_df)
            else:
                success_no_results += 1
                prom_total_proc_rules_g.labels(state="success_no_results").inc()
                elapsed_time = time.perf_counter() - start_time
                timing_traces.append(elapsed_time)
                processing_report_rec.elapsed_time = elapsed_time
                processing_report_rec.status = "success_no_results"

        except Exception as e:
            failed += 1
            elapsed_time = time.perf_counter() - start_time
            processing_report_rec.elapsed_time = elapsed_time
            processing_report_rec.status = "failed"
            processing_report_rec.error_message = str(e)
            prom_total_proc_rules_g.labels(state="failed").inc()
            logging.error(
                f" Error while processing rule {rule_definition.rule} for class {rule_definition.class_id} \
                and property {rule_definition.property_name}"
            )
            logging.error(traceback.format_exc())
            if stop_on_exception:
                raise e

        if processing_report:
            processing_report.records.append(processing_report_rec)

    if processing_report:
        processing_report.total_rules = len(transformation_rules.properties)
        processing_report.total_success = success
        processing_report.total_success_no_results = success_no_results
        processing_report.total_failed = failed
        processing_report.elapsed_time = time.perf_counter() - proc_start_time

    if timing_traces:
        df = pd.Series(timing_traces)
        rules_processing_timing_metric.labels(aggregation="sum").set(df.sum())
        rules_processing_timing_metric.labels(aggregation="std_div").set(df.std())
        rules_processing_timing_metric.labels(aggregation="min").set(df.min())
        rules_processing_timing_metric.labels(aggregation="max").set(df.max())
        rules_processing_timing_metric.labels(aggregation="mean").set(df.mean())

    type_df = pd.concat(types).drop_duplicates(EntityTypes.subject).reset_index(drop=True)

    # Add instance - RDF Type relations
    for _, triple in type_df.iterrows():  # type: ignore[assignment]
        app_instance_graph.add(triple.values)  # type: ignore[arg-type]
        check_commit()

    for i, triple in enumerate(extra_triples or []):  # type: ignore[assignment]
        try:
            app_instance_graph.add(triple)  # type: ignore[arg-type]
            check_commit()
        except ValueError as e:
            raise ValueError(f"Triple {i} in extra_triples is not correct and cannot be added!") from e

    check_commit(force_commit=True)
    return app_instance_graph
