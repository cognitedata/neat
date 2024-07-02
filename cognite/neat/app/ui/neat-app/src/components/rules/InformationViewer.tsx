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
import { valueTypesBaseline } from './LookupLists';

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
    const [rules, setRules] = React.useState<any>({})
    const [selectedTab, setSelectedTab] = React.useState(0);
    const [propsEditorOpen, setPropsEditorOpen] = React.useState(false);
    const [classEditorOpen, setClassEditorOpen] = React.useState(false);
    const [editorData, setEditorData] = React.useState({});
    const modelType = props.modelType;

    const [tableContainerKey, setTableContainerKey] = React.useState(0); // Add state for the key

    const handlePropertyEdit = (data: any) => {
        setRules(data.rules);
        setPropsEditorOpen(false);
        setTableContainerKey(prevKey => prevKey + 1); // Update the key to trigger redraw
    }

    const handleClassEdit = (data: any) => {
        setRules(data.rules);
        setClassEditorOpen(false);
        setTableContainerKey(prevKey => prevKey + 1); // Update the key to trigger redraw
    }

    const handleMetadataEdit = (data: any) => {
        setRules(data.rules);
    }

    const onEditClick = (data: any, action: any) => {
        if (action === "prop_edit") {
            setEditorData(data);
            setPropsEditorOpen(true);
        } else if (action === "class_edit") {
            setEditorData(data);
            setClassEditorOpen(true);
        }
    }

    React.useEffect(() => {
        setRules(props.rules);
    }, [props.rules]);

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
                <InformationMetadataTable metadata={rules.metadata} fileName={props.fileName} onSaved={handleMetadataEdit} />
            )}
            {selectedTab === 1 && (
                <TableContainer component={Paper} key={tableContainerKey}>
                    <InformationArchitectDataModelPropertyEditor data={editorData} classes={rules.classes} fileName={props.fileName} open={propsEditorOpen} onSaved={handlePropertyEdit} onClose={() => { setPropsEditorOpen(false) }} />
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
                                <React.Fragment>
                                    <InformationArchitectPropsRow row={row} properties={rules.properties} onEditClick={onEditClick} modelType={modelType} />
                                </React.Fragment>
                            ))}
                        </TableBody>
                    </Table>
                    <InformationArchitectClassEditor data={editorData} fileName={props.fileName} open={classEditorOpen} onSaved={handleClassEdit} onClose={() => { setClassEditorOpen(false) }} />
                    {modelType == "current" && (<Button variant="outlined" size="small" color="success" style={{ margin: 5 }} onClick={() => setClassEditorOpen(true)}>Add new class</Button>)}
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
    const [editorOpen, setEditorOpen] = React.useState(false);
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
                            <TableCell><b>Data model type</b></TableCell>
                            <TableCell>{metadata?.data_model_type}</TableCell>
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
            <Button variant="outlined" size="small" color="success" style={{ margin: 5 }} onClick={() => setEditorOpen(true)}>Edit</Button>
            <InformationArchitectMetadataEditor data={metadata} fileName={props.fileName} open={editorOpen} onSaved={(data: any) => { props.onSaved(data); setEditorOpen(false) }} onClose={() => { setEditorOpen(false) }} />
        </Box>
    );
}

