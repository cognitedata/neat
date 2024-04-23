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
import { Tab, Tabs, ToggleButton, ToggleButtonGroup } from '@mui/material';
import RulesBrowserDialog from 'components/RulesBrowserDialog';
import RulesV1Viewer from 'components/RulesV1Viewer';
import RulesV2Viewer from 'components/RulesV2Viewer';

export default function TransformationTable() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [data, setData] = useState({"rules":{"classes":[],
  "properties":[],
  "metadata":{"prefix":"","suffix":"","namespace":"","version":"","title":"","description":"","created":"","updated":"","creator":[],"contributor":[],"rights":"","license":"","dataModelId":"","source":""}},
  "file_name":"","hash":"","error_text":"","src":"","rules_schema_version":""});
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
      if (data.rules.metadata)
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

  const onRoleChange = (role:string) => {
    let url = neatApiRootUrl+"/api/rules?"+new URLSearchParams({"workflow_name":selectedWorkflow,"file_name":data.file_name,"version":data.hash,"as_role":role}).toString()
    fetch(url)
    .then((response) => {
      return response.json();
    }).then((data) => {
      setAlertMsg("");
      setData(data);
    }).catch((err) => {
      setAlertMsg("Rules file "+data.file_name+" is either invalid or missing. Please ensure that you have a valid Rules file.");
    }
  )}

  return (
    <Box>
    <Typography variant="subtitle1" gutterBottom>
        Data model (rules {data.rules_schema_version} ) : <a href={downloadUrl} >{data.file_name}</a>  version : {data.hash} source: {data.src} <RulesBrowserDialog onSelectRule={loadArbitraryRulesFile} />
        {data.error_text && <Container sx={{ color: 'red' }}>{data.error_text}</Container>}
    </Typography>
    {alertMsg != "" && (<Alert severity="warning">
      <AlertTitle>Warning</AlertTitle>
        {alertMsg}
    </Alert> )}
    {data?.rules_schema_version == "v1" && (
    <RulesV1Viewer rules={data.rules} ></RulesV1Viewer>
    )}
    {data?.rules_schema_version == "v2" && (
     <Box>
     <RulesV2Viewer rules={data.rules} onRoleChange={onRoleChange} ></RulesV2Viewer>
    </Box>
    )}
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
