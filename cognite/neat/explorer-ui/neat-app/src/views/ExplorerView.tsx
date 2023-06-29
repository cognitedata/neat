import * as React from 'react';
import {useState,useEffect} from 'react';
import Box from '@mui/material/Box';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import Button from '@mui/material/Button';
import TextareaAutosize from '@mui/material/TextareaAutosize';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import Collapse from '@mui/material/Collapse';
import Alert from '@mui/material/Alert';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Breadcrumbs from '@mui/material/Breadcrumbs';
import Link from '@mui/material/Link';
import TextField from '@mui/material/TextField';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import TabPanel from 'components/TabPanel';
import OverviewRow from './OverviewView';
import OverviewTable from './OverviewView';
import { ExplorerContext } from '../components/Context';
import RemoveNsPrefix, { getNeatApiRootUrl, getSelectedWorkflowName,getShortenedString } from '../components/Utils';
import Chip from '@mui/material/Chip';
import OutlinedInput from '@mui/material/OutlinedInput';
import { Theme, useTheme } from '@mui/material/styles';
import GraphExplorer from './GraphView';
import AlertTitle from '@mui/material/AlertTitle';


function handleClick(event: React.MouseEvent<HTMLDivElement, MouseEvent>) {
  event.preventDefault();
  console.info('You clicked a breadcrumb.');
}

export function NavBreadcrumbs( props:{bhistory:Array<string>,selectedHandler:Function} ) {
  if (props.bhistory)
  {
  return (
    <div role="presentation" onClick={handleClick}>
      <Breadcrumbs aria-label="breadcrumb">
        {props.bhistory.map((item => (
        <Link underline="hover" color="inherit" onClick={()=>{props.selectedHandler(item)}}>
          {item}
        </Link>
        )))}
      </Breadcrumbs>

    </div>
  );} else
    return ( <Breadcrumbs aria-label="breadcrumb"></Breadcrumbs>);
 }

export function QuerySelector(props:{selectedHandler:Function,settingsUpdateHandler:Function}) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [query, setQuery] = useState('');
    const [rule, setRule] = useState('');
    const [data, setData] = useState([]);
    const [advancedMode, setAdvancedMode] = useState(false);

    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [graphName, setGraphName] = graphNameCtx;
    const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;

    const handleTemplateChange = (event: SelectChangeEvent) => {
      setQuery(event.target.value as string);
    };

    const handleGraphChange = (event: SelectChangeEvent) => {
      console.log("handleGraphChange",event.target.value);
      setGraphName(event.target.value);
    };

    const handleQueryChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setQuery(event.target.value);
    };

    const handleRuleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setRule(event.target.value);
    };

    const handleAdvancedChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      setAdvancedMode(event.target.checked);
    };
    const handleHiddenNsPrefixModeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      console.log("hiddenNsPrefixMode",event.target.checked);
      setHiddenNsPrefixMode(event.target.checked);
      props.settingsUpdateHandler();
    };

    useEffect(() => {
      fetch(neatApiRootUrl+`/api/list-queries`)
       .then((response) => response.json())
        .then((data) => setData(data));
     }, []);

    return (
      <Box sx={{ minWidth: 400  }}>
        <FormControlLabel sx={{marginBottom:2}}  control={<Switch value={advancedMode} onChange={handleAdvancedChange} />} label="Advanced mode" />
        <FormControlLabel sx={{marginBottom:2}}  control={<Switch value={hiddenNsPrefixMode} onChange={handleHiddenNsPrefixModeChange} defaultChecked />} label="Hidden NS Prefix mode" />
        <Box>
        <FormControl sx={{width:500,marginBottom:2}} >
          <InputLabel id="graphSelectorLabel">Graph to query</InputLabel>
            <Select
              labelId="graphSelectorLabel"
              id="graphSelector"
              value={graphName}
              label="Graph to query"
              size='small'
              onChange={handleGraphChange}
            >
              <MenuItem value="source" >Source graph </MenuItem>
              <MenuItem value="solution" >Solution graph </MenuItem>
            </Select>
        </FormControl>
        </Box>
        {advancedMode && (
        <React.Fragment>
        <FormControl sx={{width:"80vw"}}>
          <InputLabel id="queryTemplateSelectorLabel">Query template</InputLabel>
          <Select
            labelId="queryTemplateSelectorLabel"
            id="queryTemplateSelector"
            value={query}
            size='small'
            label="Query template"
            onChange={handleTemplateChange}
          >
          {
            data && data.map((item,i) => (
              <MenuItem value={item.query} key={i}>{item.name} </MenuItem>
            ))
          }
          </Select>
        </FormControl>
        <div style={{margin:"10px"}}> </div>
        <Box>
        <TextareaAutosize  aria-label="SPARQL query" minRows={2} value = {query} placeholder="SPARQL query" style={{width:"80vw"}}  onChange={handleQueryChange} />
        <Button sx={{ margin: "5px" }} variant="contained" onClick={()=>{ props.selectedHandler(query,"query") }}> Run query </Button>
        </Box>
        <Box>
         <TextField id="rule" label="Rule" value = {rule} size='small' sx={{width:"80vw"}} variant="outlined" onChange={handleRuleChange}  />
         <Button sx={{ margin: "5px" }} variant="contained" onClick={()=>{ props.selectedHandler(rule,"rule") }}> Execute rule </Button>
         </Box>
        </React.Fragment>
)}
        <Box>

        </Box>
      </Box>
    );
  }

