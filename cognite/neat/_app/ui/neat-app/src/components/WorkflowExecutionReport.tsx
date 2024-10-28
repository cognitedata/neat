import Timeline from '@mui/lab/Timeline';
import TimelineConnector from '@mui/lab/TimelineConnector';
import TimelineContent from '@mui/lab/TimelineContent';
import TimelineDot from '@mui/lab/TimelineDot';
import TimelineItem, { timelineItemClasses } from '@mui/lab/TimelineItem';
import TimelineSeparator from '@mui/lab/TimelineSeparator';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import { Container } from '@mui/system';
import React, { useEffect } from 'react';
import { useState } from 'react';
import { WorkflowStats } from 'views/WorkflowView';
import NJsonViewer from './JsonViewer';
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';

export default function WorkflowExecutionReport(props: any) {
    const [workflowStats, setWorkflowStats] = useState<any>();
    const run_id = props.run_id;

    useEffect(() => {
      if (props.run_id)
          loadReport();
      else
          setWorkflowStats(filterStats(props.report));
    }, [props.report]);

    const loadReport = () => {
      const neatApiRootUrl = getNeatApiRootUrl();
      let url = neatApiRootUrl+"/api/workflow/detailed-execution-report/"+run_id;
      fetch(url)
      .then((response) => {
        return response.json();
      }).then((jdata) => {
        setWorkflowStats(filterStats(jdata.report));

      }
    )}
    const filterStats = (stats: WorkflowStats) => {

      console.dir(stats)
      // detelete all log RUNNING entries that have both RUNNING and COMPLETED entries for the same step
      if (stats?.execution_log == null )
        return stats;

      const filteredLog = stats.execution_log!.filter((log, index) => {
        if (log.state == "STARTED") {
          const nextLog = stats.execution_log[index + 1];
          if (nextLog && nextLog.state == "COMPLETED" && nextLog.id == log.id)
            return false;
        }
        return true;
      })
      stats.execution_log = filteredLog;
      return stats;
    }

    function createMarkup(text) {
      return {__html: text};
    }

    return (
        <Timeline sx={{
            [`& .${timelineItemClasses.root}:before`]: {
              flex: 0,
              padding: 0,
            },
          }} >
            {workflowStats?.execution_log?.map((log) => (
              <TimelineItem key={log.id}>
                <TimelineSeparator>
                  {log.state == "STARTED" && (<TimelineDot color="success" variant="outlined" />)}
                  {log.state == "COMPLETED" && (<TimelineDot color="success" />)}
                  {log.state == "FAILED" && (<TimelineDot color="error" />)}
                  {log.state != "STARTED" && log.state != "COMPLETED" && log.state != "FAILED" && (<TimelineDot />)}
                  <TimelineConnector />
                </TimelineSeparator>
                <TimelineContent> {log.timestamp} - {log.state} : {log.label} ({log.id}) in ({log.elapsed_time} sec)
                  {log.state == "FAILED" && (<div dangerouslySetInnerHTML={ createMarkup(log.error) }></div>)}
                  {log.state == "COMPLETED" && (<div dangerouslySetInnerHTML={ createMarkup(log.output_text) }></div>)}
                  {log.data && ( <NJsonViewer data={log.data} />) }
                </TimelineContent>

              </TimelineItem>
            ))}
            {(workflowStats?.state == "COMPLETED" || workflowStats?.state == "FAILED") && (
              <TimelineItem>
                <TimelineSeparator>
                  {workflowStats?.state == "COMPLETED" && (<TimelineDot color="success" />)}
                  {workflowStats?.state == "FAILED" && (<TimelineDot color="error" />)}
                </TimelineSeparator>
                <TimelineContent> Workflows completed with state : {workflowStats?.state} . Elapsed time : {workflowStats?.elapsed_time} seconds.
                 </TimelineContent>
              </TimelineItem>
            )}
            {(workflowStats?.state != "COMPLETED" && workflowStats?.state != "FAILED" && workflowStats?.state != "CREATED") && (
              <TimelineItem>
                <TimelineSeparator>
                  <TimelineDot variant="outlined" />
                </TimelineSeparator>
                <TimelineContent> <CircularProgress /> </TimelineContent>
              </TimelineItem>
            )}
          </Timeline>
    )
}
