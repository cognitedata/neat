import * as React from 'react';
import {useState,useEffect, useRef, useImperativeHandle} from 'react';
import Box from '@mui/material/Box';
import Graph from "graphology";
import { SigmaContainer, useLoadGraph } from "@react-sigma/core";
import { useWorkerLayoutForceAtlas2,useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import "@react-sigma/core/lib/react-sigma.min.css";
import { ControlsContainer, useSigma } from "@react-sigma/core";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import { LayoutForceAtlas2Control } from "@react-sigma/layout-forceatlas2";
import { ExplorerContext } from 'components/Context';
import RemoveNsPrefix, { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';


export function LoadGraph(props:{filters:Array<string>,nodeNameProperty:string,reloader:number}) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [graphName, setGraphName] = graphNameCtx;

    const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;
    const loadGraph = useLoadGraph();
    const sigma = useSigma();
    const { positions, assign } = useLayoutCircular();
    const { start, stop,kill } = useWorkerLayoutForceAtlas2({ settings: { slowDown: 5 } });

    useEffect(() => {
      loadDataset();
    //   start();
      return () => {
        // Kill FA2 on unmount
        kill();
      };

    }, [loadGraph,start,kill]);

    useEffect(() => {
      if (props.reloader) {
        loadDataset();
      }
    }, [props.reloader]);

    const loadDataset = () => {
         console.log("loading dataset");
        //TODO - this is a hack to get the node name property for the solution graph. Make this configurable.
        let nodeNameProperty = props.nodeNameProperty;
        if(!props.nodeNameProperty) {
          if (graphName == "solution") {
              nodeNameProperty = "<http://purl.org/cognite/tnt/IdentifiedObject.name>"
          }else {
              nodeNameProperty = "cim:IdentifiedObject.name"
          }
        }
        const graph = new Graph();
        const url = neatApiRootUrl+"/api/get-nodes-and-edges";
        const workflowName = getSelectedWorkflowName();
        const requestFilter = {
            "graph_name": graphName,
            "workflow_name":workflowName,
            "node_class_filter": props.filters,
            "src_edge_filter": props.filters,
            "dst_edge_filter": props.filters,
            "node_name_property": nodeNameProperty,
            "cache": false,
            "limit": 100000
        }
        fetch(url,{ method:"post",body:JSON.stringify(requestFilter),headers: {
            'Content-Type': 'application/json;charset=utf-8'
          }}).then((response) => response.json()).then((data) => {
            console.dir(data)
            const addedNodes : string[] = [];
            data.nodes.forEach((node) => {
                let nodeClassName = RemoveNsPrefix(node.node_class);
                const nodeLabel = node.node_name+" ("+nodeClassName+")";
                if (!addedNodes.includes(node.node_id)) {
                    addedNodes.push(node.node_id);
                    graph.addNode(node.node_id,{label:nodeLabel,x:1,y:1,color:getColor(nodeClassName), size:getSize(nodeClassName)});
                }
            });
            data.edges.forEach((edge) => {
                if (addedNodes.includes(edge.src_object_ref) && addedNodes.includes(edge.dst_object_ref)) {
                    graph.mergeEdge(edge.src_object_ref,edge.dst_object_ref);
                }

            });
            // loadGraph(graph);
            loadGraph(graph);
            assign();
            console.log("graph loaded");
          }).catch((error) => {
            console.log('Error:', error);
          }).finally(() => {  });
    }

    return null;
  };


export default function GraphExplorer(props:{filters:Array<string>,nodeNameProperty:string}) {
    const [nodeNameProperty, setNodeNameProperty] = useState(localStorage.getItem('nodeNameProperty'));
    const [reloader, setReloader] = useState(0);

    const loaderCompRef = useRef()

    const handleNodeNameProperty = (event: React.ChangeEvent<HTMLInputElement>) => {
        setNodeNameProperty(event.target.value);
        localStorage.setItem('nodeNameProperty',event.target.value);
    };

    const reload = () => {
          setReloader(reloader+1);
    }

    return (
        <Box>
            <TextField id="search" label="Property to use as node name" value={nodeNameProperty} size='small' sx={{width:500}} variant="outlined" onChange={handleNodeNameProperty}  />
            <Button sx={{ marginLeft: 2 }} onClick={() => reload()  } variant="contained"> Reload </Button>
            <SigmaContainer style={{ height: "70vh", width: "100%" }}>
                <LoadGraph filters={props.filters} nodeNameProperty={nodeNameProperty} reloader={reloader} />
                <ControlsContainer position={"top-right"}>
                    <LayoutForceAtlas2Control settings={{ settings: { slowDown: 10 } }} />
                </ControlsContainer>
            </SigmaContainer>

        </Box>
    );
    }

    const colorMap = {
      "Substation": "#42f557",
      "Bay": "#4842f5",
      "Line": "#f59b42",
      "PowerTransformer": "#f54e42",
      "HydroGeneratingUnit": "##0335fc",
      "WindGeneratingUnit": "#03f0fc",
      "SynchronousMachine": "#8d9191",
      "plant": "#42f598",
      "reservoir": "#4263f5",
      "generator": "#f5c542",
      "gate": "#889c6e",
      "pump": "#f58a42",
    }

    const sizeMap = {
      "plant": 8,
      "reservoir": 5,
      "gate": 3,
      "generator": 3,
      "pump": 3,
    }

    function getSize(nodeClass:string) {
      if (nodeClass in sizeMap) {
        return sizeMap[nodeClass];
      } else
        return 1;
    }

    function getColor(nodeClass:string) {
      if (nodeClass in colorMap) {
        return colorMap[nodeClass];
      } else
        return "#c0c4c4";
    }