export function SearchBar(props:{searchButtonHandler:Function}) {
    const [searchStr, setSearchStr] = useState('');
    const [searchType,setSearchType] = useState("value_exact_match");

    const handleSearchTypeChange = (event: SelectChangeEvent) => {
      setSearchType(event.target.value);
    };
    const handleSearchStrChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setSearchStr(event.target.value);
    };


    return (
        <Box sx={{marginBottom:1,marginTop:1}}>
         <TextField id="search" label="Search" value={searchStr} size='small' sx={{width:500}} variant="outlined" onChange={handleSearchStrChange}  />
         <FormControl sx={{width:180 , marginLeft:2}} >
          <InputLabel id="graphSearchTypeLabel">type</InputLabel>
            <Select
              labelId="graphSearcTypehLabel"
              id="graphSearchType"
              value={searchType}
              label="type"
              size='small'
              onChange={handleSearchTypeChange}
            >
              <MenuItem value="value_exact_match" > Exact match </MenuItem>
              <MenuItem value="value_regexp" > Free search </MenuItem>
              <MenuItem value="reference" > Object reference </MenuItem>
            </Select>
        </FormControl>
         <Button sx={{ marginLeft: 2 }} variant="contained" onClick={()=>{props.searchButtonHandler(searchStr,searchType)}}> Search </Button>
        </Box>
    );
  }

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
const MenuProps = {
    PaperProps: {
      style: {
        maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
        width: 250,
      },
    },
};

function getStyles(name: string, personName: readonly string[], theme: Theme) {
  return {
    fontWeight:
      personName.indexOf(name) === -1
        ? theme.typography.fontWeightRegular
        : theme.typography.fontWeightMedium,
  };
}

