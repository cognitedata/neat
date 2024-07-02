import * as React from 'react';
import { useState, useEffect } from 'react';

import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import { Alert, AlertTitle, Button, Tab, Tabs, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { DMSArchitectContainers, DMSArchitectPropsRow, DMSArchitectRulesViewer, DMSArchitectViews, DmsMetadataTable } from './rules/DmsViewer';
import { DomainExpertRulesViewer } from './rules/DomainViewer';
import { InformationArchitectPropsRow, InformationArchitectRulesViewer, InformationArchitectTransformationRow, InformationMetadataTable } from './rules/InformationViewer';


export default function RulesV2Viewer(props: any) {
  const neatApiRootUrl = getNeatApiRootUrl();
  const newLocal = useState<any>({
    "classes": [],
    "properties": [],
    "views": [],
    "containers": [],
    "metadata": { "prefix": "", "role": "", "extension": "", "schema_": "", "suffix": "", "namespace": "", "version": "", "title": "", "description": "", "created": "", "updated": "", "creator": [], "contributor": [], "rights": "", "license": "", "dataModelId": "", "source": "" },
    "reference": {},
    "last": {}
  });
  const [rules, setRules] = newLocal;
  const [selectedTab, setSelectedTab] = useState(1);
  const [role, setRole] = useState("");
  const [alertMsg, setAlertMsg] = useState("");
  const [modelType, setModelType] = useState("current");
  const [originalRole, setOriginalRole] = useState("");

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'name', headerName: 'Name', width: 130 },
    { field: 'value', headerName: 'Value', type: 'number', width: 90 },
  ];
  const handleRoleChange = (event: React.SyntheticEvent, newValue: string) => {
    if (newValue == null) {
      return;
    }
    if (role == "information architect" && newValue == "domain expert") {
      setAlertMsg("Automatic convertion from Information Architect to Domain Expert is not supported yet ");
      return
    }

    if (role == "domain expert" && (newValue == "information architect" || newValue == "DMS Architect")) {
      setAlertMsg("Automatic convertion  from Domain expert to Information Architect or DMS Architect is not supported yet");
      return
    }

    if (role == "DMS Architect" && newValue == "domain expert") {
      setAlertMsg("Automatic convertion  from DMS Architect to Domain Expert or Information Architect is not supported yet");
      return
    }
    setSelectedTab(0);
    if (newValue == "asset architect") {
      newValue = "information architect";
    }
    setRole(newValue);
    props.onRoleChange(newValue);
  }

  const handleModelTypeChange = (event: React.SyntheticEvent, newValue: string) => {
    if (newValue == null) {
      return;
    }
    if (newValue == "reference" && rules.reference) {
      setRules(rules.reference);
      setModelType(newValue);
    } else if (newValue == "last" && rules.last) {
      setRules(rules.last);
      setModelType(newValue);
    } else if (newValue == "current") {
      setRules(props.rules);
      setModelType(newValue);
    }

  }

  useEffect(() => {
    if (props.rules.metadata.role == "asset architect") {
      setRole("information architect")
    } else {
      setRole(props.rules.metadata.role)
    }
    setRules(props.rules)
  }, [props.rules]);
  useEffect(() => {
    setOriginalRole(props.rules.metadata.role)
  }, []);

  return (
    <Box>
      <ToggleButtonGroup
        color="primary"
        value={role}
        exclusive
        onChange={handleRoleChange}
        aria-label="Platform"
      >
        <ToggleButton value="domain expert">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <img width="70" src="./img/sme-icon.svg" alt="Domain expert" />
            <span>Domain Expert {originalRole != role && role == "domain expert" && ("(PREVIEW)")}</span>
          </div>
        </ToggleButton>
        <ToggleButton value="information architect">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <img width="70" src="./img/architect-icon.svg" alt="Information Architect" />
            <span>Information Architect  {originalRole != role && role == "information architect" && ("(PREVIEW)")}</span>
          </div>
        </ToggleButton>
        <ToggleButton value="DMS Architect">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <img width="70" src="./img/developer-icon.svg" alt="DMS Expert" />
            <span>CDF DM Expert {originalRole != role && role == "DMS Architect" && ("(PREVIEW)")}</span>
          </div>
        </ToggleButton>
      </ToggleButtonGroup>
      {(rules.reference || modelType == "reference" || rules.last || modelType == "last") && (
        <Box sx={{ marginTop: 1 }}>
          <ToggleButtonGroup
            color="primary"
            value={modelType}
            exclusive
            onChange={handleModelTypeChange}
            aria-label="Platform"
            size='small'
          >
            <ToggleButton value="current">
              Current model
            </ToggleButton>
            <ToggleButton value="last">
              Model before new changes
            </ToggleButton>
            <ToggleButton value="reference">
              Reference model
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>)}
      {alertMsg != "" && (<Alert severity="warning" onClose={() => { setAlertMsg("") }}>
        <AlertTitle>Warning</AlertTitle>
        {alertMsg}
      </Alert>)}
      {role == "domain expert" && (
        <DomainExpertRulesViewer rules={rules} fileName={props.fileName} />
      )}
      {role == "information architect" && (
        <InformationArchitectRulesViewer rules={rules} fileName={props.fileName} modelType={modelType} />
      )}
      {role == "DMS Architect" && (
        <DMSArchitectRulesViewer rules={rules} />
      )}
    </Box>
  );
}
