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
import Button from '@mui/material/Button';
import { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import FileUpload from 'react-mui-fileuploader';
import { margin } from '@mui/system';
import CdfPublisher from 'components/CdfPublisher';
import LocalUploader from 'components/LocalUploader';
import Container from '@mui/material/Container';
import CdfDownloader from 'components/CdfDownloader';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import { Tab, Tabs } from '@mui/material';
import RulesBrowserDialog from 'components/RulesBrowserDialog';

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


export default function TransformationTable() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [data, setData] = useState({"classes":[],"properties":[],"file_name":"","hash":"","error_text":"","src":"",
  "metadata":{"prefix":"","suffix":"","namespace":"","version":"","title":"","description":"","created":"","updated":"","creator":[],"contributor":[],"rights":"","license":"","dataModelId":"","source":""}});
  const [alertMsg, setAlertMsg] = useState("");
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>(getSelectedWorkflowName());
  const [selectedTab, setSelectedTab] = useState(1);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
  };
  const columns: GridColDef[] = [
    {field: 'id', headerName: 'ID', width: 70},
    {field: 'name', headerName: 'Name', width: 130},
    {field: 'value', headerName: 'Value', type: 'number', width: 90},
  ];
  const downloadUrl = neatApiRootUrl+"/data/rules/"+data.file_name+"?version="+data.hash;
  useEffect(() => {
    loadDataset("","");
  }, []);

  const loadDataset = (fileName:string,fileHash:string) => {
    let url = neatApiRootUrl+"/api/rules?"+new URLSearchParams({"workflow_name":selectedWorkflow,"file_name":fileName,"version":fileHash}).toString()
    fetch(url)
    .then((response) => {
      return response.json();
    }).then((data) => {

      setAlertMsg("");
      if (data.classes)
        setData(data)
      else
        setAlertMsg("Rules file "+fileName+" is either invalid or missing. Please ensure that you have a valid Rules file.");
    }).catch((err) => {

      setAlertMsg("Rules file "+fileName+" is either invalid or missing. Please ensure that you have a valid Rules file.");
    }
  )}

  const loadArbitraryRulesFile = (fileName:string) => {
    let url = neatApiRootUrl+"/api/rules?"+new URLSearchParams({"workflow_name":"undefined","file_name":fileName,"version":""}).toString()
    fetch(url)
    .then((response) => {
      return response.json();
    }).then((data) => {
      setAlertMsg("");
      setData(data);
    }).catch((err) => {

      setAlertMsg("Rules file "+fileName+" is either invalid or missing. Please ensure that you have a valid Rules file.");
    }
  )}



  const [filesToUpload, setFilesToUpload] = useState([])

  const onUpload = (fileName:string , hash: string) => {

    loadDataset(fileName,hash);
  }

  const onDownloadSuccess = (fileName:string , hash: string) => {

    loadDataset(fileName,hash);
  }

  return (
    <Box>
    <Typography variant="subtitle1" gutterBottom>
        Data model (rules) : <a href={downloadUrl} >{data.file_name}</a>  version : {data.hash} source: {data.src} <RulesBrowserDialog onSelectRule={loadArbitraryRulesFile} />
        {data.error_text && <Container sx={{ color: 'red' }}>{data.error_text}</Container>}
    </Typography>
    {alertMsg != "" && (<Alert severity="warning">
      <AlertTitle>Warning</AlertTitle>
        {alertMsg}
    </Alert> )}
        <Box>
          <Tabs value={selectedTab} onChange={handleTabChange} aria-label="Metadata tabs">
            <Tab label="Metadata" />
            <Tab label="Data model" />
          </Tabs>

          {selectedTab === 0 && data.metadata && (
            <Box sx={{marginTop:5}}>
              <TableContainer component={Paper}>
                <Table aria-label="metadata table">
                  <TableBody>
                    <TableRow>
                      <TableCell><b>Title</b></TableCell>
                      <TableCell>{data.metadata.title}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Description</b></TableCell>
                      <TableCell>{data.metadata.description}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Prefix and DMS Space</b></TableCell>
                      <TableCell>{data.metadata.prefix}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Data Model ID</b></TableCell>
                      <TableCell>{data.metadata.suffix}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Namespace</b></TableCell>
                      <TableCell>{data.metadata.namespace}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Version</b></TableCell>
                      <TableCell>{data.metadata.version}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Created</b></TableCell>
                      <TableCell>{data.metadata.created}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Updated</b></TableCell>
                      <TableCell>{data.metadata.updated}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell><b>Creator</b></TableCell>
                      <TableCell>{data.metadata.creator.join(", ")}</TableCell>
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
                {/* <TableCell align="right"><b>CDF resource</b></TableCell> */}
                <TableCell align="right"></TableCell>
                <TableCell align="right"></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.classes?.map((row:any) => (
                <Row key={row.class} row={row} properties={data.properties} />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
     )}
   </Box>
    <Box sx={{margin:5}}>
      <Box sx={{width : 500}}>
      <LocalUploader fileType="rules" action="none" stepId="none" label="Upload new data model" workflowName={selectedWorkflow} onUpload={onUpload} />
      </Box>
      <CdfPublisher type="transformation rules" fileName={data.file_name} />
      <CdfDownloader type="neat-wf-rules" onDownloadSuccess={onDownloadSuccess} />
    </Box>


    </Box>
  );
}