export function FilterBar(props:{filterChangeHandler:Function}) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [filters, setFilters] = React.useState<string[]>([]);
    const theme = useTheme();
    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [graphName, setGraphName] = graphNameCtx;
    const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;

    const [filterOptions, setFilterOptions] = React.useState([]);
    const [alertMsg, setAlertMsg] = useState("");

    useEffect(() => {
      loadClassSummary();
    }, [graphName]);

    const handleChange = (event: SelectChangeEvent<typeof filters>) => {
      const { target: { value }, } = event;
      setFilters(
        // On autofill we get a stringified value.
        typeof value === 'string' ? value.split(',') : value,
      );
      props.filterChangeHandler(filters)
    };

    function sortArrayOfObjectsByName(arr) {
      return
    }

    const loadClassSummary = () => {
      const workflowName = getSelectedWorkflowName();
      const url = neatApiRootUrl+"/api/get-classes?"+new URLSearchParams({"graph_name":graphName,"cache":"false","workflow_name":workflowName}).toString();

      fetch(url).then((response) => response.json()).then((data) => {
        if (data.error) {
          setAlertMsg("The workflow is missing or has uninitialized graph stores. Please ensure that you add a graph store and/or run the workflow before proceeding. Error msg: "+data.error);
          return;
        }
        let options = [];
        data.rows.forEach((row) => {
          let vClass = "";
          if (hiddenNsPrefixMode) {
            vClass = RemoveNsPrefix(row.class);
          }else {
            vClass = row.class;
          }

          // vClass = row.class;
          setAlertMsg("");
          options.push({class:vClass,ns_class:row.class});
        });
        options = options.sort((a, b) => a.class.localeCompare(b.class));
        setFilterOptions(options);
      }).catch((error) => {
        console.error('Error:', error);
        setAlertMsg("The workflow is missing or has uninitialized graph stores. Please ensure that you add a graph store and/or run the workflow before proceeding. Error msg: "+error);
      }).finally(() => {
       });
    }

    return (
      <div>
    {alertMsg != "" && (<Alert severity="warning">
          <AlertTitle>Warning</AlertTitle>
          {alertMsg}
    </Alert> )}
      <FormControl sx={{ m: 0, width: "94vw" }}>
        <InputLabel id="demo-multiple-chip-label">Filter</InputLabel>
        <Select
          labelId="demo-multiple-chip-label"
          id="demo-multiple-chip"
          multiple
          value={filters}
          size='small'
          onChange={handleChange}
          input={<OutlinedInput id="select-multiple-chip" label="Chip" />}
          renderValue={(selected) => (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {selected.map((value) => (
                <Chip key={value} label={value} />
              ))}
            </Box>
          )}
          MenuProps={MenuProps}
        >
          {filterOptions.map((item) => (
            <MenuItem
              key={item.ns_class}
              value={item.ns_class}
              style={getStyles(item.ns_class, filters, theme)}
            >
              {item.class}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </div>
    );
}

function reshapeData(data) {
    data.rows.map((item,i) => {
      item["id"] = i;
    });
    return;
  }

function a11yProps(index: number) {
    return {
      id: `simple-tab-${index}`,
      'aria-controls': `simple-tabpanel-${index}`,
    };
}


export default function QDataTable() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [loading, setLoading] = React.useState(false);
  const [data, setData] = useState({"fields": [], "rows": [] , "query": "" ,"elapsed_time_sec":0, "error": ""});
  const [columns, setColumns] = useState([]);
  const [openAlert, setOpenAlert] = React.useState(false);
  const [alertMsg, setAlertMsg] = useState("");

  const [graphName, setGraphName] = React.useState("source");
  const [hiddenNsPrefixMode, setHiddenNsPrefixMode] = useState(true);

  const [bhistory, setBhistory] = useState(Array<string>);
  const [tabValue, setTabValue] = React.useState(0);
  const [filters , setFilters] = React.useState(Array<string>);
  const [sparqlQuery, setSparqlQuery] = React.useState("");

  // const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
  // const [graphName, setGraphName] = graphNameCtx;
  // const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;
  let nodeNameProperty = ""


  const getColumnDefs = (fields:[string]) => {
    const columns: GridColDef[] = [];
    columns.push({field: 'id', headerName: 'ID', width: 70});
    fields.map((field) => {
      columns.push({field: field, headerName: field,renderCell: renderCellExpand , flex:0.5});
    });
    return columns;
  }

  const loadObjectAsGraph = (reference:string) => {
    setTabValue(2);
    nodeNameProperty = localStorage.getItem('nodeNameProperty')
    let query = ``
    if (!nodeNameProperty) {
      query = `SELECT (?inst AS ?node_name) ?node_class (?inst AS ?node_id) WHERE {
        BIND( <`+reference+`> AS ?inst)
        ?inst rdf:type ?node_class .
        } `
    } else {
      query = `SELECT ?node_name ?node_class (?inst AS ?node_id) WHERE {
        BIND( <`+reference+`> AS ?inst)
        ?inst `+nodeNameProperty+` ?node_name .
        ?inst rdf:type ?node_class .
        } `
    }

    setSparqlQuery(query);
    // loadDataset(sparqlQuery,"query");
  }

  const loadObjectProperties = (reference:string) => {
    const newHistory  = bhistory.slice();
    let deleteFlag = false;
    for (const [index, value] of newHistory.entries()) {
      if (value == reference) {
         deleteFlag = true;
         bhistory.splice(index);
         break;
      }
      console.log("somethiong here");
    }
    bhistory.push(reference);
    const workflowName = getSelectedWorkflowName();
    fetch(neatApiRootUrl+`/api/object-properties?`+new URLSearchParams({"reference":reference,"graph_name":graphName,"workflow_name":workflowName}).toString())
     .then((response) => response.json())
      .then((rdata) => {
        reshapeData(rdata);
        const cm = getColumnDefs(rdata.fields)
        setColumns(cm);
        setData(rdata)
        setLoading(false);
        setOpenAlert(true);
      }).catch((error) => {
        console.error('Error:', error);
        setData({"fields": [], "rows": [] , "query": "" ,"elapsed_time_sec":0, "error": error.message})
        setLoading(false);
        setOpenAlert(true);
      });
   }

   const searchObjects = (searchStr:string,searchType:string) => {
      setTabValue(1);
      setLoading(true);
      const workflowName = getSelectedWorkflowName();
      fetch(neatApiRootUrl+`/api/search?`+new URLSearchParams({"search_str":searchStr,"graph_name":graphName,"search_type":searchType,"workflow_name":workflowName}).toString())
      .then((response) => response.json())
        .then((rdata) => {
          reshapeData(rdata);
          const cm = getColumnDefs(rdata.fields)
          setColumns(cm);
          setData(rdata)
          setLoading(false);
          setOpenAlert(true);
        }).catch((error) => {
          console.error('Error:', error);
          setData({"fields": [], "rows": [] , "query": "" ,"elapsed_time_sec":0, "error": error.message})
          setLoading(false);
          setOpenAlert(true);
        });
   }

   const handleFilterChange = (filters:string[]) => {
    console.log("handleFilterChange",filters);
    setFilters(filters);
   }
  const renderCellExpand = (params) => {
    console.log(hiddenNsPrefixMode);
    if (params.value?.includes("#_")) {
      return <Box>{getShortenedString(params.value,10)} <Button onClick={(e)=> {loadObjectProperties(params.value)}}>Table </Button> <Button onClick={(e)=> {loadObjectAsGraph(params.value)}}>Graph </Button></Box>

      } else if (params.value?.includes("#") && hiddenNsPrefixMode) {
      const value = RemoveNsPrefix(params.value);

      return <Box sx={{ display: 'flex' }}> {value}</Box>
    } else
    return (
       <Box sx={{ display: 'flex' }}> {params.value}</Box>
    );
  }

  const settingsUpdateHandler = (settings:any) => {
    console.log("settingsUpdateHandler",settings);
    if (settings) {
      setGraphName(settings.graphName);
      setHiddenNsPrefixMode(settings.hiddenNsPrefixMode);
    }
  }

  const handleRunQueryCommand = (q:string,qtype:string) => {
    setSparqlQuery(q);
    if (tabValue == 0) {
      // switching from Overview tab to Table tab
      setTabValue(1);
    }
    if (tabValue != 2) {
      // non-graph tab
      loadDataset(q,qtype);
    }

  };

  const loadDataset = (q:string,qtype:string) => {
    let query = {}
    let url = ""

    console.log('reseting history');
    setLoading(true);
    const workflowName = getSelectedWorkflowName();
    if (qtype == "query") {
      query = {"query":q,"graph_name":graphName,"workflow_name":workflowName}
      url = neatApiRootUrl+"/api/query"
    } else if (qtype == "rule") {
      query = {"rule":q,"rule_type":"rdfpath","graph_name":graphName,"workflow_name":workflowName}
      url = neatApiRootUrl+"/api/execute-rule"
    }

    fetch(url,{ method:"post",body:JSON.stringify(query),headers: {
      'Content-Type': 'application/json;charset=utf-8'
    }})
    .then((response) => response.json()).then((rdata) => {
      console.dir(rdata)
      reshapeData(rdata);
      const cm = getColumnDefs(rdata.fields)
      setColumns(cm);
      setData(rdata)
      setLoading(false);
      setOpenAlert(true);
    }).catch((error) => {
      console.error('Error:', error);
      setData({"fields": [], "rows": [] , "query": "" ,"elapsed_time_sec":0, "error": error.message})
      setLoading(false);
      setOpenAlert(true);
    });
  }

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    console.log("handleTabChange",newValue);
    setTabValue(newValue);
  };

  const activateTable= (className:string) => {
    setTabValue(1);
    let sparqlQuery = `SELECT ?instance ?property ?value  WHERE {
      ?instance rdf:type <`+className+`> .
      ?instance ?property ?value
     } LIMIT 10000`
    loadDataset(sparqlQuery,"query");
  }

  return (
    <div>

    <ExplorerContext.Provider value={{hiddenNsPrefixModeCtx:[hiddenNsPrefixMode, setHiddenNsPrefixMode],graphNameCtx:[graphName, setGraphName]}}>
    {alertMsg != "" && (<Alert severity="warning">
          <AlertTitle>Warning</AlertTitle>
            {alertMsg}
    </Alert> )}
    <QuerySelector selectedHandler={handleRunQueryCommand} settingsUpdateHandler={settingsUpdateHandler}/>
    <SearchBar searchButtonHandler={searchObjects} />
    <FilterBar filterChangeHandler={handleFilterChange}/>
    { loading &&( <LinearProgress />) }
    <Box sx={{ width: '100%' }}>
      <Tabs value={tabValue} onChange={handleTabChange} aria-label="Explorer tabls">
        <Tab label="Overview" {...a11yProps(0)} />
        <Tab label="Table" {...a11yProps(1)} />
        <Tab label="Graph" {...a11yProps(2)} />
      </Tabs>
      <TabPanel value={tabValue} index={0}>
       <OverviewTable onItemClick={activateTable}/>
      </TabPanel>
      <TabPanel value={tabValue} index={1} >
        <NavBreadcrumbs bhistory={bhistory} selectedHandler={loadObjectProperties}/>
        <div style={{ height: '70vh', width: '100%' }}>
          <DataGrid
              rows={data.rows}
              columns={columns}
              pageSize={100}
              rowsPerPageOptions={[5]}
            />
        </div>
      </TabPanel>
      <TabPanel value={tabValue} index={2}>
        <GraphExplorer filters={filters} sparqlQuery={sparqlQuery}/>
      </TabPanel>
      <Collapse in={openAlert}>
            <Alert
              action={
                <IconButton aria-label="close" color="inherit" size="small" onClick={() => { setOpenAlert(false); }} >
                  <CloseIcon fontSize="inherit" />
                </IconButton>
              } sx={{ mb: 2 }}>
              Elapsed time: {data.elapsed_time_sec*1000} ms. Number of rows: {data.rows.length} . <Box> SPARQL query : {data.query } </Box>
              {data.error &&(<Box> Error: {data.error} </Box>) }
            </Alert>
        </Collapse>
    </Box>

    </ExplorerContext.Provider>
    </div>
  );
}
