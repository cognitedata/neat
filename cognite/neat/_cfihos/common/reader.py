import json

import pandas as pd
import yaml


def read_yaml(yaml_file_path: str) -> dict:
    """reads a yaml file and returns it as a dict

    Args:
        yaml_file_path (str): file path to yaml-file

    Returns:
        dict: the yaml-file's content
    """
    with open(yaml_file_path, "r") as f:
        try:
            yaml_file = yaml.safe_load(f)
        except Exception as exc:
            print(exc)
            raise

    f.close()
    return yaml_file


def read_json(fpath: str) -> dict:
    """
    Reads a given json file and returns it as dictionary

    Args:
        fpath (str): path and filename of json file

    Returns:
        dict: diciontary representing json data
    """
    # Opening JSON file
    try:
        f = open(fpath)

        data = json.load(f)

        return data
    except Exception as exc:
        print(exc)
        raise


def read_csv(fpath: str, **kwargs) -> pd.DataFrame:
    """
    Read CSV and load it into a pandas dataframe.

    Args:
        fpath (str): path and filename of csv file.

    Returns:
        pd.DataFrame: dataframe representing csv data.
    """
    try:
        return pd.read_csv(fpath, **kwargs)
    except Exception as exc:
        print(exc)
        raise


def read_excel(fpath: str, **kwargs) -> pd.DataFrame:
    """
    Read Excel and load it into a pandas dataframe.

    Args:
        fpath (str): path and filename of excel file.

    Returns:
        pd.DataFrame: dataframe representing excel sheet data.
    """
    try:
        return pd.read_excel(fpath, **kwargs)
    except Exception as exc:
        print(exc)
        raise
