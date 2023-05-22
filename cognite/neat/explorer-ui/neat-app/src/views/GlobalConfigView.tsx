import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import { styled } from '@mui/material/styles';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import LinearProgress from '@mui/material/LinearProgress';
import { useState, useEffect } from 'react';
import { getNeatApiRootUrl } from 'components/Utils';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';

const Item = styled(Paper)(({ theme }) => ({
  backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
  ...theme.typography.body2,
  padding: theme.spacing(1),
  textAlign: 'left',
  color: theme.palette.text.secondary,
}));

export default function GlobalConfigView() {
  const [loading, setLoading] = React.useState(false);
  const [configs, setConfigs] = React.useState({
    "data_store_path": "",
    "cdf_client": {
      "project": "",
      "client_id": "",
      "client_name": "neat",
      "base_url": "https://az-power-no-northeurope.cognitedata.com",
      "scopes": [
        "https://az-power-no-northeurope.cognitedata.com/.default"
      ],
      "token_url": "",
      "client_secret": ""
    },
    "cdf_default_dataset_id": 0,
    "load_examples": true,
    "download_workflows_from_cdf": false,
    "workflow_downloader_filter": "",
    "log_level": "DEBUG",
    "log_format": "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    "stop_on_error": false
  });
  
  let initCdfResourcesResult:string = "";

  const [neatApiRootUrl, setNeatApiRootUrl] = useState(getNeatApiRootUrl());

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = () => {
    const url = neatApiRootUrl+"/api/configs/global";
    fetch(url).then((response) => response.json()).then((data) => {
      console.dir(data)
      setConfigs(data)
    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { setLoading(false); });
  }


  const saveConfigButtonHandler = () => {
    console.dir(configs);
    setLoading(true);
    let url = neatApiRootUrl+"/api/configs/global";

    fetch(url, {
      method: "post", body: JSON.stringify(configs), headers: {
        'Content-Type': 'application/json;charset=utf-8'
      }
    }).then((response) => response.json()).then((data) => {
      console.dir(data)
    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { setLoading(false); });
  }

  const saveNeatApiConfigButtonHandler = () => {
    localStorage.setItem("neatApiRootUrl", neatApiRootUrl);
  }

  const handleConfigChange = (name, value) => {
    if (name == "neatApiRootUrl") {
      setNeatApiRootUrl(value);
    }else {
      setConfigs({ ...configs, [name]: value });
    }
  };
  const handleCdfConfigChange = (name, value) => {
    let new_config  = {...configs};
    new_config.cdf_client[name] = value;
    setConfigs(new_config);
  };

  const initCdfResources = () => {
    setLoading(true);
    let url = neatApiRootUrl+"/api/cdf/init-neat-resources";
    // send post request 
    fetch(url, {
      method: "post"})
      .then((response) => response.json())
      .then((data) => {
        console.dir(data)
        initCdfResourcesResult = data.result;
      }).catch((error) => {
        console.error('Error:', error);
        initCdfResourcesResult = "Error: "+error;
      }).finally(() => { setLoading(false); });
  }

  return (
    <Box sx={{ width: "70%" }}>
      <Stack spacing={2}>
        <Item>
          <h3>Global Configuration</h3>
          <Box sx={{ minWidth: 200 }}>
            <Stack spacing={2} direction="column">
              <h3>CDF configuration</h3>
              <TextField id="project_name" label="Project name" size='small' variant="outlined" value={configs.cdf_client.project} onChange={(event) => { handleCdfConfigChange("project", event.target.value) }} />
              <TextField id="client_id" label="Client id" size='small' variant="outlined" value={configs.cdf_client.client_id} onChange={(event) => { handleCdfConfigChange("client_id", event.target.value) }} />
              <TextField id="client_secret" label="Client secret" type="password" size='small' variant="outlined" value={configs.cdf_client.client_secret} onChange={(event) => { handleCdfConfigChange("client_secret", event.target.value) }} />
              <TextField id="client_name" label="Client name" size='small' variant="outlined" value={configs.cdf_client.client_name} onChange={(event) => { handleCdfConfigChange("client_name", event.target.value) }} />
              <TextField id="cdf_api_base_url" label="CDF api base url" size='small' variant="outlined" value={configs.cdf_client.base_url} onChange={(event) => { handleCdfConfigChange("base_url", event.target.value) }} />
              <TextField id="scopes" label="Scopes" size='small' variant="outlined" value={configs.cdf_client.scopes} onChange={(event) => { handleCdfConfigChange("scopes", event.target.value) }} />
              <TextField id="oidc_token_url" label="OIDC token url" size='small' variant="outlined" value={configs.cdf_client.token_url} onChange={(event) => { handleCdfConfigChange("token_url", event.target.value) }} />
              <TextField id="cdf_default_dataset_id" type="number"  label="Default CDF dataset id.The dataset is used as workflow and rules storage." size='small' variant="outlined" value={configs.cdf_default_dataset_id} onChange={(event) => { handleConfigChange("cdf_default_dataset_id", event.target.value) }} />
              <h3>Storage and workflows</h3>
              <TextField id="data_store_path" label="Data directory.Is used as local workflow , rules and db storage." size='small' variant="outlined" value={configs.data_store_path} onChange={(event) => { handleConfigChange("data_store_path", event.target.value) }} />
              <FormControlLabel control={<Switch checked={configs.download_workflows_from_cdf} onChange={(event) => { handleConfigChange("download_workflows_from_cdf", event.target.checked) }} />} label="Automatically download workflows from CDF on startup"  />
              <TextField id="workflow_downloader_filter" label="List of workflows or filters that will be used for downloading workflows" size='small' variant="outlined" value={configs.workflow_downloader_filter} onChange={(event) => { handleConfigChange("workflow_downloader_filter", event.target.value) }} />
              <FormControlLabel control={<Switch checked={configs.load_examples} onChange={(event) => { handleConfigChange("load_examples", event.target.checked) }} />} label="Load default examples"  />
              <TextField id="log_level" label="Log level" size='small' variant="outlined" value={configs.log_level} onChange={(event) => { handleConfigChange("log_level", event.target.value) }} />
              <Button variant="contained" onClick={saveConfigButtonHandler}>Save</Button>
              {loading && (<LinearProgress />)}
            </Stack>
          </Box>
          <h3>NEAT UI configuration</h3>
          <Box sx={{ minWidth: 120 }}>
            <Stack spacing={2} direction="column">
              <TextField id="neat_api_root_url" label="API root url" size='small' variant="outlined" value={neatApiRootUrl} onChange={(event) => { handleConfigChange("neatApiRootUrl", event.target.value) }} />
              <Button variant="contained" onClick={saveNeatApiConfigButtonHandler}>Save</Button>
            </Stack>
          </Box>
          <h3> CDF resources</h3>
          
          <Button variant="contained" onClick={initCdfResources}>Init CDF resources</Button>
          
        </Item>

      </Stack>
    </Box>
  );
}
