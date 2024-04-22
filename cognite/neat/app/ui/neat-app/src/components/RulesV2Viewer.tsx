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
import { Alert, AlertTitle, Button, Tab, Tabs, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { Image } from '@mui/icons-material';
import InformationArchitectDataModelEditor from './RulesV2Editor';

function MetadataTable(props: any) {
  const metadata = props.metadata;
  return (
    <Box sx={{marginTop:5}}>
      <TableContainer component={Paper}>
        <Table aria-label="metadata table">
          <TableBody>
            <TableRow>
              <TableCell><b>Name</b></TableCell>
              <TableCell>{metadata?.name}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Role</b></TableCell>
              <TableCell>{metadata?.role}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Schema state</b></TableCell>
              <TableCell>{metadata?.schema_}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Extension</b></TableCell>
              <TableCell>{metadata?.extension}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Description</b></TableCell>
              <TableCell>{metadata?.description}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>DMS Space</b></TableCell>
              <TableCell>{metadata?.space}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Version</b></TableCell>
              <TableCell>{metadata?.version}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Created at</b></TableCell>
              <TableCell>{metadata?.created}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Updated at</b></TableCell>
              <TableCell>{metadata?.updated}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><b>Creator</b></TableCell>
              <TableCell>{metadata?.creator}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

/*
Class:
{
"class_": "Sourceable",
"name": null,
"description": null,
"parent": null,
"reference": null,
"match_type": null,
"comment": null
},

Property:
{
"class_": "Asset",
"name": null,
"description": null,
"property_": "Systemstatus",
"value_type": "string",
"min_count": 1,
"max_count": 1,
"default": null,
"reference": null,
"match_type": null,
"rule_type": null,
"rule": null,
"comment": null
},
*/

function InformationArchitectPropsRow(props: { row: any,properties: any,onEditClick: any}) {
  const { row,properties } = props;
  const [open, setOpen] = React.useState(false);
  const getPropertyByClass = (className: string) => {
    const r = properties.filter((f: any) => f.class_ == className);
    return r;
  }
  const [fProps,setFProps] = useState(getPropertyByClass(row.class_));
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
          {row.class_}
        </TableCell>
        <TableCell align="right">{row.name}</TableCell>
        <TableCell align="right">{row.description}</TableCell>
        <TableCell align="right">{row.reference}</TableCell>
        <TableCell align="right">{row.match_type}</TableCell>
        <TableCell align="right">{row.comment}</TableCell>
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
                    <TableCell><b>Property Id</b></TableCell>
                    <TableCell><b>Name</b></TableCell>
                    <TableCell><b>Description</b></TableCell>
                    <TableCell><b>Value type</b></TableCell>
                    <TableCell><b>Min count</b></TableCell>
                    <TableCell><b>Max count</b></TableCell>
                    <TableCell><b>Default</b></TableCell>
                    <TableCell><b>Reference</b></TableCell>
                    <TableCell><b>Match type</b></TableCell>
                    <TableCell><b>Comment</b></TableCell>
                    <TableCell><b>Action</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fProps?.map((pr) => (
                    <TableRow key={pr.class_+pr.property_}>
                      <TableCell component="th" scope="row"> {pr.property_} </TableCell>
                      <TableCell>{pr.name}</TableCell>
                      <TableCell>{pr.description}</TableCell>
                      <TableCell>{pr.value_type}</TableCell>
                      <TableCell>{pr.min_count}</TableCell>
                      <TableCell>{pr.max_count}</TableCell>
                      <TableCell>{pr.default}</TableCell>
                      <TableCell>{pr.reference}</TableCell>
                      <TableCell>{pr.match_type}</TableCell>
                      <TableCell>{pr.comment}</TableCell>
                      <TableCell> <Button onClick={()=>{props.onEditClick(pr);}}>Edit</Button> </TableCell>
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
/*
{
"class_": "CurrentLimit",
"name": null,
"description": null,
"property_": "CurrentLimit_value",
"relation": null,
"value_type": "text",
"nullable": false,
"is_list": false,
"default": null,
"reference": null,
"container": "CurrentLimit",
"container_property": "CurrentLimit_value",
"view": "CurrentLimit",
"view_property": "CurrentLimit_value",
"index": null,
"constraint": null
},
*/

function DMSArchitectPropsRow(props: { row: any,properties: any,views: any}) {
  const { row,properties,views } = props;
  const [open, setOpen] = React.useState(false);
  const getPropertyByClass = (className: string) => {
    const r = properties.filter((f: any) => f.class_ == className);
    return r;
  }
  const getViewNameByClassId = (className: string) => {
    const r = views.filter((f: any) => f.class_ == className);
    try {
      return r[0].name;
    } catch (e) {
      return "";
    }
  }
  const [fProps,setFProps] = useState(getPropertyByClass(row.class_));
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
          {row.class_}
        </TableCell>
        <TableCell align="right">{ getViewNameByClassId(row.class_) }</TableCell>
        <TableCell align="right">{row.description}</TableCell>
        <TableCell align="center"></TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 ,minWidth:2000}} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 1 }}>
              <Typography variant="h6" gutterBottom component="div">
                Properties
              </Typography>
              { fProps != undefined &&(<Table size="small" aria-label="purchases">
                <TableHead>
                  <TableRow>
                    <TableCell><b>Property Id</b></TableCell>
                    <TableCell><b>Property name</b></TableCell>
                    <TableCell><b>Description</b></TableCell>
                    <TableCell><b>Value type</b></TableCell>
                    <TableCell><b>Nullable</b></TableCell>
                    <TableCell><b>Is list</b></TableCell>
                    <TableCell><b>Default</b></TableCell>
                    <TableCell><b>Reference</b></TableCell>
                    <TableCell><b>Container</b></TableCell>
                    <TableCell><b>Container property</b></TableCell>
                    <TableCell><b>View</b></TableCell>
                    <TableCell><b>View property</b></TableCell>
                    <TableCell><b>Index</b></TableCell>
                    <TableCell><b>Constraint</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fProps?.map((pr) => (
                    <TableRow key={pr.class_+pr.property_}>
                      <TableCell component="th" scope="row"> {pr.property_} </TableCell>
                      <TableCell>{pr.name}</TableCell>
                      <TableCell>{pr.description}</TableCell>
                      <TableCell>{pr.value_type}</TableCell>
                      <TableCell>{pr.nullable}</TableCell>
                      <TableCell>{pr.is_list}</TableCell>
                      <TableCell>{pr.default}</TableCell>
                      <TableCell>{pr.reference}</TableCell>
                      <TableCell>{pr.container}</TableCell>
                      <TableCell>{pr.container_property}</TableCell>
                      <TableCell>{pr.view}</TableCell>
                      <TableCell>{pr.view_property}</TableCell>
                      <TableCell>{pr.index}</TableCell>
                      <TableCell>{pr.constraint}</TableCell>
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

/*

{
"class_": "CurrentLimit",
"name": null,
"description": null,
"view": "CurrentLimit",
"implements": null,
"reference": null,
"filter_": null,
"in_model": true
},

*/

function DMSArchitectViews(props: { row: any}) {
  const {row} = props;
  const [open, setOpen] = React.useState(false);
  return (
    <React.Fragment>
      <TableContainer component={Paper}>
              { row != undefined &&(<Table size="small" aria-label="purchases">
                <TableHead>
                  <TableRow>
                    <TableCell><b>External Id</b></TableCell>
                    <TableCell><b>Name</b></TableCell>
                    <TableCell><b>Description</b></TableCell>
                    <TableCell><b>View</b></TableCell>
                    <TableCell><b>Implements</b></TableCell>
                    <TableCell><b>Reference</b></TableCell>
                    <TableCell><b>Filter</b></TableCell>
                    <TableCell><b>In model</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {row?.map((pr) => (
                    <TableRow key={pr.class_}>
                      <TableCell component="th" scope="row"> {pr.class_} </TableCell>
                      <TableCell>{pr.name}</TableCell>
                      <TableCell>{pr.description}</TableCell>
                      <TableCell>{pr.view}</TableCell>
                      <TableCell>{pr.implements}</TableCell>
                      <TableCell>{pr.reference}</TableCell>
                      <TableCell>{pr.filter_}</TableCell>
                      <TableCell>{pr.in_model}</TableCell>
                      <TableCell></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table> )}
      </TableContainer>
           
    </React.Fragment>
  );
}

/*
{
"class_": "OperationalLimitSet",
"name": null,
"description": null,
"container": "OperationalLimitSet",
"reference": null,
"constraint": null
},
*/


function DMSArchitectContainers(props: { row: any}) {
  const {row} = props;
  const [open, setOpen] = React.useState(false);
  return (
    <React.Fragment>
      <TableContainer component={Paper}>
              { row != undefined &&(<Table size="small" aria-label="purchases">
                <TableHead>
                  <TableRow>
                    <TableCell><b>External Id</b></TableCell>
                    <TableCell><b>Name</b></TableCell>
                    <TableCell><b>Description</b></TableCell>
                    <TableCell><b>Container</b></TableCell>
                    <TableCell><b>Reference</b></TableCell>
                    <TableCell><b>Constraint</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {row?.map((pr) => (
                    <TableRow key={pr.class_}>
                    <TableCell component="th" scope="row"> {pr.class_} </TableCell>
                    <TableCell>{pr.name}</TableCell>
                    <TableCell>{pr.description}</TableCell>
                    <TableCell>{pr.container}</TableCell>
                    <TableCell>{pr.reference}</TableCell>
                    <TableCell>{pr.constraint}</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                  ))}
                </TableBody>
              </Table> )}
      </TableContainer>
    </React.Fragment>
  );
}

function InformationArchitectTransformationRow(props: { row: any,properties: any }) {
  const { row,properties } = props;
  const [open, setOpen] = React.useState(false);
  const getPropertyByClass = (className: string) => {
    const r = properties.filter((f: any) => f.class_ == className);
    return r;
  }
  const [fProps,setFProps] = useState(getPropertyByClass(row.class_));
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
          {row.class_}
        </TableCell>
        <TableCell align="right">{row.name}</TableCell>
        <TableCell align="right">{row.description}</TableCell>
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
                    <TableCell><b>Value type</b></TableCell>
                    <TableCell><b>Tranformation type</b></TableCell>
                    <TableCell><b>Transformation rule expression</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fProps?.map((pr) => (
                    <TableRow key={pr.property_}>
                      <TableCell component="th" scope="row"> {pr.property_} </TableCell>
                      <TableCell>{pr.value_type}</TableCell>
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


export default function RulesV2Viewer(props: any) {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [rules, setRules] = useState({"classes":[],
  "properties":[],
  "views":[],
  "containers":[],
  "metadata":{"prefix":"","role":"","extension":"","schema_":"","suffix":"","namespace":"","version":"","title":"","description":"","created":"","updated":"","creator":[],"contributor":[],"rights":"","license":"","dataModelId":"","source":""}});
  const [selectedTab, setSelectedTab] = useState(1);
  const [role, setRole] = useState("");
  const [alertMsg, setAlertMsg] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorData, setEditorData] = useState({});

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
  };
  const columns: GridColDef[] = [
    {field: 'id', headerName: 'ID', width: 70},
    {field: 'name', headerName: 'Name', width: 130},
    {field: 'value', headerName: 'Value', type: 'number', width: 90},
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

  const getListOfClassesFromProperties = (properties: any) => {
    const classes = properties.map((p: any) => p.class_);
    const uniqueClasses = [...new Set(classes)];
    const classesObjects = uniqueClasses.map((c: any) => {
      return {"class_":c,"description":"","name":"","parent":""};
    }
    );
    return classesObjects;
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
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
                <img width="70" src="./img/architect-icon.svg" alt="Information Architect"  />
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
          <Tabs value={selectedTab} onChange={handleTabChange} aria-label="Metadata tabs">
            <Tab label="Metadata" />
            <Tab label="Data model" />
            { role ==  "information architect" && ( <Tab label="Transformations" /> ) }
            { role ==  "DMS Architect" && ( <Tab label="CDF DM Views" /> ) }
            { role ==  "DMS Architect" && ( <Tab label="CDF DM Containers" /> ) }
          </Tabs>
          {alertMsg != "" && (<Alert severity="warning" onClose={() => { setAlertMsg("")}}>
            <AlertTitle>Warning</AlertTitle>
              {alertMsg}
          </Alert> )}     
          {selectedTab === 0 && rules.metadata && (
          <MetadataTable metadata={rules.metadata} />
          )}
          
     {selectedTab == 1 && role == "information architect" && (
        <TableContainer component={Paper}>
          <InformationArchitectDataModelEditor data={editorData} open={editorOpen} onClose={() => {setEditorOpen(false)}} />
          <Table aria-label="collapsible table">
            <TableHead>
              <TableRow>
                <TableCell />
                <TableCell> <b>Class Id</b></TableCell>
                <TableCell align="right"><b>Name</b></TableCell>
                <TableCell align="right"><b>Description</b></TableCell>
                <TableCell align="right">Reference</TableCell>
                <TableCell align="right">Match type</TableCell>
                <TableCell align="right">Comment</TableCell>
                <TableCell align="right"></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.classes?.map((row:any) => (
                <InformationArchitectPropsRow key={row.class} row={row} properties={rules.properties} onEditClick={(data)=>{setEditorOpen(true);setEditorData(data) }} />
              ))}
            </TableBody>
          </Table>
          <Button variant="outlined" size="small" color="success" style={{margin:5}}  onClick={() => setEditorOpen(true)}>Add</Button>
        </TableContainer>
     )}
      {selectedTab == 2 && role == "information architect" && (
        <TableContainer component={Paper}>
          <Table aria-label="collapsible table">
            <TableHead>
              <TableRow>
                <TableCell />
                <TableCell> <b>Class Id</b></TableCell>
                <TableCell align="right"><b>Name</b></TableCell>
                <TableCell align="right"><b>Description</b></TableCell>
                <TableCell align="right">Reference</TableCell>
                <TableCell align="right">Match type</TableCell>
                <TableCell align="right">Comment</TableCell>
                <TableCell align="right"></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.classes?.map((row:any) => (
                <InformationArchitectTransformationRow key={row.class} row={row} properties={rules.properties} />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
     )}
      {selectedTab == 1 && role == "DMS Architect" && (
        <TableContainer component={Paper}>
          <Table aria-label="collapsible table">
            <TableHead>
              <TableRow>
                <TableCell />
                <TableCell> <b>Class Id</b></TableCell>
                <TableCell align="right"><b>Name</b></TableCell>
                <TableCell align="right"><b>Description</b></TableCell>
                <TableCell align="right"></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {getListOfClassesFromProperties(rules.properties)?.map((row:any) => (
                <DMSArchitectPropsRow key={row.class} row={row} properties={rules.properties} views={rules.views} />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
     )}
     {selectedTab == 2 && role == "DMS Architect" && (
        <DMSArchitectViews row={rules.views} />
     )}
     {selectedTab == 3 && role == "DMS Architect" && (
        <DMSArchitectContainers row={rules.containers} />
      )}
    </Box>
  );
}
