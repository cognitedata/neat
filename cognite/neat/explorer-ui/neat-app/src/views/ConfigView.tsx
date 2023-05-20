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
import { List, ListItem, ListItemText } from '@mui/material';

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

  const addItem = () => {
    let updConfigs = workflowConfigItems;
    let newItem = new WorkflowConfigItem();
    newItem.name = "new item";
    newItem.value = "new value";
    updConfigs.push(newItem);
    console.dir(updConfigs);
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
    <Box sx={{ width: 800 }}>
      <Stack spacing={2}>
        <Item>
          <h2> Workflow configurations</h2>
          <List>
          {workflowConfigItems?.map((item) => (
          <ListItem>
                <ListItemText primary={item.name} />
                <TextField key={item.name} sx={{width:400}} size='small' variant="outlined" value={item.value} onChange={(event) => { handleWfConfigChange(item.name, event.target.value) }} />
          </ListItem>
          ))}
          </List>
          <Button variant="contained" sx={{marginRight:50}} onClick={saveWorkflow} >Save</Button>
          {loading && (<LinearProgress />)}
        </Item>
      </Stack>
    </Box>
  );
}
