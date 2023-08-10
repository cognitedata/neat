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

from datetime import datetime

# get the start time

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
        "helper_row": ("Data Model Definition", "", "", "", "State", "", "", "Knowledge acquisition log", "", "", "", "", ""),
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
            "Taxonomy",
            "Class Category"
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
            "",
            "",
            "State",
            "",
            "",
            "Knowledge acquisition log",
            "",
            "",
            "",
            "",
            "",
        ),
        "header": (
            "Class",
            "Property",
            "Name",
            "Description",
            "Parent Class",
            "Default",
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
            "Taxonomy",
            "Class Category"
        ),
    }


class AvevaXML:
    
    def __init__(self, xml_filepath, dataframe_filter=None, dataframe_start_idx=None, dataframe_end_idx=None):
        self.tree = ET.parse(xml_filepath)
        self.root = self.tree.getroot()
        self.xmlns = self.root.tag.split("}")[0]+ "}"
        self.parent_map = {c:p for p in self.tree.iter() for c in p}
        self.dataframe_filter = dataframe_filter
        self.dataframe_start_idx = dataframe_start_idx
        self.dataframe_end_idx = dataframe_end_idx
        
        self._parse_attributes()
        self._parse_functional_classes()
        self._parse_document_classes()
        self._parse_taxonomies()
        
    def _parse_attributes(self):
        for item in self.root:
            if f"{self.xmlns}Attributes" == item.tag:
                attributes = item
                
        attributes = attributes.findall(f".//{self.xmlns}Attribute")
        self.attributes_dict = {i.attrib['id']: i.attrib for i in attributes}
        
        
        
    def _parse_functional_classes(self):
        for item in self.root:
            if f"{self.xmlns}Functionals" == item.tag:
                functionals = item
                
        functional_classes = functionals.findall(f".//{self.xmlns}Class")
        functional_classes_dict = {i.attrib['id']: i.attrib for i in functional_classes}
        
        for class_item in functional_classes:
            # list_of_attributes = []
            class_attributes_dict = {}
            for item in class_item:
                if f"{self.xmlns}Attributes" == item.tag:
                    attributes = item
                    
            for attribute in attributes:
                # if attrib.attrib["obsolete"] == "false": # get only non-obsolete attributes
                # list_of_attributes.append(attribute.attrib)
                tmp_dict = attribute.attrib
                try:
                    tmp_dict2 = self.attributes_dict[attribute.attrib["id"]]
                except KeyError as e:
                    warnings.warn(f"Attribute {attribute.attrib['id']} not found in attributes dictionary")
                    
                tmp_dict.update(tmp_dict2)
                class_attributes_dict[attribute.attrib["id"]] = tmp_dict
                
            functional_classes_dict[class_item.attrib["id"]]["attributes"] = class_attributes_dict

        self.functional_classes_dict = functional_classes_dict
        
        
    def _parse_document_classes(self):
        for item in self.root:
            if f"{self.xmlns}Documents" == item.tag:
                documents = item
                
        document_classes = documents.findall(f".//{self.xmlns}Class")
        self.document_classes_dict = {i.attrib['id']: i.attrib for i in document_classes}
        
    
    def _parse_taxonomies(self):
        all_nodes = []
        taxonomies = self.root.findall(f".//{self.xmlns}Taxonomy")
        nodes = self.root.findall(f".//{self.xmlns}Node")

        for node in nodes:
            node_entity = {}
            
            attributes = node.findall(f".//{self.xmlns}Attributes") 
            if attributes == []: # skip nodes where there are no attributes
                continue
            
            taxonomy = None
            while taxonomy not in taxonomies:
                if taxonomy is None:
                    taxonomy = self.parent_map[self.parent_map[node]]
                else: 
                    taxonomy = self.parent_map[taxonomy]

            for attribute in taxonomy.attrib:
                node_entity[f"taxonomy_{attribute}"] = taxonomy.attrib[attribute]
                
            if taxonomy.attrib['concept'] == 'Document': # Not looking at document taxonomies for now
                continue
            
            
            functional_class = None
            for item in node:
                if f"{self.xmlns}Classes" == item.tag:
                    functional_class = item[0]
                    
            
            if functional_class is not None:
                functional_class_id = functional_class.attrib['id']
                functional_class_data = self.functional_classes_dict[functional_class_id]
                for k, v in functional_class_data.items():
                    node_entity[f'class_{k}'] = v
              
            # if attributes != []:
            attributes = attributes[0]
            attributes = [i.attrib for i in attributes]
            node_entity['set_attributes'] = {i['id']: i['value'] for i in attributes}
                
            try:
                node_entity["attributes"] = self.functional_classes_dict[node_entity["class_id"]]["attributes"]
            except KeyError:
                pass
            
            parent_node = self.parent_map[self.parent_map[node]]
        
                
            node_entity['parent'] = parent_node.attrib
            for attribute in parent_node.attrib:
                node_entity[f"parent_{attribute}"] = parent_node.attrib[attribute]
                
            node_entity['id'] = node.attrib['id']
            node_entity['name'] = node.attrib['name']
            if '|' in node.attrib['name']:
                node_entity['unique_id'] = node.attrib['name'].split(' ')[0] # Perhaps a more explicity way of gettign unique ID, traverse up tree and combine all the node ids together
            else:
                node_entity['unique_id'] = node.attrib['id']
                
            if '|' in node_entity['parent_name']:
                node_entity['parent_unique_id'] = node_entity['parent']['name'].split(' ')[0]
            else:
                node_entity['parent_unique_id'] = node_entity['parent_id']
            
            all_nodes.append(node_entity)
            
        df = pd.DataFrame(all_nodes)
        df["Taxonomy"] = df["taxonomy_id"]
        df["Class Category"] = df["parent_id"]
        
        if self.dataframe_filter is not None:
            filter_lst = list(zip(self.dataframe_filter.keys(), self.dataframe_filter.values()))
            df2 = pd.DataFrame()
            for item in filter_lst:
                if df2.empty:
                    # df2 = df_class[(df_class[item[0]].isin(item[1]))]
                    df2 = df[df[item[0]].isnull() | df[item[0]].isin(item[1])]
                else:
                    # df2 = df2[(df2[item[0]].isin(item[1]))]
                    df2 = df2[df2[item[0]].isnull() | df2[item[0]].isin(item[1])]
                    
            df = df2
            
        if (self.dataframe_start_idx is not None) and (self.dataframe_end_idx is not None): 
            df = df.iloc[self.dataframe_start_idx: self.dataframe_end_idx]
            
        elif (self.dataframe_start_idx is not None) and (self.dataframe_end_idx is None):
            df = df.iloc[self.dataframe_start_idx:]
            
        elif (self.dataframe_start_idx is None) and (self.dataframe_end_idx is not None):
            df = df.iloc[:self.dataframe_end_idx]
            
        else:
            raise ValueError("Must specify either dataframe_start_idx or dataframe_end_idx") # TODO: Fix this so that it can be either or

        
        # self.df = df[df['taxonomy_concept']=='Functional']
        self.df = df
        

