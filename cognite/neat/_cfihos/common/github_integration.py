# import base64
# import io
# import os
# from dataclasses import dataclass
# from pathlib import Path

# import pandas as pd
# from github import Auth, Github, GithubException, GithubIntegration
# from github.ContentFile import ContentFile

# from RIWB.Pipelines.constants import (
#     GITHUB_APP_ID_KEY,
#     GITHUB_APP_PRIVATE_KEY,
#     GITHUB_MAIN_BRANCH,
#     GITHUB_ORGANIZATION,
#     GITHUB_REPOSITORY,
# )

# gh_client: "GithubClient" = None


# @dataclass
# class GithubClient:
#     """Simple wrapper on PyGithub's Github, Organization and Repository objects.
#     Our only concern revolves around retrieving files from Github,
#     thus this GithubClient class is an over-simplification on the otherwise complicated python package.

#     PyGithub documentation: https://pygithub.readthedocs.io/en/stable/index.html
#     """

#     organization_name: str
#     repository_name: str

#     def __post_init__(self):
#         """
#         Authenticate to the GitHub App using its Application ID and Private Key.
#         Obtain the GitHub App installation, and create a GitHub client for that installation.
#         - https://pygithub.readthedocs.io/en/stable/examples/Authentication.html#app-authentication

#         get organization object specified by the provided `organization_name`,
#         get repository object specified by the provided `repository_name`.
#         """

#         auth = Auth.AppAuth(
#             app_id=os.environ[GITHUB_APP_ID_KEY],
#             private_key=f"-----BEGIN RSA PRIVATE KEY-----\n{os.environ[GITHUB_APP_PRIVATE_KEY]}\n-----END RSA PRIVATE KEY-----",
#         )
#         gi = GithubIntegration(auth=auth)

#         try:
#             installation = gi.get_repo_installation(owner=self.organization_name, repo=self.repository_name)
#         except GithubException as ge:
#             raise ValueError(f"Could not find installation for {self.organization_name}/{self.repository_name}") from ge
#         except Exception as e:
#             raise e

#         self.client: Github = installation.get_github_for_installation()
#         self.organization = self.client.get_organization(self.organization_name)
#         self.repository = self.organization.get_repo(self.repository_name)

#     def get_all_files(self) -> dict[str, ContentFile]:
#         """Recursively iterate over the repository and save all files in a dictionary.

#         Returns:
#             dict[str, ContentFile]: dict with file name as key, and its ContentFile as value.
#         """
#         files: dict[str, ContentFile] = {}
#         contents = self.repository.get_contents("")
#         while contents:
#             file_content = contents.pop(0)
#             if file_content.type == "dir":
#                 contents.extend(self.repository.get_contents(file_content.path))
#             else:
#                 files[file_content.name] = file_content
#         return files

#     def get_file(self, file_path: str, ref: str = GITHUB_MAIN_BRANCH) -> ContentFile:
#         """Retrieve a specific file provided by the `file_path` parameter. Optionally, specify a `ref` / branch to retrieve from."""
#         # `get_contents()` does not take Path objects
#         if isinstance(file_path, Path):
#             file_path = str(file_path)
#         _file = self.repository.get_contents(file_path, ref=ref)
#         if _file.size >= 1e6:  # 1MB
#             blob = self.repository.get_git_blob(_file.sha)
#             return blob
#         else:
#             return _file

#     def get_files_from_dir(self, dir_path: str) -> list[ContentFile]:
#         """Retrieve files within a directory, provided by the `dir_path` parameter"""
#         return self.repository.get_contents(dir_path)


# def decode_file_contents(content_file: ContentFile) -> str:
#     """get the decoded string value of the content_file's content."""
#     return base64.b64decode(content_file.content).decode("utf-8")


# def convert_to_dataframe_from_csv(decoded_string: str, sep: str = ";") -> pd.DataFrame:
#     """Convert the decoded_string of a csv to a pandas dataframe.

#     Note: All values retrieved are treated as strings (dtype=str) to avoid weirdness when loading the dataframe.

#     Args:
#         decoded_string (str): the file's content decoded, and loadable into a dataframe.
#         sep (str, optional): separator to split columns on. Defaults to ";".

#     Returns:
#         pd.DataFrame: the CSV loaded into a dataframe.
#     """
#     return pd.read_csv(io.StringIO(decoded_string), sep=sep, dtype=str)


# def read_csv(fpath: str, ref: str = GITHUB_MAIN_BRANCH, **kwargs) -> pd.DataFrame:
#     """Read a csv file from GitHub and return a pandas dataframe.

#     This is a convenience function that wraps the following functions:
#     - `GithubClient.get_file`
#     - `decode_file_contents`
#     - `pd.read_csv`

#     Created to simplify the usage of loading CSVs from GitHub, while also mimicing the `pd.read_csv` function.

#     Creates its own GitHubClient instance, and thus does not require the user to create one. Facilitates more loosely coupled code.

#     Args:
#         fpath (str): relative path to the file in the GitHub repository.

#     Returns:
#         pd.DataFrame: pandas dataframe of the csv file.
#     """
#     global gh_client
#     if not gh_client:
#         gh_client = GithubClient(organization_name=GITHUB_ORGANIZATION, repository_name=GITHUB_REPOSITORY)
#     file_content = gh_client.get_file(fpath, ref)
#     decoded_file_content = decode_file_contents(file_content)
#     return pd.read_csv(io.StringIO(decoded_file_content), **kwargs)


# if __name__ == "__main__":
#     # sample usage
#     github_client = GithubClient(organization_name="aker-information-model", repository_name="epc-domain-model")

#     # sample retrieving one specific file
#     # copied relative path directly from GitHub
#     _file = github_client.get_file(
#         "common/Domain Model EPC/Container Model EPC/Mapping/comos_object_eng_id_to_domain_model.csv"
#     )
#     decoded_csv = decode_file_contents(_file)
#     df = convert_to_dataframe_from_csv(decoded_csv)
#     print(df.head(10))

#     # sample retrieving all files within a folder
#     folder_name = "Yggdrasil/Domain Model EPC/Container Model EPC/use case definition material"
#     gh_folder = github_client.get_files_from_dir(folder_name)
#     # load all the CSV (and excel) files into a dictionary with the file name as keys
#     dfs = {}
#     for content_file in gh_folder:
#         if content_file.name.endswith(".xlsx"):
#             # for excel files, we can use the ContentFile's decoded_content, as read_excel also accepts bytes input
#             # dfs[content_file.name] = pd.read_excel(content_file.decoded_content)

#             # alternatively we can read the excel file into an ExcelFile, then load each sheet into a dataframe from there.
#             dfs[content_file.name] = {}
#             excel = pd.ExcelFile(content_file.decoded_content)
#             for sheet_name in excel.sheet_names:
#                 dfs[content_file.name][sheet_name] = pd.read_excel(excel, sheet_name=sheet_name)
#         elif content_file.name.endswith(".csv"):
#             decoded_contents = decode_file_contents(content_file)
#             dfs[content_file.name] = convert_to_dataframe_from_csv(decoded_contents, sep=",")

#     print(df.head(10))
#     for name, frame in dfs.items():
#         if isinstance(frame, dict):
#             for _name, sub_frame in frame.items():
#                 print(_name, "\n", sub_frame, "\n")
#         else:
#             print(name, "\n", frame, "\n")
