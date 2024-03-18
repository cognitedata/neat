import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { styled } from '@mui/material/styles';
import { SelectChangeEvent } from '@mui/material/Select';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import LinearProgress from '@mui/material/LinearProgress';
import { useState, useEffect } from 'react';
import { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import { WorkflowConfigItem, WorkflowDefinition } from 'types/WorkflowTypes';
import { Dialog, DialogActions, DialogContent, DialogTitle, FormControl, IconButton, List, ListItem, ListItemText, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';

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
  const [dialogOpen, setDialogOpen ] = useState(false);
  const [workflowDefinition, setWorkflowDefinition] = useState<WorkflowDefinition>(new WorkflowDefinition());
  const [workflowConfigItems, setWorkflowConfigItems] = useState<WorkflowConfigItem[]>([]);
  const [selectedConfigItem, setSelectedConfigItem] = useState<WorkflowConfigItem>(new WorkflowConfigItem());

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

  const saveWorkflow = () => {
    let wdef = workflowDefinition;
    wdef.configs = workflowConfigItems;
    const url = neatApiRootUrl+"/api/workflow/workflow-definition/"+workflowName;
    fetch(url,{ method:"post",body:wdef.serializeToJson(),headers: {
        'Content-Type': 'application/json;charset=utf-8'
    }}).then((response) => response.json()).then((data) => {
        window.location.reload();
    }
    ).catch((error) => {
        console.error('Error:', error);
    })
};

const configEditorDialogHandler = (configItem: WorkflowConfigItem,action: string) => {
  console.dir(configItem)
  switch (action) {
    case "save":
      workflowDefinition.upsertConfigItem(configItem);
      break;
    case "delete":
      workflowDefinition.deleteConfigItem(configItem.name)
      break;
  }
  setDialogOpen(false);
}

const openItemEditorDialog = (selectedConfigItem: WorkflowConfigItem) => {
    if (selectedConfigItem) {
      setSelectedConfigItem(selectedConfigItem);
    }else{
      setSelectedConfigItem(new WorkflowConfigItem());
    }
    setDialogOpen(true);
}

  return (
    <Box sx={{ width: 1200 }}>
      <TableContainer component={Paper}>
      <Table sx={{ minWidth: 650 }}  size="small" aria-label="simple table">
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell align="right">Config group</TableCell>
            <TableCell align="right">Value</TableCell>
            <TableCell align="right">Label</TableCell>
            <TableCell align="right">Action</TableCell>

          </TableRow>
        </TableHead>
        <TableBody>
          {workflowConfigItems?.map((row) => (
            <TableRow
              key={row.name}
              sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
            >
              <TableCell component="th" scope="row">
               <b> {row.name} </b>
              </TableCell>
              <TableCell align="right">{row.group}</TableCell>
              <TableCell align="right">{row.value}</TableCell>
              <TableCell align="right">{row.label}</TableCell>
              <TableCell align="right">
              <IconButton aria-label="edit" size="small" onClick={ () => openItemEditorDialog(row) } > <EditIcon fontSize="small" /> </IconButton>
              <IconButton aria-label="delete" size="small" onClick={ ()=> configEditorDialogHandler(row,"delete")}> <DeleteIcon fontSize="small" /> </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

    </TableContainer>
      <Button  variant="outlined" size="small" sx={{marginRight:2,marginTop:2}} onClick={saveWorkflow} >Save</Button>
      <Button variant="outlined" size="small" sx={{marginRight:2,marginTop:2}} onClick={()=>openItemEditorDialog(null)} >Add</Button>
      <ConfigEditorDialog open={dialogOpen} onClose={configEditorDialogHandler} configItem={selectedConfigItem} />
      {loading && (<LinearProgress />)}
    </Box>
  );
}


export function ConfigEditorDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [configItem, setConfigItem] = useState<WorkflowConfigItem>(null);
    const handleDialogSave = () => {
        setDialogOpen(false);
        props.onClose(configItem,"save");
    };
    const handleDialogCancel = () => {
        setDialogOpen(false);
        props.onClose(configItem,"cancel");
    };
    const handleConfigItemChange = (name: string, value: any) => {

        console.dir(configItem);
        let updConfigItem = Object.assign({},configItem);
        updConfigItem[name] = value;

        console.dir(updConfigItem);
        setConfigItem(updConfigItem);
    }
    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            setConfigItem(props.configItem);
            console.dir(props.configItem);
        }
      }, [props.open]);

return (
<Dialog open={dialogOpen} onClose={handleDialogCancel}>
<DialogTitle>Configuration editor</DialogTitle>
<DialogContent >
  <FormControl sx={{ width: 500 }} >
    <TextField sx={{ marginTop: 1 }} id="step-config-id" fullWidth label="Name" size='small' variant="outlined" value={configItem?.name} onChange={(event) => { handleConfigItemChange("name", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Value" size='small' variant="outlined" value={configItem?.value} onChange={(event) => { handleConfigItemChange("value", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-label" fullWidth label="Label" size='small' variant="outlined" value={configItem?.label} onChange={(event) => { handleConfigItemChange("label", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-label" fullWidth label="Config group" size='small' variant="outlined" value={configItem?.group} onChange={(event) => { handleConfigItemChange("group", event.target.value) }} />
  </FormControl>
</DialogContent>
<DialogActions>
  <Button variant="outlined" size="small" onClick={handleDialogSave}>Save</Button>
  <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
</DialogActions>
</Dialog>
)
}
