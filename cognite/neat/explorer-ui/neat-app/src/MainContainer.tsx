import * as React from 'react';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import QDataTable from './views/ExplorerView';

import Button from '@mui/material/Button';
import MetricsTable from './views/MetricsView';
import ConfigView from './views/ConfigView';
import TransformationTable from './views/TransformationView';
import WorkflowView from './views/WorkflowView';
import ExecutionsTable from 'views/ExecutionsView';
import BuildRoundedIcon from '@mui/icons-material/BuildRounded';
import GlobalConfigView from 'views/GlobalConfigView';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `simple-tab-${index}`,
    'aria-controls': `simple-tabpanel-${index}`,
  };
}

export default function BasicTabs() {
  const [value, setValue] = React.useState(0);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={value} onChange={handleChange} aria-label="basic tabs example">
          <Tab label="Workflows" {...a11yProps(0)} />
          <Tab label="Execution history" {...a11yProps(1)} />
          <Tab label="Configurations" {...a11yProps(2)} />
          <Tab label="Transformation rules" {...a11yProps(3)} />
          <Tab label="Data explorer" {...a11yProps(4)} />
          <Tab label="Statistics" {...a11yProps(5)} />
          <Tab icon={<BuildRoundedIcon />} aria-label="Global config" {...a11yProps(6)} />
        </Tabs>
      </Box>
      <TabPanel value={value} index={0}>
        <WorkflowView/>
      </TabPanel>
      <TabPanel value={value} index={1}>
        <ExecutionsTable />
      </TabPanel>
      <TabPanel value={value} index={2}>
        <ConfigView/>
      </TabPanel>
      <TabPanel value={value} index={3}>
        <TransformationTable/>
      </TabPanel>
      <TabPanel value={value} index={4}>
        <QDataTable />
      </TabPanel>
      <TabPanel value={value} index={5}>
        <MetricsTable />
      </TabPanel>
      <TabPanel value={value} index={6}>
        <GlobalConfigView />
      </TabPanel>

    </Box>
  );
}
