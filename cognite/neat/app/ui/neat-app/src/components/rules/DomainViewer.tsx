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
import { Alert, AlertTitle, Box, Button, Tab, Tabs, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { Image } from '@mui/icons-material';

export function DomainExpertRulesViewer(props: any) {
    const { rules } = props;
    const [selectedTab, setSelectedTab] = React.useState(0);
    const [editorOpen, setEditorOpen] = React.useState(false);
    const [editorData, setEditorData] = React.useState({});
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
            </Tabs>
            {selectedTab === 0 && rules.metadata && (
                <DomainMetadataTable metadata={rules.metadata} />
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

                        </TableBody>
                    </Table>
                    <Button variant="outlined" size="small" color="success" style={{ margin: 5 }} onClick={() => setEditorOpen(true)}>Add</Button>
                </TableContainer>
            )}

        </React.Fragment>
    );
}

export function DomainMetadataTable(props: any) {
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
