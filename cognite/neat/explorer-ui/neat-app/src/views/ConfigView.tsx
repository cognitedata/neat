import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import { styled } from '@mui/material/styles';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import LinearProgress from '@mui/material/LinearProgress';
import { useState, useEffect } from 'react';
import { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import { WorkflowConfigItem, WorkflowDefinition } from 'types/WorkflowTypes';

const Item = styled(Paper)(({ theme }) => ({
  backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
  ...theme.typography.body2,
  padding: theme.spacing(1),
  textAlign: 'left',
  color: theme.palette.text.secondary,
}));

export default function ConfigView() {
  const [graphSourceName, setGraphSourceName] = React.useState('');
  const [workflowName, setWorkflowName] = React.useState(getSelectedWorkflowName());
  const [loading, setLoading] = React.useState(false);
  const [configs, setConfigs] = React.useState({
    "rules_store_type": "file",
    "rules_store_path": "",
    "workflows_store_path": "",
    "workflows_store_type": "file",
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
    "cdf_default_dataset_id": null,
    "log_level": "DEBUG",
    "log_format": "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    "stop_on_error": false
  });
  const [workflowDefinition, setWorkflowDefinition] = useState<WorkflowDefinition>(new WorkflowDefinition());
  const [workflowConfigItems, setWorkflowConfigItems] = useState<WorkflowConfigItem[]>([]);

  const handleGraphSourceNameChange = (event: SelectChangeEvent) => {
    setGraphSourceName(event.target.value as string);
  };
  // const neatApiRootUrl = getNeatApiRootUrl();
  const [neatApiRootUrl, setNeatApiRootUrl] = useState(getNeatApiRootUrl());

  useEffect(() => {
    loadConfigs();
    loadWorkflowConfigs();
  }, []);

  const loadConfigs = () => {
    const url = neatApiRootUrl+"/api/configs";
    fetch(url).then((response) => response.json()).then((data) => {
      console.dir(data)
      setConfigs(data)
    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { setLoading(false); });
  }

  const loadWorkflowConfigs = () => {
    const workflowName = getSelectedWorkflowName();
    const url = neatApiRootUrl+"/api/workflow/workflow-definition/" + workflowName;
    fetch(url).then((response) => response.json()).then((data) => {
      const workflow = WorkflowDefinition.fromJSON(data.definition);
      setWorkflowDefinition(workflow);
      setWorkflowConfigItems(workflow.configs);

    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { });
  }


  const saveConfigButtonHandler = () => {
    console.dir(configs);
    setLoading(true);
    let url = neatApiRootUrl+"/api/configs";

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

  const handleWfConfigChange = (name, value) => {
    console.log("handleWfConfigChange", name, value);
    let updConfigs = workflowConfigItems.map((item: WorkflowConfigItem) => {
      if (item.name === name) {
        item.value = value;
      }
      return item;
    });
    setWorkflowConfigItems(updConfigs);
  };

  const saveWorkflow = () => {
    let wdef = workflowDefinition;
    wdef.configs = workflowConfigItems;
    const url = neatApiRootUrl+"/api/workflow/workflow-definition/"+workflowName;
    fetch(url,{ method:"post",body:wdef.serializeToJson(),headers: {
        'Content-Type': 'application/json;charset=utf-8'
    }}).then((response) => response.json()).then((data) => {
        console.dir(data)
    }
    ).catch((error) => {
        console.error('Error:', error);
    })
};

  return (
    <Box sx={{ width: 500 }}>
      <Stack spacing={2}>
        <Item>
          <h2> Workflow configurations ({workflowName})</h2>
          <Box sx={{ minWidth: 120 }}>
            <Stack spacing={2} direction="column">
              {workflowConfigItems?.map((item) => (
                     <TextField key={item.name} label={item.name} size='small' variant="outlined" value={item.value} onChange={(event) => { handleWfConfigChange(item.name, event.target.value) }} />
              ))}
              <Button variant="contained" onClick={saveWorkflow}>Save</Button>
              {loading && (<LinearProgress />)}
            </Stack>
          </Box>
        </Item>


        <Item>
          <h2>Global Configuration</h2>
          <Box sx={{ minWidth: 120 }}>
            <Stack spacing={2} direction="column">
              <h3>CDF</h3>
              <TextField id="project_name" label="Project name" size='small' variant="outlined" value={configs.cdf_client.project} onChange={(event) => { handleConfigChange("rdf_store_query_url", event.target.value) }} />
              <TextField id="client_id" label="Client id" size='small' variant="outlined" value={configs.cdf_client.client_id} onChange={(event) => { handleConfigChange("rdf_store_update_url", event.target.value) }} />
              <TextField id="client_secret" label="Client secret" type="password" size='small' variant="outlined" value={configs.cdf_client.client_secret} onChange={(event) => { handleConfigChange("rdf_store_update_url", event.target.value) }} />
              <TextField id="client_name" label="Client name" size='small' variant="outlined" value={configs.cdf_client.client_name} onChange={(event) => { handleConfigChange("rdf_store_update_url", event.target.value) }} />
              <TextField id="cdf_api_base_url" label="CDF api base url" size='small' variant="outlined" value={configs.cdf_client.base_url} onChange={(event) => { handleConfigChange("rdf_store_update_url", event.target.value) }} />
              <TextField id="scopes" label="Scopes" size='small' variant="outlined" value={configs.cdf_client.scopes} onChange={(event) => { handleConfigChange("rdf_store_update_url", event.target.value) }} />
              <TextField id="oidc_token_url" label="OIDC token url" size='small' variant="outlined" value={configs.cdf_client.token_url} onChange={(event) => { handleConfigChange("rdf_store_update_url", event.target.value) }} />
              <TextField id="cdf_default_dataset_id" label="Default CDF dataset id" size='small' variant="outlined" value={configs.cdf_default_dataset_id} onChange={(event) => { handleConfigChange("rules_store_path", event.target.value) }} />
              <h3>Data stores</h3>
              <TextField id="workflows_store_path" label="Workflow storage" size='small' variant="outlined" value={configs.workflows_store_path} onChange={(event) => { handleConfigChange("workflows_store_path", event.target.value) }} />
              <TextField id="rules_store_path" label="Rules storage" size='small' variant="outlined" value={configs.rules_store_path} onChange={(event) => { handleConfigChange("rules_store_path", event.target.value) }} />

              <Button variant="contained" onClick={saveConfigButtonHandler}>Save</Button>
              {loading && (<LinearProgress />)}
            </Stack>
          </Box>
          <h2>NEAT UI configuration</h2>
          <Box sx={{ minWidth: 120 }}>
            <Stack spacing={2} direction="column">
              <TextField id="neat_api_root_url" label="API root url" size='small' variant="outlined" value={neatApiRootUrl} onChange={(event) => { handleConfigChange("neatApiRootUrl", event.target.value) }} />
              <Button variant="contained" onClick={saveNeatApiConfigButtonHandler}>Save</Button>
            </Stack>
          </Box>
        </Item>

      </Stack>
    </Box>
  );
}
