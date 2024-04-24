import * as React from 'react';

import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import { Alert, AlertTitle, Box, Button, Collapse, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, IconButton, MenuItem, Select, Tab, Tabs, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { Autocomplete, Container, FormGroup, InputLabel, Link, List, ListItem, ListItemText, Stack, Tooltip, darken, lighten, styled } from "@mui/material"
import { Image } from '@mui/icons-material';
import { JsonViewer } from '@textea/json-viewer'

const GroupHeader = styled('div')(({ theme }) => ({
    position: 'sticky',
    top: '-8px',
    padding: '4px 10px',
    color: theme.palette.primary.main,
    backgroundColor:
        theme.palette.mode === 'light'
            ? lighten(theme.palette.primary.light, 0.85)
            : darken(theme.palette.primary.main, 0.8),
}));

const GroupItems = styled('ul')({
    padding: 0,
});

export function InformationArchitectRulesViewer(props: any) {
    const { rules } = props;
    const [selectedTab, setSelectedTab] = React.useState(0);
    const [editorOpen, setEditorOpen] = React.useState(false);
    const [editorData, setEditorData] = React.useState({});

    const handlePropertyEdit = (data: any) => {
        // merge data with existing properties
        const newProperties = [...rules.properties];
        const index = newProperties.findIndex((f: any) => (f.property_ == data.property_ && f.class_ == data.class_));
        if (index > -1) {
            newProperties[index] = data;
        } else {
            newProperties.push(data);
        }
        rules.properties = newProperties;
        setEditorOpen(false);
    }

    return (
        <React.Fragment>
            <Tabs
                value={selectedTab}
                onChange={(event, newValue) => {
                    setSelectedTab(newValue);
                }}
                variant="scrollable"
                scrollButtons="auto"
                aria-label="scrollable auto tabs example"
            >
                <Tab label="Metadata" />
                <Tab label="Data model" />
                <Tab label="Transformations" />
            </Tabs>
            {selectedTab === 0 && rules.metadata && (
                <InformationMetadataTable metadata={rules.metadata} />
            )}
            {selectedTab === 1 && (
                <TableContainer component={Paper}>
                    <InformationArchitectDataModelPropertyEditor data={editorData} classes={rules.classes} open={editorOpen} onSave={handlePropertyEdit} onClose={() => { setEditorOpen(false) }} />
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
                                <TableCell align="right">Action</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {rules.classes?.map((row: any) => (
                                <InformationArchitectPropsRow row={row} properties={rules.properties} onEditClick={(data, action) => { setEditorData(data); setEditorOpen(true); }} />
                            ))}
                        </TableBody>
                    </Table>
                    <Button variant="outlined" size="small" color="success" style={{ margin: 5 }} onClick={() => setEditorOpen(true)}>Add new class</Button>
                </TableContainer>
            )}
            {selectedTab == 2 && (
                <TableContainer component={Paper}>
                    <Table aria-label="collapsible table">
                        <TableHead>
                            <TableRow>
                                <TableCell />
                                <TableCell> <b>
                                    Class Id</b></TableCell>
                                <TableCell align="right"><b>Name</b></TableCell>
                                <TableCell align="right"><b>Description</b></TableCell>
                                <TableCell align="right">Reference</TableCell>
                                <TableCell align="right">Match type</TableCell>
                                <TableCell align="right">Comment</TableCell>
                                <TableCell align="right"> Action </TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {rules.classes?.map((row: any) => (
                                <InformationArchitectTransformationRow key={row.class} row={row} properties={rules.properties} />
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}
        </React.Fragment>
    );
}


export function InformationMetadataTable(props: any) {
    const metadata = props.metadata;
    return (
        <Box sx={{ marginTop: 5 }}>
            <TableContainer component={Paper}>
                <Table aria-label="metadata table">
                    <TableBody>
                        <TableRow>
                            <TableCell><b>Title</b></TableCell>
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
                            <TableCell><b>Namespace</b></TableCell>
                            <TableCell>{metadata?.namespace}</TableCell>
                        </TableRow>
                        <TableRow>
                            <TableCell><b>Prefix</b></TableCell>
                            <TableCell>{metadata?.prefix}</TableCell>
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
                        <TableRow>
                            <TableCell><b>License</b></TableCell>
                            <TableCell>{metadata?.license}</TableCell>
                        </TableRow>
                        <TableRow>
                            <TableCell><b>Rights</b></TableCell>
                            <TableCell>{metadata?.rights}</TableCell>
                        </TableRow>
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
}

/*
props.data =
{
  "class_": "CFIHOS_00000003",
  "name": "plant_code",
  "description": "A code that uniquely identifies the plant",
  "property_": "CFIHOS_10000005",
  "value_type": "string",
  "min_count": 1,
  "max_count": 1,
  "default": null,
  "reference": null,
  "match_type": null,
  "rule_type": null,
  "rule": null,
  "comment": null
}

Supported value types:
The following XSD types are supported: boolean, float, double ,integer ,nonPositiveInteger ,nonNegativeInteger ,negativeInteger ,long ,string ,langString ,anyURI ,normalizedString ,token ,dateTime ,dateTimeStamp and date. In addition to the subset of XSD types, the following value types are supported: timeseries, file , sequence and json

*/

const valueTypesBaseline = [
    { name: "string", description: "simple string", category: "Basic types" },
    { name: "integer", description: "integer number", category: "Basic types" },
    { name: "boolean", description: "", category: "Basic types" },
    { name: "float", description: "float number", category: "Basic types" },
    { name: "date", description: "", category: "Basic types" },
    { name: "langString", description: "", category: "Advanced types" },
    { name: "long", description: "", category: "Advanced types" },
    { name: "nonPositiveInteger", description: "It represents an number that must be zero or positive number", category: "Advanced types" },
    { name: "nonNegativeInteger", description: "It It represents an number that must be zero or negative number ", category: "Advanced types" },
    { name: "negativeInteger", description: "", category: "Advanced types" },
    { name: "double", description: "", category: "Advanced types" },
    { name: "anyURI", description: "", category: "Advanced types" },
    { name: "normalizedString", description: "", category: "Advanced types" },
    { name: "token", description: "", category: "Advanced types" },
    { name: "dateTime", description: "", category: "Advanced types" },
    { name: "dateTimeStamp", description: "", category: "Advanced types" },
    { name: "timeseries", description: "It represents reference to timeseries.For instance CDF timeseries", category: "Complex types" },
    { name: "file", description: "It represents refernce to a file.For instance CDF file", category: "Complex types" },
    { name: "sequence", description: "It represents reference to CDF sequence", category: "Complex types" },
    { name: "json", description: "json object", category: "Complex types" },
];

export default function InformationArchitectDataModelPropertyEditor(props: any) {
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [data, setData] = React.useState<any>({});
    const [valueTypes, setValueTypes] = React.useState<any>(valueTypesBaseline);

    React.useEffect(() => {
        loadUserDefinedTypes(props.classes);
        setData(props.data);
        setDialogOpen(props.open);
    }, [props.data, props.open, props.classes]);

    const handleSave = () => {
        props.onSave(data);
    };

    const loadUserDefinedTypes = (classes: any) => {
        if (classes == undefined) {
            return;
        }
        const valueTypesClean = [...valueTypesBaseline];
        for (let i = 0; i < props.classes.length; i++) {
            valueTypesClean.push({ name: classes[i].class_, description: classes[i].name, category: "User defined types" });
        }
        setValueTypes(valueTypesClean);
    }

    const handleDialogClose = () => {
        setDialogOpen(false);
        if (props.onClose) {
            props.onClose();
        }
    };
    const handleConfigChange = (key: string, value: any) => {
        setData({ ...data, [key]: value });
    }

    return (
        <React.Fragment>
            <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
                <DialogTitle>Data model property editor</DialogTitle>
                <DialogContent sx={{ height: '90vh' }}>
                    <FormControl sx={{ marginTop: 2 }} fullWidth >
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Class Id" size='small' variant="outlined" value={data?.class_} onChange={(event) => { handleConfigChange("class_", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Name" size='small' variant="outlined" value={data?.name} onChange={(event) => { handleConfigChange("name", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Description" size='small' variant="outlined" value={data?.description} onChange={(event) => { handleConfigChange("description", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Property" size='small' variant="outlined" value={data?.property_} onChange={(event) => { handleConfigChange("property_", event.target.value) }} />
                        <FormControl sx={{ marginTop: 2 }} fullWidth >
                            <Autocomplete
                                disablePortal
                                options={valueTypes.sort((a, b) => -b.category.localeCompare(a.category))} // .sort((a, b) => -b.category.localeCompare(a.category))
                                value={data?.value_type}
                                isOptionEqualToValue={(option, value) => { return option.name === value }}
                                getOptionLabel={(option) => {
                                    if (option.name && option.description) return option.name + " (" + option.description + ")";
                                    else if (option.name) return option.name;
                                    else return option;
                                }}
                                sx={{ marginBottom: 2 }}
                                size='small'
                                groupBy={(option) => option.category}
                                renderGroup={(params) => (
                                    <li key={params.key}>
                                        <GroupHeader>{params.group}</GroupHeader>
                                        <GroupItems>{params.children}</GroupItems>
                                    </li>
                                )}
                                onChange={(event: React.SyntheticEvent, value, reason, details) => { handleConfigChange("value_type", value.name) }}
                                renderInput={(params) => <TextField {...params} label="Valu type (Value type that the property can hold. It takes either subset of XSD type (see note below) or a class defined)" />}
                            />
                        </FormControl>
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Min count (Minimum number of values that the property can hold. If no value is provided, the default value is 0, which means that the property is optional.)" size='small' variant="outlined" value={data?.min_count} onChange={(event) => { handleConfigChange("min_count", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Max count (Maximum number of values that the property can hold. If no value is provided, the default value is inf, which means that the property can hold any number of values (listable).	)" size='small' variant="outlined" value={data?.max_count} onChange={(event) => { handleConfigChange("max_count", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Default (Specifies default value for the property.)" size='small' variant="outlined" value={data?.default} onChange={(event) => { handleConfigChange("default", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Reference (Reference to the source of the property provided as URI)" size='small' variant="outlined" value={data?.reference} onChange={(event) => { handleConfigChange("reference", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Match type (The match type between the source entity and the class)" size='small' variant="outlined" value={data?.match_type} onChange={(event) => { handleConfigChange("match_type", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Comment" size='small' variant="outlined" value={data?.comment} onChange={(event) => { handleConfigChange("comment", event.target.value) }} />
                    </FormControl>
                    {/* <JsonViewer value={data} /> */}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleSave}>Save</Button>
                    <Button onClick={handleDialogClose}>Close</Button>
                </DialogActions>
            </Dialog>
        </React.Fragment>
    )
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

export function InformationArchitectPropsRow(props: { row: any, properties: any, onEditClick: any }) {
    const { row, properties } = props;
    const [open, setOpen] = React.useState(false);
    const getPropertyByClass = (className: string) => {
        const r = properties.filter((f: any) => f.class_ == className);
        return r;
    }
    const [fProps, setFProps] = React.useState(getPropertyByClass(row.class_));
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
                <TableCell align="center"><Button onClick={() => { props.onEditClick(row, "class_edit"); }}>Edit</Button></TableCell>
            </TableRow>
            <TableRow>
                <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
                    <Collapse in={open} timeout="auto" unmountOnExit>
                        <Box sx={{ margin: 1 }}>
                            <Typography variant="h6" gutterBottom component="div">
                                Properties
                            </Typography>
                            {fProps != undefined && (<Table size="small" aria-label="purchases">
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
                                        <TableRow key={pr.class_ + pr.property_}>
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
                                            <TableCell> <Button onClick={() => { props.onEditClick(pr, "prop_edit"); }}>Edit</Button> </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>)}
                        </Box>
                    </Collapse>
                </TableCell>
            </TableRow>
        </React.Fragment>
    );
}

export function InformationArchitectTransformationRow(props: { row: any, properties: any }) {
    const { row, properties } = props;
    const [open, setOpen] = React.useState(false);
    const getPropertyByClass = (className: string) => {
        const r = properties.filter((f: any) => f.class_ == className);
        return r;
    }
    const [fProps, setFProps] = React.useState(getPropertyByClass(row.class_));
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
                            {fProps != undefined && (<Table size="small" aria-label="purchases">
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
                            </Table>)}
                        </Box>
                    </Collapse>
                </TableCell>
            </TableRow>
        </React.Fragment>
    );
}
