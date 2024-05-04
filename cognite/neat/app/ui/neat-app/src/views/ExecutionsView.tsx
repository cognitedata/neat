import * as React from 'react';
import {useState,useEffect} from 'react';

import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import parsePrometheusTextFormat from 'parse-prometheus-text-format';
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
import { convertMillisToStr, getNeatApiRootUrl } from 'components/Utils';
import WorkflowExecutionReport from 'components/WorkflowExecutionReport';

function Row(props: { row: any }) {
  const { row } = props;
  const [open, setOpen] = React.useState(false);
  const [activeRunId, setActiveRunId] = React.useState("");
  const [detailedExecutionReport, setDetailedExecutionReport] = React.useState("");


  const loadExecutionLog = () => {
    setOpen(!open)


  }

  return (
    <React.Fragment>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell>
          <IconButton
            aria-label="expand row"
            size="small"
            onClick={() => loadExecutionLog()}
          >
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell component="th" scope="row">
          {row.workflow_name}
        </TableCell>
        <TableCell align="right">{row.run_id}</TableCell>
        <TableCell align="right" style={{color: row.state == "FAILED" || row.state == "EXPIRED" ? "red" : "green"}}>{row.state}</TableCell>
        <TableCell align="right">{convertMillisToStr(row.start_time)}</TableCell>
        <TableCell align="right">{convertMillisToStr(row.end_time)}</TableCell>
        <TableCell align="right">{row.elapsed_time} sec</TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 1 }}>
              <Typography variant="h6" gutterBottom component="div">
                Detailed execution log
              </Typography>
              {open && (
                <WorkflowExecutionReport report={row} run_id = {row.run_id}/>
              )}

            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </React.Fragment>
  );
}

export default function ExecutionsTable() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [data, setData] = useState(Array<any>);

  useEffect(() => {
    loadDataset();
  }, []);

  const loadDataset = () => {
    let url = neatApiRootUrl+"/api/workflow/executions"
    fetch(url)
    .then((response) => {
      return response.json();
    }).then((jdata) => {
      setData(jdata.executions);

    }
  )}
  return (
    <div>
    <TableContainer component={Paper}>
      <Table aria-label="collapsible table">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell>Workflow name</TableCell>
            <TableCell align="right">Run id</TableCell>
            <TableCell align="right">State</TableCell>
            <TableCell align="right">Start time</TableCell>
            <TableCell align="right">End time</TableCell>
            <TableCell align="right">Duration</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row:any) => (
            <Row key={row.name} row={row} />
          ))}
        </TableBody>
      </Table>

    </TableContainer>
    </div>
  );
}
