import Button from '@mui/material/Button';
import React, { useEffect, useRef } from 'react';
import { useState } from 'react';
import { Editor } from '@monaco-editor/react';
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';
import { FormControl, InputLabel, MenuItem, Select, SelectChangeEvent } from '@mui/material';

export default function FileEditor(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const selectedWorkflow = getSelectedWorkflowName()
    const [data, setData] = useState<any>(props.data);
    const [listOfFilies, setListOfFiles] = useState([]);
    const [filePath, setFilePath] = useState("workflow.yaml");

    const editorRef = useRef(null);

    function handleEditorDidMount(editor, monaco) {
      editorRef.current = editor;
    }

    useEffect(() => {
        loadListOfFiles();
        fetchFileContent(filePath);
    }, []);

    const loadListOfFiles = () => {
        let url = neatApiRootUrl + "/api/workflow/files/" + selectedWorkflow
        fetch(url).then((response) => {
            return response.json();
        }).then((jdata) => {
            setListOfFiles(jdata.files);
        })
    }
    const handleFileSelectorChange = (event: SelectChangeEvent) => {
        setFilePath(event.target.value);
        fetchFileContent(event.target.value);
      };
    
      async function sendStringAsFileToAPI(stringData: string, filePath: string): Promise<void> {
        try {
          const apiUrl = neatApiRootUrl + "/api/workflow/file/" + selectedWorkflow
          // Create a new FormData object
          const formData = new FormData();
      
          // Create a Blob from the string data
          const blob = new Blob([stringData], { type: 'text/plain' });
      
          // Append the Blob to the FormData with a specified filename
          formData.append('file', blob, filePath);
          
          
          // Create headers object with the desired Content-Type
          const headers = new Headers();
          headers.append('Content-Type', 'multipart/form-data');

          // Send a POST request to the API
          const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData,
          });
      
          // Check the response status
          if (response.ok) {
            console.log('String data sent successfully as a file.');
          } else {
            console.error('Failed to send string data as a file to the API.');
          }
        } catch (error) {
          console.error('Error sending string data as a file:', error);
        }
      }  

    const saveFile = () => {
        const payload = editorRef.current.getValue();
        sendStringAsFileToAPI(payload, filePath);
    
    }

      
    const fetchFileContent = async (filePath:string) => {
        let fullPath = neatApiRootUrl + '/data/workflows/' + selectedWorkflow +"/"+ filePath;
        try {
          var myHeaders = new Headers();
          myHeaders.append('pragma', 'no-cache');
          myHeaders.append('cache-control', 'no-cache');
          const response = await fetch(fullPath, { method: "get", headers: myHeaders });
          const content = await response.text();
          setData(content); 
        } catch (error) {
          console.error('Error fetching file:', error);
        }
      };
    return (
        <React.Fragment>
           <FormControl sx={{ width: 500, marginBottom: 2 }}>
                <InputLabel id="workflowSelectorLabel">File selector</InputLabel>
                <Select
                labelId="workflowSelectorLabel"
                id="workflowSelector"
                value={filePath}
                size='small'
                label="File selector"
                onChange={handleFileSelectorChange}
                >
                {
                    listOfFilies && listOfFilies.map((item, i) => (
                    <MenuItem value={item} key={item}>{item} </MenuItem>
                    ))
                }
                </Select>
          </FormControl>  
          <Editor height="75vh" defaultLanguage="python" value={data} onMount={handleEditorDidMount}   />
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={saveFile} >Save</Button>
        </React.Fragment>
    )
}
