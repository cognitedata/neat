# Installation

`neat` is distributed as a Python package. It is intended to be used in a notebook environment such as, for example, 
Jupyter Notebooks. Another notebook environment is the CDF notebooks.

## CDF Notebooks Environment

CDF Notebooks are a part of the Cognite Data Fusion (CDF) platform. These notebooks are a great way to get started with
`neat`, even if you have **no coding experience**.

!!! note "Limitations"

    CDF Notebooks are running in your browser. This have some limitations compared to running `neat` locally. The
    main difference is that locally neat can use a more powerful storge backend. This means that if you are working
    with large amounts of metadata, you might want to consider running `neat` locally.

1. Go to [Cognite Data Fusion](https://fusion.cogniteapp.com/)
2. Login to your account
3. Ensure you have selected the `Data Management` workspace.
4. Select `Build solutions` in your left menubar. 
5. Click on `Jupyter Notebooks` under the expanded `Build solutions` menu.
6. Launch a new notebook.
7. Install `cognite-neat` by running `%pip install cognite-neat` in a cell.
8. Import `NeatSession` and `CogniteClient` and start using it as shown below

```python
from cognite.client import CogniteClient
from cognite.neat import NeatSession

client = CogniteClient()

neat = NeatSession(client)

# Start using neat by typing neat.<TAB>
```

## Local Notebook Environment
Running `neat` locally requires a Python environment as well as a notebook environment. The following steps will 
guide youy through the installation process using [Jupyter Lab](https://jupyter.org/install) as the notebook environment.

**Prerequisites**: Installed Python 3.10 or later, see [python.org](https://www.python.org/downloads/)

1. Create and enter directory for `neat` installation
1. Create a virtual environment:
2. Activate your virtual environment
3. Install `cognite-neat`
4. Install a notebook environment, `pip install jupyterlab`
5. Start your notebook environment, `jupyter lab`
6. Import `NeatSession` and `get_cognite_client` and start using it

=== "Windows"

    ```
    mkdir neat && cd neat
    ```
    ```
    python -m venv venv
    ```
    ```
    venv\Scripts\activate.bat
    ```
    ```
    pip install cognite-neat
    ```
    ```
    pip install pip install jupyterlab
    ```
    ```
    jupyter lab
    ```

=== "Mac/Linux"

    ```bash
    mkdir neat && cd neat
    ```
    ```bash
    python -m venv venv
    ```
    ```bash
    source venv/bin/activate
    ```
    ```bash
    pip install cognite-neat
    ```
    ```bash
    pip install pip install jupyterlab
    ```
    ```bash
    jupyter lab
    ```

In a notebook cell, you can now import `NeatSession` and `get_cognite_client` and start using it as shown below

```python
from cognite.neat import NeatSession, get_cognite_client

client = get_cognite_client(".env")

neat = NeatSession(client)

# Start using neat by typing neat.<TAB>
```

!!! tip "Helper get_cognite_client function"

    The `get_cognite_client` function is a helper function that reads the environment variables from a `.env` file
    and creates a `CogniteClient` instance. This is a common pattern when working with Cognite Data Fusio through
    Python. Note that if you dont' have a `.env` file, it will prompt you to enter environment variables
    interactively and offer to save them to a `.env` file. You can instantiate a `CogniteClient` instance directly
    if you prefer.
