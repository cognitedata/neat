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

function Row(props: { row: any,properties: any }) {
  const { row,properties } = props;
  const [open, setOpen] = React.useState(false);
  const getPropertyByClass = (className: string) => {
    const r = properties.filter((f: any) => f.class == className);
    return r;
  }
  const [fProps,setFProps] = useState(getPropertyByClass(row.class));

  console.log("row = ",row.class);

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
        <TableCell align="center"><Button >test</Button></TableCell>
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
                    <TableCell><b>Action</b></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fProps.map((pr) => (
                    <TableRow key={pr.property}>
                      <TableCell component="th" scope="row"> {pr.property} </TableCell>
                      <TableCell>{pr.property_description}</TableCell>
                      <TableCell>{pr.property_type}</TableCell>
                      <TableCell>{pr.cdf_resource_type}.{pr.cdf_metadata_type}</TableCell>
                      <TableCell>{pr.rule_type}</TableCell>
                      <TableCell>{pr.rule}</TableCell>
                      <TableCell><Button >test</Button></TableCell>
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
  const [data, setData] = useState({"classes":[],"properties":[],"file_name":"","hash":"","error_text":"","src":""});
  const [alertMsg, setAlertMsg] = useState("");
  const columns: GridColDef[] = [
    {field: 'id', headerName: 'ID', width: 70},
    {field: 'name', headerName: 'Name', width: 130},
    {field: 'value', headerName: 'Value', type: 'number', width: 90},
  ];

  useEffect(() => {
    loadDataset("","");
  }, []);

  const loadDataset = (fileName:string,fileHash:string) => {
    const workflowName = getSelectedWorkflowName();
    let url = neatApiRootUrl+"/api/rules?"+new URLSearchParams({"workflow_name":workflowName,"file_name":fileName,"version":fileHash}).toString()
    fetch(url)
    .then((response) => {
      return response.json();
    }).then((data) => {
      // console.log(text);
      setAlertMsg("");
      setData(data);
    }).catch((err) => {
      console.log(err);
      setAlertMsg("Transformation rules file "+fileName+" is either invalid or missing. Please ensure that you have a valid data model and the necessary transformation rules file in place.");
    }
  )}

  const [filesToUpload, setFilesToUpload] = useState([])

  const onUpload = (fileName:string , hash: string) => {
    console.log("onUpload",fileName,hash)
    loadDataset(fileName,hash);
  }

  const onDownloadSuccess = (fileName:string , hash: string) => {
    console.log("onDownloadSuccess",fileName,hash)
    loadDataset(fileName,hash);
  }

  return (
    <Box>
    <Typography variant="subtitle1" gutterBottom>
        Rules file : {data.file_name}  version : {data.hash} source: {data.src}
        {data.error_text && <Container sx={{ color: 'red' }}>{data.error_text}</Container>}
    </Typography>
    {alertMsg != "" && (<Alert severity="warning">
      <AlertTitle>Warning</AlertTitle>
        {alertMsg} 
    </Alert> )}
    <TableContainer component={Paper}>
      <Table aria-label="collapsible table">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell> <b>Solution class</b></TableCell>
            <TableCell align="right"><b>Description</b></TableCell>
            <TableCell align="right"><b>CDF resource</b></TableCell>
            <TableCell align="right"><b>Parent resource</b></TableCell>
            <TableCell align="right"><b>Action</b></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.classes.map((row:any) => (
            <Row key={row.class} row={row} properties={data.properties} />
          ))}
        </TableBody>
      </Table>
    </TableContainer>
    <Box sx={{margin:5}}>
      <CdfPublisher type="transformation rules" fileName={data.file_name} />
      <CdfDownloader type="neat-wf-rules" onDownloadSuccess={onDownloadSuccess} />
      <LocalUploader type="transformation rules" onUpload={onUpload} />
    </Box>


    </Box>
  );
}