export function InformationArchitectMetadataEditor(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [data, setData] = React.useState<any>({});
    const [error, setError] = React.useState<any>("");

    React.useEffect(() => {
        setData(props.data);
        setDialogOpen(props.open);
    }, [props.data, props.open]);

    const handleSave = async () => {
        const request = { rule_file: props.fileName, metadata: data };
        const response = await fetch(neatApiRootUrl + '/api/rules/information-architect/component/upsert', { method: 'POST', body: JSON.stringify(request), headers: { 'Content-Type': 'application/json' } })
        if (!response.ok) {
            console.log("Error response", response.status);
            if (response.status >= 400) {
                const errorData = await response.json();
                try {
                    setError(errorData.detail[0].msg);
                } catch (e) {
                    setError(JSON.stringify(errorData));
                }
                return;
            } else {
                setError("An unknown error occurred");
                return;
            }
        } else {
            console.log("Success response", response.status);
            const responseData = await response.json();
            props.onSaved(responseData);
            setDialogOpen(false);
        }
    };

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
                <DialogTitle>Metadata editor</DialogTitle>
                <DialogContent sx={{ height: '90vh' }}>
                    <FormControl sx={{ marginTop: 1 }} fullWidth >
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Title" size='small' variant="outlined" value={data?.name} onChange={(event) => { handleConfigChange("name", event.target.value) }} />
                        <FormControl sx={{ marginTop: 1 }} fullWidth >
                            <InputLabel id="data-model-type-label">Data model type</InputLabel>
                            <Select
                                labelId="data-model-type-label"
                                id="data-model-type"
                                value={data?.data_model_type}
                                label="Data model type"
                                size='small'
                                onChange={(event) => { handleConfigChange("data_model_type", event.target.value) }}
                            >
                                <MenuItem value="solution">
                                    Solution model - is expected to be based on another data model, which should be present as Reference rules.
                                </MenuItem>
                                <MenuItem value="enterprise">
                                    Enterprise model - is expected to be a fundamental data model, meaning that is not based on another data model.
                                </MenuItem>
                            </Select>
                        </FormControl>
                        <FormControl sx={{ marginTop: 1 }} fullWidth >
                            <InputLabel id="role-label">Role</InputLabel>
                            <Select
                                labelId="role-label"
                                id="role"
                                value={data?.role}
                                label="Role"
                                size='small'
                                onChange={(event) => { handleConfigChange("role", event.target.value) }}
                            >
                                <MenuItem value="information architect">
                                    Information architect
                                </MenuItem>
                                <MenuItem value="domain expert">
                                    Domain expert
                                </MenuItem>
                                <MenuItem value="DMS Architect">
                                    DMS Architect
                                </MenuItem>
                            </Select>
                        </FormControl>
                        <FormControl sx={{ marginTop: 1 }} fullWidth >
                            <InputLabel id="schema-label">Schema state</InputLabel>
                            <Select
                                labelId="schema-label"
                                id="schema"
                                size='small'
                                value={data?.schema_}
                                label="Schema state"
                                onChange={(event) => { handleConfigChange("schema_", event.target.value) }}
                            >
                                <MenuItem value="complete">
                                    Complete - model should contain all the classes, views, and containers that are needed for the data model.
                                </MenuItem>
                                <MenuItem value="partial">
                                    Partial - model is expected to be a partial data model. No validation of the consistency of the Rule object as a whole will be done.
                                </MenuItem>
                                <MenuItem value="extended">
                                    extended - model is expected to be an extension of the previous iteration
                                </MenuItem>
                            </Select>
                        </FormControl>
                        <FormControl sx={{ marginTop: 1 }} fullWidth >
                            <InputLabel id="extension-label">Extension</InputLabel>
                            <Select
                                labelId="extension-label"
                                id="schema"
                                size='small'
                                value={data?.extension}
                                label="Schema state"
                                onChange={(event) => { handleConfigChange("extension", event.target.value) }}
                            >
                                <MenuItem value="addition">
                                    addition
                                </MenuItem>
                                <MenuItem value="reshape">
                                    reshape
                                </MenuItem>
                                <MenuItem value="rebuild">
                                    rebuild
                                </MenuItem>
                            </Select>
                        </FormControl>
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Description" size='small' variant="outlined" value={data?.description} onChange={(event) => { handleConfigChange("description", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Namespace" size='small' variant="outlined" value={data?.namespace} onChange={(event) => { handleConfigChange("namespace", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Prefix" size='small' variant="outlined" value={data?.prefix} onChange={(event) => { handleConfigChange("prefix", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Version" size='small' variant="outlined" value={data?.version} onChange={(event) => { handleConfigChange("version", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Created at" size='small' variant="outlined" value={data?.created} onChange={(event) => { handleConfigChange("created", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Updated at" size='small' variant="outlined" value={data?.updated} onChange={(event) => { handleConfigChange("updated", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Creator" size='small' variant="outlined" value={data?.creator} onChange={(event) => { handleConfigChange("creator", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="License" size='small' variant="outlined" value={data?.license} onChange={(event) => { handleConfigChange("license", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Rights" size='small' variant="outlined" value={data?.rights} onChange={(event) => { handleConfigChange("rights", event.target.value) }} />
                    </FormControl>
                    {error && (<Alert severity="error" sx={{ marginTop: 2 }}>
                        <AlertTitle>Error</AlertTitle>
                        {error}
                    </Alert>
                    )}
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
*/

export function InformationArchitectClassEditor(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [data, setData] = React.useState<any>({});
    const [error, setError] = React.useState<any>("");

    React.useEffect(() => {
        setData(props.data);
        setDialogOpen(props.open);
    }, [props.data, props.open]);

    const handleSave = async () => {
        const request = { rule_file: props.fileName, class_: data };
        const response = await fetch(neatApiRootUrl + '/api/rules/information-architect/component/upsert', { method: 'POST', body: JSON.stringify(request), headers: { 'Content-Type': 'application/json' } })
        if (!response.ok) {
            console.log("Error response", response.status);
            if (response.status >= 400) {
                const errorData = await response.json();
                try {
                    setError(errorData.detail[0].msg);
                } catch (e) {
                    setError(JSON.stringify(errorData));
                }
                return;
            } else {
                setError("An unknown error occurred");
                return;
            }
        } else {
            console.log("Success response", response.status);
            const responseData = await response.json();
            props.onSaved(responseData);
            setDialogOpen(false);
        }
    };

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
                <DialogTitle>Class editor</DialogTitle>
                <DialogContent sx={{ height: '90vh' }}>
                    <FormControl sx={{ marginTop: 2 }} fullWidth >
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Class Id" size='small' variant="outlined" value={data?.class_} onChange={(event) => { handleConfigChange("class_", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Name" size='small' variant="outlined" value={data?.name} onChange={(event) => { handleConfigChange("name", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Description" size='small' variant="outlined" value={data?.description} onChange={(event) => { handleConfigChange("description", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Parent" size='small' variant="outlined" value={data?.parent} onChange={(event) => { handleConfigChange("parent", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Reference" size='small' variant="outlined" value={data?.reference} onChange={(event) => { handleConfigChange("reference", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Match type" size='small' variant="outlined" value={data?.match_type} onChange={(event) => { handleConfigChange("match_type", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Comment" size='small' variant="outlined" value={data?.comment} onChange={(event) => { handleConfigChange("comment", event.target.value) }} />
                    </FormControl>
                    {/* <JsonViewer value={data} /> */}
                    {error && (<Alert severity="error" sx={{ marginTop: 2 }}>
                        <AlertTitle>Error</AlertTitle>
                        {error}
                    </Alert>)}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleSave}>Save</Button>
                    <Button onClick={handleDialogClose}>Close</Button>
                </DialogActions>
            </Dialog>
        </React.Fragment>
    )
}

export default function InformationArchitectDataModelPropertyEditor(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = React.useState(false);
    const [data, setData] = React.useState<any>({});
    const [valueTypes, setValueTypes] = React.useState<any>(valueTypesBaseline);
    const [error, setError] = React.useState<any>("");

    React.useEffect(() => {
        loadUserDefinedTypes(props.classes);
        setData(props.data);
        setDialogOpen(props.open);
    }, [props.data, props.open, props.classes]);

    const handleSave = async () => {
        const request = { rule_file: props.fileName, property: data };
        const response = await fetch(neatApiRootUrl + '/api/rules/information-architect/component/upsert', { method: 'POST', body: JSON.stringify(request), headers: { 'Content-Type': 'application/json' } })
        if (!response.ok) {
            console.log("Error response", response.status);
            if (response.status >= 400) {
                const errorData = await response.json();
                try {
                    setError(errorData.detail[0].msg);
                } catch (e) {
                    setError(JSON.stringify(errorData));
                }
                return;
            } else {
                setError("An unknown error occurred");
                return;
            }
        } else {
            console.log("Success response", response.status);
            const responseData = await response.json();
            props.onSaved(responseData);
            setDialogOpen(false);
        }
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
        if (key === "max_count" && value == "" || value == "inf" || value == " ") {
            value = null;
        }
        setData({ ...data, [key]: value });
    }

    return (
        <React.Fragment>
            <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
                <DialogTitle>Data model property editor</DialogTitle>
                <DialogContent sx={{ height: '90vh' }}>
                    <FormControl sx={{ marginTop: 2 }} fullWidth >
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Class Id" size='small' variant="outlined" value={data?.class_} onChange={(event) => { handleConfigChange("class_", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Property Id" size='small' variant="outlined" value={data?.property_} onChange={(event) => { handleConfigChange("property_", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Name" size='small' variant="outlined" value={data?.name} onChange={(event) => { handleConfigChange("name", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Description" size='small' variant="outlined" value={data?.description} onChange={(event) => { handleConfigChange("description", event.target.value) }} />
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
                                renderInput={(params) => <TextField {...params} label="Value type (Value type that the property can hold. It takes either subset of XSD type (see note below) or a class defined)" />}
                            />
                        </FormControl>
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Min count (Minimum number of values that the property can hold. If no value is provided, the default value is 0, which means that the property is optional.)" size='small' variant="outlined" value={data?.min_count} onChange={(event) => { handleConfigChange("min_count", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Max count (Maximum number of values that the property can hold. If no value is provided, the default value is inf, which means that the property can hold any number of values (listable).	)" size='small' variant="outlined" value={data?.max_count} onChange={(event) => { handleConfigChange("max_count", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Default (Specifies default value for the property.)" size='small' variant="outlined" value={data?.default} onChange={(event) => { handleConfigChange("default", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Reference (Reference to the source of the property provided as URI)" size='small' variant="outlined" value={data?.reference} onChange={(event) => { handleConfigChange("reference", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Match type (The match type between the source entity and the class)" size='small' variant="outlined" value={data?.match_type} onChange={(event) => { handleConfigChange("match_type", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Comment" size='small' variant="outlined" value={data?.comment} onChange={(event) => { handleConfigChange("comment", event.target.value) }} />
                    </FormControl>
                    {error && (<Alert severity="error" sx={{ marginTop: 2 }}>
                        <AlertTitle>Error</AlertTitle>
                        {error}
                    </Alert>)}


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

export function InformationArchitectPropsRow(props: { row: any, properties: any, onEditClick: any, modelType: string }) {
    const { row, properties } = props;
    const [open, setOpen] = React.useState(false);
    const getPropertyByClass = (className: string) => {
        const r = properties.filter((f: any) => f.class_ == className);
        return r;
    }
    const modelType = props.modelType;
    const addNewProperty = () => {
        const newProperty = { class_: row.class_, property_: "", name: "", description: "", value_type: "", min_count: 1, max_count: 1, default: null, reference: null, match_type: null, rule_type: null, rule: null, comment: null };
        props.onEditClick(newProperty, "prop_edit");
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
                <TableCell align="center"> {modelType == "current" && (<Button onClick={() => { props.onEditClick(row, "class_edit"); }}>Edit</Button>)}</TableCell>
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
                                            <TableCell>{pr.max_count || "infinite"}</TableCell>
                                            <TableCell>{pr.default}</TableCell>
                                            <TableCell>{pr.reference}</TableCell>
                                            <TableCell>{pr.match_type}</TableCell>
                                            <TableCell>{pr.comment}</TableCell>
                                            <TableCell>   {modelType == "current" && (<Button onClick={() => { props.onEditClick(pr, "prop_edit"); }}>Edit</Button>)} </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>)}
                            {modelType == "current" && (<Button variant="outlined" size="small" color="success" style={{ margin: 5 }} onClick={addNewProperty}>Add new property</Button>)}
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
