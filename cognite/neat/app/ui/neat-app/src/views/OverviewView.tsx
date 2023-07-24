import * as React from 'react';
import {useState,useEffect} from 'react';
import LinearProgress from '@mui/material/LinearProgress';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import RemoveNsPrefix, { getNeatApiRootUrl, getSelectedWorkflowName } from '../components/Utils';
import {ExplorerContext} from '../components/Context';
import { Button, Tab } from '@mui/material';


export interface OverviewRow {
  "class": string;
  "instances": string;
  }


export interface OverviewResponse {
  fields: string[];
  rows: OverviewRow[];
  query: string;
  error: string;
  elapsed_time_sec: number;
  };


export default function OverviewTable(props: {onItemClick: (class_name:string) => void}) {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [data, setData] = useState( {rows:[],fields:[],query:"",error:"",elapsed_time_sec:0} as OverviewResponse );
  const [loading, setLoading] = React.useState(false);
  const [totalInstances, setTotalInstances] = React.useState(0);

  const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
  const [graphName, setGraphName] = graphNameCtx;
  const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;

  useEffect(() => {
    loadClassSummary();
  }, []);

  const loadClassSummary = () => {
    setLoading(true);
    const workflowName = getSelectedWorkflowName();
    const url = neatApiRootUrl+"/api/get-classes?"+new URLSearchParams({"graph_name":graphName,"cache":"false","workflow_name":workflowName}).toString();
    fetch(url).then((response) => response.json()).then((data) => {
      console.dir(data)
      let total = 0;
      data.rows.forEach((row:OverviewRow) => {
        total += parseInt(row.instances);
        row["original_class"] = row.class;
        if (hiddenNsPrefixMode) {
          row.class = RemoveNsPrefix(row.class);
        }
      });
      setTotalInstances(total);
      setData(data);

    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => {
      setLoading(false);
     });
  }

  function Row(iprops: { row: any }) {
    const { row } = iprops;

    return (
      <React.Fragment>
        <TableRow >
          <TableCell align="left">{row.class}</TableCell>
          <TableCell align="left">{row.instances}</TableCell>
          <TableCell align="center"><Button onClick={ ()=> { props.onItemClick(row.original_class) } }>Open in table</Button></TableCell>
        </TableRow>
      </React.Fragment>
    );
  }


  return (
    <div>
    { loading &&( <LinearProgress />) }
    <TableContainer component={Paper}>
      <Table aria-label="collapsible table">
        <TableHead>
          <TableRow>
            <TableCell>Class name</TableCell>
            <TableCell align="left">Instances</TableCell>
            <TableCell align="left">Action</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.rows.map((row:any) => (
            <Row key={row.name} row={row} />
          ))}
          <TableRow >
            <TableCell align="left">Total </TableCell>
            <TableCell align="left">{totalInstances}</TableCell>
            <TableCell align="left"></TableCell>
          </TableRow>
        </TableBody>
      </Table>

    </TableContainer>
    </div>
  );
}
