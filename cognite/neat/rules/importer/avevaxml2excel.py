"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

import warnings
from pathlib import Path

import pandas as pd
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from cognite.neat.rules import parse_rules_from_excel_file
from cognite.neat.rules import _exceptions
from cognite.neat.utils.utils import generate_exception_report,  pascal_case, camel_case

REPLACE_TYPE = {
    "String": "string",
    "Boolean": "boolean",
    "Decimal": "float",
}

def _create_default_metadata_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Metadata pydantic model
    return {
        "header": (
            "namespace",
            "prefix",
            "dataModelName",
            "cdfSpaceName",
            "version",
            "isCurrentVersion",
            "created",
            "updated",
            "title",
            "description",
            "creator",
            "contributor",
            "rights",
            "license",
        )
    }


def _create_default_classes_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Class pydantic model
    return {
        "helper_row": ("Data Model Definition", "", "", "", "State", "", "", "Knowledge acquisition log", "", "", ""),
        "header": (
            "Class",
            "Name",
            "Description",
            "Parent Class",
            "Deprecated",
            "Deprecation Date",
            "Replaced By",
            "Source",
            "Source Entity Name",
            "Match",
            "Comment",
        ),
    }


def _create_default_properties_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Property pydantic model
    return {
        "helper_row": (
            "Data Model Definition",
            "",
            "",
            "",
            "",
            "",
            "",
            "State",
            "",
            "",
            "Knowledge acquisition log",
            "",
            "",
            "",
        ),
        "header": (
            "Class",
            "Property",
            "Name",
            "Description",
            "Type",
            "Min Count",
            "Max Count",
            "Deprecated",
            "Deprecation Date",
            "Replaced By",
            "Source",
            "Source Entity Name",
            "Match",
            "Comment",
        ),
    }


def avevaxml2excel(avevaxml_filepath: Path, excel_filepath: Path = None, validate_results: bool = True):
    """Convert owl ontology to transformation rules serialized as Excel file.

    Parameters
    ----------
    avevaxml_filepath : Path
        Path to Aveva XML ontology
    excel_filepath : Path
        Path to save transformation rules, defaults to None
    validate_results : bool, optional
        Whether to validate generated Excel file and create validation report, by default True
    """

    avevaxml_filepath = Path(avevaxml_filepath)
    if excel_filepath:
        excel_filepath = Path(excel_filepath)
    else:
        excel_filepath = avevaxml_filepath.parent / "transformation_rules.xlsx"

    tree = ET.parse(avevaxml_filepath)
    root = tree.getroot()

    with pd.ExcelWriter(excel_filepath) as writer:
        _parse_avevaxml_metadata_df(root).to_excel(writer, sheet_name="Metadata", header=False)
        _parse_avevaxml_classes_df(root).to_excel(writer, sheet_name="Classes", index=False, header=True)
        _parse_avevaxml_properties_df(root).to_excel(writer, sheet_name="Properties", index=False, header=True)

    if validate_results:
        _validate_excel_file(excel_filepath)


def _parse_avevaxml_metadata_df(root: Element, parsing_config: dict = None) -> pd.DataFrame:
    """Parse xml metadata to pandas dataframe.

    Parameters
    ----------
    root : Element
        XML Element tree to query
    parsing_config : dict, optional
        Configuration for parsing, by default None

    Returns
    -------
    pd.DataFrame
        Dataframe containing xml metadata
    """
   
    if parsing_config is None:
        parsing_config = _create_default_metadata_parsing_config()
        
    xmlns = root.tag.split("}")[0]+ "}"
    root_attributes = root.attrib
    
    attributes = {}
    attributes["namespace"] = xmlns.replace("{", "").replace("}", "")
    attributes["prefix"] = root_attributes["id"]
    attributes["description"] = root_attributes["description"]
    attributes["version"] = root_attributes["version"]
    attributes["updated"] = root_attributes["versionDate"].replace(".","_")
    attributes["created"] = root_attributes["versionDate"].replace(".","_")
    attributes["isCurrentVersion"] = "TRUE"
    attributes["cdfSpaceName"] = root_attributes["contentType"]
    attributes["dataModelName"] = root_attributes["contentType"]
    attributes["title"] = root_attributes["name"]    
    attributes["creator"] = root_attributes["id"]    
    
    df_metadata = pd.DataFrame(attributes, index=[0])
    columns_to_keep = list(parsing_config["header"])
    missing_fields = [item for item in columns_to_keep if item not in df_metadata.columns]
    for field in missing_fields:
        df_metadata[field] = ''
    df_metadata = df_metadata[columns_to_keep]
    
    return df_metadata.T


