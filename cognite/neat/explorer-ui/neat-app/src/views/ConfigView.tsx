import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import { styled } from '@mui/material/styles';
import { SelectChangeEvent } from '@mui/material/Select';
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
  const [workflowDefinition, setWorkflowDefinition] = useState<WorkflowDefinition>(new WorkflowDefinition());
  const [workflowConfigItems, setWorkflowConfigItems] = useState<WorkflowConfigItem[]>([]);

  const handleGraphSourceNameChange = (event: SelectChangeEvent) => {
    setGraphSourceName(event.target.value as string);
  };
  const [neatApiRootUrl, setNeatApiRootUrl] = useState(getNeatApiRootUrl());

  useEffect(() => {
    loadWorkflowConfigs();
  }, []);


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

      </Stack>
    </Box>
  );
}
