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
import { Alert, AlertTitle, Box, Button, Collapse, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Tab, Tabs, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { Image } from '@mui/icons-material';
import JsonViewer from 'components/JsonViewer';


export function DMSArchitectRulesViewer(props: any) {
    const { rules } = props;
    const [selectedTab, setSelectedTab] = React.useState(0);
    const [editorOpen, setEditorOpen] = React.useState(false);
    const [editorData, setEditorData] = React.useState({});
    const getListOfClassesFromProperties = (properties: any) => {
        const classes = properties.map((p: any) => p.class_);
        const uniqueClasses = [...new Set(classes)];
        const classesObjects = uniqueClasses.map((c: any) => {
            return { "class_": c, "description": "", "name": "", "parent": "" };
        }
        );
        return classesObjects;
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
                <Tab label="CDF DM Views" />
                <Tab label="CDF DM Containers" />
            </Tabs>
            {selectedTab === 0 && rules.metadata && (
                <DmsMetadataTable metadata={rules.metadata} />
            )}
            {selectedTab === 1 && (
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
                            {getListOfClassesFromProperties(rules.properties)?.map((row: any) => (
                                <DMSArchitectPropsRow key={row.class} row={row} properties={rules.properties} views={rules.views} onEditClick={(data) => { setEditorOpen(true); setEditorData(data) }} />
                            ))}
                        </TableBody>
                    </Table>
                    <Button variant="outlined" size="small" color="success" style={{ margin: 5 }} onClick={() => setEditorOpen(true)}>Add</Button>
                </TableContainer>
            )}
            {selectedTab == 2 && (
                <DMSArchitectViews row={rules.views} />
            )}
            {selectedTab == 3 && (
                <DMSArchitectContainers row={rules.containers} />
            )}
        </React.Fragment>
    );
}

export function DmsMetadataTable(props: any) {
    const metadata = props.metadata;
    return (
        <Box sx={{ marginTop: 5 }}>
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
                            <TableCell><b>External ID</b></TableCell>
                            <TableCell>{metadata?.external_id}</TableCell>
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

export function DMSArchitectPropsRow(props: { row: any, properties: any, views: any, onEditClick: any }) {
    const { row, properties, views } = props;
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
                <TableCell align="right">{getViewNameByClassId(row.class_)}</TableCell>
                <TableCell align="right">{row.description}</TableCell>
                <TableCell align="center"></TableCell>
            </TableRow>
            <TableRow>
                <TableCell style={{ paddingBottom: 0, paddingTop: 0, minWidth: 2000 }} colSpan={6}>
                    <Collapse in={open} timeout="auto" unmountOnExit>
                        <Box sx={{ margin: 1 }}>
                            <Typography variant="h6" gutterBottom component="div">
                                Properties
                            </Typography>
                            {fProps != undefined && (<Table size="small" aria-label="purchases">
                                <TableHead>
                                    <TableRow>
                                        <TableCell><b>Property Id</b></TableCell>
                                        <TableCell><b>Property name</b></TableCell>
                                        <TableCell><b>Description</b></TableCell>
                                        <TableCell><b>Value type</b></TableCell>
                                        <TableCell><b>Nullable</b></TableCell>
                                        <TableCell><b>Is list</b></TableCell>
                                        <TableCell><b>Relation</b></TableCell>
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
                                        <TableRow key={pr.class_ + pr.property_}>
                                            <TableCell component="th" scope="row"> {pr.property_} </TableCell>
                                            <TableCell>{pr.name}</TableCell>
                                            <TableCell>{pr.description}</TableCell>
                                            <TableCell>{pr.value_type}</TableCell>
                                            <TableCell>{pr.nullable}</TableCell>
                                            <TableCell>{pr.is_list}</TableCell>
                                            <TableCell>{pr.relation}</TableCell>
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
                            </Table>)}
                        </Box>
                    </Collapse>
                </TableCell>
            </TableRow>
        </React.Fragment>
    );
}

export default function DMSArchitectPropsEditor(props: any) {
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [data, setData] = React.useState<any>({});
    const [buttonLabel, setButtonLabel] = React.useState<any>(props.label ? props.label : "View full report");

    React.useEffect(() => {
        setData(props.data);
        setDialogOpen(props.open);
    }, [props.data, props.open]);

    const handleDialogClickOpen = () => {
        setDialogOpen(true);
        if (props.onOpen) {
            props.onOpen();
        }
    };

    const handleDialogClose = () => {
        setDialogOpen(false);
        if (props.onClose) {
            props.onClose();
        }
    };
    return (
        <React.Fragment>
            <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
                <DialogTitle>Data object viewer</DialogTitle>
                <DialogContent sx={{ height: '90vh' }}>
                    <JsonViewer value={data} />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleDialogClose}>Close</Button>
                </DialogActions>
            </Dialog>
        </React.Fragment>
    )
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
export function DMSArchitectViews(props: { row: any }) {
    const { row } = props;
    const [open, setOpen] = React.useState(false);
    return (
        <React.Fragment>
            <TableContainer component={Paper}>
                {row != undefined && (<Table size="small" aria-label="purchases">
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
                </Table>)}
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


export function DMSArchitectContainers(props: { row: any }) {
    const { row } = props;
    const [open, setOpen] = React.useState(false);
    return (
        <React.Fragment>
            <TableContainer component={Paper}>
                {row != undefined && (<Table size="small" aria-label="purchases">
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
                </Table>)}
            </TableContainer>
        </React.Fragment>
    );
}