def avevaxml2excel(avevaxml_filepath: Path, excel_filepath: Path = None, validate_results: bool = True, dataframe_filter: dict = None, dataframe_start_idx: int =None, dataframe_end_idx: int =None):
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

    avevaxml = AvevaXML(avevaxml_filepath, dataframe_filter=dataframe_filter, dataframe_start_idx=dataframe_start_idx, dataframe_end_idx=dataframe_end_idx)

    with pd.ExcelWriter(excel_filepath) as writer:
        _parse_avevaxml_metadata_df(avevaxml).to_excel(writer, sheet_name="Metadata", header=False)
        _parse_avevaxml_classes_df(avevaxml, dataframe_filter = dataframe_filter).to_excel(writer, sheet_name="Classes", index=False, header=True)
        _parse_avevaxml_properties_df(avevaxml, dataframe_filter = dataframe_filter).to_excel(writer, sheet_name="Properties", index=False, header=True)
        
    if validate_results:
        _validate_excel_file(excel_filepath)
        
        
def _parse_avevaxml_metadata_df(avevaxml: AvevaXML, parsing_config: dict = None) -> pd.DataFrame:
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
        
    xmlns = avevaxml.xmlns
    root_attributes = avevaxml.root.attrib
    
    attributes = {}
    attributes["namespace"] = xmlns.replace("{", "").replace("}", "")
    attributes["prefix"] = root_attributes["id"]
    attributes["description"] = root_attributes["description"]
    attributes["version"] = root_attributes["version"]
    attributes["updated"] = datetime.fromisoformat(root_attributes["versionDate"].replace(".","-"))
    attributes["created"] = datetime.fromisoformat(root_attributes["versionDate"].replace(".","-"))
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


def _get_class_attribute(avevaxml):
    attributes_dict = avevaxml.attributes_dict
    group_ids = list(set([v.get("groupId", None) for v in attributes_dict.values()]))
    group_ids = [''.join((x for x in group_id if not x.isdigit())) for group_id in group_ids]
    
    class_object_lst = []
    for group_id in group_ids:
        class_object = {}
        class_object["Class"] = pascal_case(group_id)
        class_object["Name"] = group_id
        class_object["Description"] = group_id
        class_object["Source Entity Name"] = group_id
        class_object["Source"] = avevaxml.xmlns.replace("{","").replace("}","")
        class_object["Deprecated"] = "false"
        class_object["Match"] = "exact"
        class_object_lst.append(class_object)
        
    return pd.DataFrame(class_object_lst)