def _parse_avevaxml_classes_df(root: Element, parsing_config: dict = None) -> pd.DataFrame:
    """Get all classes from the xml and their parent classes.

    Parameters
    ----------
    root : Element
        XML Element tree to query
    parsing_config : dict, optional
        Configuration for parsing the dataframe, by default None

    Returns
    -------
    pd.DataFrame
        Dataframe with columns: class, parentClass
    """
    
      
    if parsing_config is None:
        parsing_config = _create_default_classes_parsing_config()
    
    xmlns = root.tag.split("}")[0]+ "}"
    functionals = root.findall(f".//{xmlns}Functionals")[0] #TODO: Better parsing of this, learn xml package
    classes = functionals.findall(f".//{xmlns}Class")
    
    classes_lst = [item.attrib for item in classes]
    df_class = pd.DataFrame(classes_lst)
    df_class["Source"] = xmlns.replace("{","").replace("}","")
    df_class["Source Entity Name"] = df_class["id"]
    df_class["Match"] = "exact"
    df_class["Class"] = [pascal_case(item) for item in df_class["name"]]
    df_class["Name"] = df_class["name"] 
    df_class["Deprecated"] = df_class["obsolete"]
    df_class["Description"] = df_class["description"]

    columns_to_keep = list(parsing_config["header"]) 
    missing_fields = [item for item in columns_to_keep if item not in df_class.columns]
    for field in missing_fields:
        df_class[field] = None
    df_class = df_class[columns_to_keep]
    df_class = df_class.T.reset_index().T.reset_index(drop=True)
    df_class.columns = parsing_config["helper_row"]
        
    return df_class
    

def _parse_avevaxml_properties_df(root: Element, parsing_config: dict = None ) -> pd.DataFrame:
    """Get all properties from the XML file

    Parameters
    ----------
    root : Element
        XML Element tree to query
    parsing_config : dict, optional
        Configuration for parsing the dataframe, by default None

    Returns
    -------
    pd.DataFrame
        Dataframe with columns: class, property, name, ...
    """
    
    if parsing_config is None:
        parsing_config = _create_default_properties_parsing_config()
        
    xmlns = root.tag.split("}")[0]+ "}"
    functionals = root.findall(f".//{xmlns}Functionals")[0] #TODO: Better parsing of this, learn xml package
    classes = functionals.findall(f".//{xmlns}Class")
    
    classes_attrib_dict = {}
    for class_item in classes:
        lst = []
        for attrib in class_item[0]:
            if attrib.attrib["obsolete"] == "false": # get only non-obsolete attributes
                lst.append(attrib.attrib)
            else:
                pass
        classes_attrib_dict[class_item.attrib["id"]] = lst
    
    classes_lst = [item.attrib for item in classes]
    classes_dict = {item["id"]:item for item in classes_lst}

    attributes_root = root[1] #TODO: Better parsing of this, learn xml package
    all_attributes = []
    for attribute in attributes_root:
        all_attributes.append(attribute)
        
    attributes_dict = {}
    for item in all_attributes:
        attributes_dict[item.attrib["id"]] = item.attrib
        
    df_lst = []
    for k, v in classes_attrib_dict.items():
        lst = []
        for item in v:
            lst.append(attributes_dict[item["id"]])
        
        def _replace_type(item):
            if REPLACE_TYPE.get(item, None) is not None:
                return REPLACE_TYPE[item]
            else:
                return item

        df_temp = pd.DataFrame(lst)
        class_name = classes_dict[k]["name"]
        df_temp["Class"] = pascal_case(class_name)
        df_temp["Property"] = df_temp["name"].apply(lambda x: camel_case(x))
        df_temp["Source"] = xmlns.replace("{", "").replace("}", "")
        df_temp["Name"] = df_temp["name"]
        df_temp["Source Entity Name"] = df_temp["name"]
        df_temp["Description"] = df_temp["description"]
        df_temp["dataType"] = df_temp["dataType"].apply(lambda x: _replace_type(x))
        
        df_temp = df_temp.rename(columns={"dataType": "Type", "obsolete": "Deprecated"})
        df_lst.append(df_temp)
        
    df_attributes = pd.concat(df_lst)
    
    columns_to_keep = list(parsing_config["header"]) 
    missing_fields = [item for item in columns_to_keep if item not in df_attributes.columns]
    for field in missing_fields:
        df_attributes[field] = ''
    df_attributes = df_attributes[columns_to_keep]
    df_attributes.iloc[0,:] = df_attributes.columns
    df_attributes.columns = parsing_config["helper_row"]
    
    return df_attributes


def _validate_excel_file(excel_filepath: Path):
    _, validation_errors, validation_warnings = parse_rules_from_excel_file(excel_filepath, return_report=True)

    report = ""
    if validation_errors:
        warnings.warn(
            _exceptions.Warning1().message,
            category=_exceptions.Warning1,
            stacklevel=2,
        )
        report = generate_exception_report(validation_errors, "Errors")

    if validation_warnings:
        warnings.warn(
            _exceptions.Warning2().message,
            category=_exceptions.Warning2,
            stacklevel=2,
        )
        report += generate_exception_report(validation_warnings, "Warnings")

    if report:
        with open(excel_filepath.parent / "report.txt", "w") as f:
            f.write(report)
