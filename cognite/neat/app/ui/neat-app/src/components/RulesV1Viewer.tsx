import * as React from 'react';
import {useState,useEffect} from 'react';

import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import { Tab, Tabs } from '@mui/material';

function Row(props: { row: any,properties: any }) {
  const { row,properties } = props;
  const [open, setOpen] = React.useState(false);
  const getPropertyByClass = (className: string) => {
    const r = properties.filter((f: any) => f.class == className);
    return r;
  }
  const [fProps,setFProps] = useState(getPropertyByClass(row.class));

  return (
    <React.Fragment>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell>
          <IconButton
            aria-label="expand row"
            size="small"
            onClick={() => setOpen(!open)}
          >
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell component="th" scope="row">
          {row.class}
        </TableCell>
        <TableCell align="right">{row.class_description}</TableCell>
        <TableCell align="right">{row.cdf_resource_type}</TableCell>
        <TableCell align="right">{row.cdf_parent_resource}</TableCell>
        <TableCell align="center"></TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 1 }}>
              <Typography variant="h6" gutterBottom component="div">
                Properties
              </Typography>
              { fProps != undefined &&(<Table size="small" aria-label="purchases">
                <TableHead>
                  <TableRow>
                    <TableCell><b>Property</b></TableCell>
                    <TableCell><b>Description</b></TableCell>
                    <TableCell><b>Value type</b></TableCell>
                    <TableCell><b>CDF metadata</b></TableCell>
                    <TableCell><b>Rule type</b></TableCell>
                    <TableCell><b>Rule (transform from source to solution object)</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fProps?.map((pr) => (
                    <TableRow key={pr.property}>
                      <TableCell component="th" scope="row"> {pr.property} </TableCell>
                      <TableCell>{pr.property_description}</TableCell>
                      <TableCell>{pr.property_type}</TableCell>
                      <TableCell>{pr.cdf_resource_type}.{pr.cdf_metadata_type}</TableCell>
                      <TableCell>{pr.rule_type}</TableCell>
                      <TableCell>{pr.rule}</TableCell>
                      <TableCell></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table> )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </React.Fragment>
  );
}


export default function RulesV1Viewer(props: any) {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [rules, setRules] = useState({"classes":[],
  "properties":[],
  "metadata":{"prefix":"","suffix":"","namespace":"","version":"","title":"","description":"","created":"","updated":"","creator":[],"contributor":[],"rights":"","license":"","dataModelId":"","source":""}});
  const [selectedTab, setSelectedTab] = useState(1);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
  };
  const columns: GridColDef[] = [
    {field: 'id', headerName: 'ID', width: 70},
    {field: 'name', headerName: 'Name', width: 130},
    {field: 'value', headerName: 'Value', type: 'number', width: 90},
  ];
  useEffect(() => {
    setRules(props.rules)
  }, [props.rules]);
  return (
        <Box>
          <Tabs value={selectedTab} onChange={handleTabChange} aria-label="Metadata tabs">
            <Tab label="Metadata" />
            <Tab label="Data model" />
          </Tabs>

          {selectedTab === 0 && rules.metadata && (
            <Box sx={{marginTop:5}}>
              <TableContainer component={Paper}>
                <Table aria-label="metadata table">
                  <TableBody>
                    <TableRow>
                      <TableCell><b>Title</b></TableCell>
                      <TableCell>{rules.metadata.title}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Description</b></TableCell>
                      <TableCell>{rules.metadata.description}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Prefix and DMS Space</b></TableCell>
                      <TableCell>{rules.metadata.prefix}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Data Model ID</b></TableCell>
                      <TableCell>{rules.metadata.suffix}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Namespace</b></TableCell>
                      <TableCell>{rules.metadata.namespace}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Version</b></TableCell>
                      <TableCell>{rules.metadata.version}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Created</b></TableCell>
                      <TableCell>{rules.metadata.created}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Updated</b></TableCell>
                      <TableCell>{rules.metadata.updated}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Creator</b></TableCell>
                      <TableCell>{rules.metadata.creator.join(", ")}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}
     {selectedTab === 1 && (
        <TableContainer component={Paper}>
          <Table aria-label="collapsible table">
            <TableHead>
              <TableRow>
                <TableCell />
                <TableCell> <b>Class</b></TableCell>
                <TableCell align="right"><b>Description</b></TableCell>
                <TableCell align="right"></TableCell>
                <TableCell align="right"></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.classes?.map((row:any) => (
                <Row key={row.class} row={row} properties={rules.properties} />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
     )}
    </Box>
  );
}