def _parse_avevaxml_classes_df(avevaxml: AvevaXML, parsing_config: dict = None, dataframe_filter: dict = None) -> pd.DataFrame:
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
        Dataframe with columns: class, parentClasss
    """
    
      
    if parsing_config is None:
        parsing_config = _create_default_classes_parsing_config()
    
    xmlns = avevaxml.xmlns

    df_class = avevaxml.df
    if 'class_obsolete' in df_class.columns:
        df_class = df_class[~df_class['class_obsolete'].isna()] # only take nodes that have a class
    
    # classes_lst = [item.attrib for item in classes]
    # df_class = pd.DataFrame(classes_lst)
    # id_to_name = dict(zip(df_class["unique_id"], [pascal_case(item) for item in df_class["name"]]))
    
    df_class["Source"] = xmlns.replace("{","").replace("}","")
    df_class["Source Entity Name"] = df_class["name"]
    df_class["Match"] = "exact"
    df_class["Class"] = [pascal_case(item) for item in df_class["unique_id"]]
    df_class["Name"] = df_class["name"] 
    # df_class["Description"] = [item['3213'] for item in df_class["set_attributes"]]
    df_class["Description"] = df_class["class_description"]
    # df_class["Taxonomy"] = df_class["taxonomy_id"]
    df_class["Parent Class"] = [pascal_case(item) for item in df_class["parent_unique_id"]]
    # df_class["Class Category"] = df_class["parent_id"]
    if 'class_obsolete' in df_class.columns:
        df_class["Deprecated"] = df_class["class_obsolete"]
        
    df_class_attributes = _get_class_attribute(avevaxml)
    df_class = pd.concat([df_class, df_class_attributes])

    columns_to_keep = list(parsing_config["header"]) 
    missing_fields = [item for item in columns_to_keep if item not in df_class.columns]
    for field in missing_fields:
        df_class[field] = None
    df_class = df_class[columns_to_keep]
    
    # if dataframe_filter is not None:
    #     filter_lst = list(zip(dataframe_filter.keys(), dataframe_filter.values()))
    #     df2 = pd.DataFrame()
    #     for item in filter_lst:
    #         if df2.empty:
    #             # df2 = df_class[(df_class[item[0]].isin(item[1]))]
    #             df2 = df_class[df_class[item[0]].isnull() | df_class[item[0]].isin(item[1])]
    #         else:
    #             # df2 = df2[(df2[item[0]].isin(item[1]))]
    #             df2 = df2[df2[item[0]].isnull() | df2[item[0]].isin(item[1])]
                
    #     df_class = df2
        
    df_class = df_class.T.reset_index().T.reset_index(drop=True)
    df_class.columns = parsing_config["helper_row"]
    
        
    return df_class


def _get_unique_attributes(avevaxml, unique_attributes):

    def _replace_type(item):
        if REPLACE_TYPE.get(item, None) is not None:
            return REPLACE_TYPE[item]
        else:
            return item
        
    attributes_dict = avevaxml.attributes_dict
    
    attributes_lst = []
    for v in attributes_dict.values():
        group_id = ''.join((x for x in v.get("groupId", None) if not x.isdigit()))
        group_id = camel_case(group_id)
        if group_id not in unique_attributes:
            continue
        attribute = {}
        attribute["Name"] = v.get("name", None)
        attribute["Property"] = camel_case(v.get("name", None))
        attribute["Description"] = v.get("description", None)
        attribute["Deprecated"] = v.get("obsolete", None)
        group_id = pascal_case(v.get("groupId", None))
        attribute["Class"] = ''.join((x for x in group_id if not x.isdigit()))
        attribute["Source Entity Name"] = v.get("name", None)
        attribute["Type"] = _replace_type(v.get("dataType", None))
        attribute["Min Count"] = 0
        attribute["Max Count"] = 1
        attributes_lst.append(attribute)
        
    return pd.DataFrame(attributes_lst)
    

def _parse_avevaxml_properties_df(avevaxml: AvevaXML, parsing_config: dict = None, dataframe_filter: dict = None ) -> pd.DataFrame:
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
        
    xmlns = avevaxml.xmlns
    # functionals = root.findall(f".//{xmlns}Functionals")[0] #TODO: Better parsing of this, learn xml package
    # functional_classes = functionals.findall(f".//{xmlns}Class")
    
    # for item in avevaxml.root:
    #     if f"{xmlns}Functionals" == item.tag:
    #         functionals = item
            
    # functional_classes = functionals.findall(f".//{xmlns}Class")
    
    # classes_lst = [item.attrib for item in functional_classes]
    # classes_dict = {item["id"]:item for item in classes_lst}

    # for class_item in functional_classes:
    #     list_of_attributes = []
    #     for attrib in class_item[0]:
    #         # if attrib.attrib["obsolete"] == "false": # get only non-obsolete attributes
    #         list_of_attributes.append(attrib.attrib)
            
    #     classes_dict[class_item.attrib["id"]]["attributes"] = list_of_attributes

    df_class = avevaxml.df
    # df_class = df_class[df_class["taxonomy_name"] =="OIH Tag Classes - VAL"]
    if 'class_obsolete' in df_class.columns:
        df_class = df_class[~df_class["class_obsolete"].isna()] # only take nodes that have a class
    

    df_lst = []
    for _, row in df_class.iterrows():
        if pd.isna(row["attributes"]):
            continue
        group_ids = list(set([v['groupId'] for v in row["attributes"].values()]))
        group_ids = [''.join((x for x in group_id if not x.isdigit())) for group_id in group_ids]
        
        data = [
            {
                'Class': pascal_case(row["unique_id"]),
                'Property': camel_case(k),
                'Name': k,
                'Deprecated': 'false',
                'Type': pascal_case(k),
                'Description': None,
                'Taxonomy': row["Taxonomy"],
                'Parent Class': pascal_case(row["parent_unique_id"]),
                'Class Category': row['Class Category']
                } 
            for k in group_ids
            ]
        
        
        
        # data = list(row["attributes"].values())
        df_subset = pd.DataFrame(data)
        # df_subset["Class"] = pascal_case(row["unique_id"])
        # set_attributes = row["set_attributes"]
        # df_subset["Default"] = [set_attributes.get(i, None) for i in df_subset["id"]]
        # df_subset["Taxonomy"] = row["taxonomy_id"]
        # df_subset["Parent Class"] = pascal_case(row["parent_unique_id"])
        # df_subset["Property"] = df_subset["name"].apply(lambda x: camel_case(x))
        # df_subset["Source"] = xmlns.replace("{", "").replace("}", "")
        # df_subset["Name"] = df_subset["name"]
        # df_subset["Source Entity Name"] = df_subset["name"]
        # df_subset["Description"] = df_subset["description"]
        # df_subset["dataType"] = df_subset["dataType"].apply(lambda x: _replace_type(x))
        df_lst.append(df_subset)

    df_attributes = pd.concat(df_lst)
    unique_attributes = list(set(df_attributes['Property']))
    df_unique_attributes = _get_unique_attributes(avevaxml, unique_attributes)
    df_attributes = pd.concat([df_attributes, df_unique_attributes])
    # df_attributes["Property"] = df_attributes["name"].apply(lambda x: camel_case(x))
    df_attributes["Source"] = xmlns.replace("{", "").replace("}", "")
    # df_attributes["Name"] = df_attributes["name"] 
    df_attributes["Source Entity Name"] = df_attributes["Name"]
    # df_attributes["Description"] = df_attributes["description"]
    # if 'obsolete' in df_attributes.columns:
    #     df_attributes["Deprecated"] = df_attributes["obsolete"]
    # df_attributes["Type"] = df_attributes["dataType"].apply(lambda x: _replace_type(x))
    df_attributes["Min Count"] = 0
    df_attributes["Max Count"] = 1
   
     
    columns_to_keep = list(parsing_config["header"]) 
    missing_fields = [item for item in columns_to_keep if item not in df_attributes.columns]
    for field in missing_fields:
        df_attributes[field] = ''
    df_attributes = df_attributes[columns_to_keep]
    
    # if dataframe_filter is not None:
    #     filter_lst = list(zip(dataframe_filter.keys(), dataframe_filter.values()))
    #     df2 = pd.DataFrame()
    #     for item in filter_lst:
    #         if df2.empty:
    #             # df2 = df_attributes[(df_attributes[item[0]].isin(item[1]))]
    #             df2 = df_attributes[df_attributes[item[0]].isnull() | df_attributes[item[0]].isin(item[1])]
    #         else:
    #             # df2 = df2[(df2[item[0]].isin(item[1]))]
    #             df2 = df2[df2[item[0]].isnull() | df2[item[0]].isin(item[1])]
                
    #     df_attributes = df2
        
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
