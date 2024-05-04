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
import { getNeatApiRootUrl } from 'components/Utils';
import { Button } from '@mui/material';

function Row(props: { row: any }) {
  const { row } = props;
  const [open, setOpen] = React.useState(false);

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
          {row.name}
        </TableCell>
        <TableCell align="right">{row.type}</TableCell>
        <TableCell align="right">{row.documentation}</TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 1 }}>
              <Typography variant="h6" gutterBottom component="div">
                Metrics
              </Typography>
              <Table size="small" aria-label="purchases">
                <TableHead>
                  <TableRow>
                    <TableCell>Labels</TableCell>
                    <TableCell>Value</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {row.samples.map((metric) => (
                    <TableRow key={JSON.stringify(metric[0])}>
                      <TableCell component="th" scope="row">
                        {JSON.stringify(metric[1])}
                      </TableCell>
                      { row.type == "gauge" &&(<TableCell>{metric[2]}</TableCell>)}
                      { row.type == "counter" &&(<TableCell>{metric[2]}</TableCell>)}
                      { row.type == "summary" &&(<TableCell>Count : {metric[2]} Sum : { metric[3] } sec Avg : {metric[2]/metric[3]} sec </TableCell>)}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </React.Fragment>
  );
}

export default function MetricsTable() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [data, setData] = useState(Array<any>);
  const columns: GridColDef[] = [
    {field: 'id', headerName: 'ID', width: 70},
    {field: 'name', headerName: 'Name', width: 130},
    {field: 'value', headerName: 'Value', type: 'number', width: 90},
  ];

  useEffect(() => {
    loadDataset();
  }, []);

  const loadDataset = () => {
    let url = neatApiRootUrl+"/api/metrics"
    fetch(url)
    .then((response) => {
      return response.json();
    }).then((jdata) => {

      // const parsed = parsePrometheusTextFormat(text);
      setData(jdata.prom_metrics);
      console.dir(jdata.prom_metrics);

    }
  )}
  return (
    <div>
      <Typography> Metrics : </Typography>
    <TableContainer component={Paper}>
      <Table aria-label="collapsible table">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell>Name</TableCell>
            <TableCell align="right">Type</TableCell>
            <TableCell align="right">Help</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row:any) => (
            <Row key={row.name} row={row} />
          ))}
        </TableBody>
      </Table>

    </TableContainer>
    <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }}  onClick={loadDataset}>Reload</Button>
    <p>  <a href='{neatApiRootUrl}/metrics'>Prometheus metrics endpoint</a> </p>
    </div>
  );
}
