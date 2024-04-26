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
import { DomainExpertRulesViewer, DomainMetadataTable } from './rules/DomainViewer';
import { InformationArchitectPropsRow, InformationArchitectRulesViewer, InformationArchitectTransformationRow, InformationMetadataTable } from './rules/InformationViewer';


export default function RulesV2Viewer(props: any) {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [rules, setRules] = useState({
    "classes": [],
    "properties": [],
    "views": [],
    "containers": [],
    "metadata": { "prefix": "", "role": "", "extension": "", "schema_": "", "suffix": "", "namespace": "", "version": "", "title": "", "description": "", "created": "", "updated": "", "creator": [], "contributor": [], "rights": "", "license": "", "dataModelId": "", "source": "" }
  });
  const [selectedTab, setSelectedTab] = useState(1);
  const [role, setRole] = useState("");
  const [alertMsg, setAlertMsg] = useState("");

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
      setAlertMsg("You cannot change role from Information Architect to Domain Expert");
      return
    }

    if (role == "DMS Architect" && newValue == "domain expert") {
      setAlertMsg("You cannot change role from DMS Architect to Domain Expert or Information Architect");
      return
    }
    setSelectedTab(0);
    setRole(newValue);
    props.onRoleChange(newValue);
  }

  useEffect(() => {
    setRole(props.rules.metadata.role)
    setRules(props.rules)
  }, [props.rules]);
  return (
    <Box>
      <ToggleButtonGroup
        color="primary"
        value={rules.metadata.role}
        exclusive
        onChange={handleRoleChange}
        aria-label="Platform"
      >
        <ToggleButton value="domain expert">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <img width="70" src="./img/sme-icon.svg" alt="Domain expert" />
            <span>Domain Expert</span>
          </div>
        </ToggleButton>
        <ToggleButton value="information architect">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <img width="70" src="./img/architect-icon.svg" alt="Information Architect" />
            <span>Information Architect</span>
          </div>
        </ToggleButton>
        <ToggleButton value="DMS Architect">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <img width="70" src="./img/developer-icon.svg" alt="DMS Expert" />
            <span>CDF DM Expert</span>
          </div>
        </ToggleButton>
      </ToggleButtonGroup>
      {alertMsg != "" && (<Alert severity="warning" onClose={() => { setAlertMsg("") }}>
        <AlertTitle>Warning</AlertTitle>
        {alertMsg}
      </Alert>)}
      {role == "domain expert" && (
        <DomainExpertRulesViewer rules={rules} />
      )}
      {role == "information architect" && (
        <InformationArchitectRulesViewer rules={rules} fileName={props.fileName} />
      )}
      {role == "DMS Architect" && (
        <DMSArchitectRulesViewer rules={rules} />
      )}
    </Box>
  );
}
