import * as React from 'react';
import {useState,useEffect, useRef, useImperativeHandle,FC} from 'react';
import Box from '@mui/material/Box';
import Graph from "graphology";
import { SigmaContainer, useLoadGraph,useRegisterEvents } from "@react-sigma/core";
import { useWorkerLayoutForceAtlas2,useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import "@react-sigma/core/lib/react-sigma.min.css";
import { ControlsContainer, useSigma } from "@react-sigma/core";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import { LayoutForceAtlas2Control } from "@react-sigma/layout-forceatlas2";
import { ExplorerContext } from 'components/Context';
import RemoveNsPrefix, { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import NodeViewer from 'components/NodeViewer';



export function LoadGraph(props:{filters:Array<string>,nodeNameProperty:string,sparqlQuery:string,reloader:number,mode:string}) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [graphName, setGraphName] = graphNameCtx;
    const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;
    const loadGraph = useLoadGraph();
    const { positions, assign } = useLayoutCircular();
    const { start, stop,kill } = useWorkerLayoutForceAtlas2({ settings: { slowDown: 5 } });
    const [ bigGraph, setBigGraph] = useState<Graph>();


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
        let graph = new Graph();

        if (props.mode== "update"){
          graph = bigGraph;
        }
        
        const url = neatApiRootUrl+"/api/get-nodes-and-edges";
        const workflowName = getSelectedWorkflowName();
        
        const requestFilter = {
            "graph_name": graphName,
            "workflow_name":workflowName,
            "node_class_filter": props.filters,
            "src_edge_filter": props.filters,
            "dst_edge_filter": props.filters,
            "node_name_property": nodeNameProperty,
            "sparql_query": props.sparqlQuery,
            "cache": false,
            "limit": 100000
        }
        fetch(url,{ method:"post",body:JSON.stringify(requestFilter),headers: {
            'Content-Type': 'application/json;charset=utf-8'
          }}).then((response) => response.json()).then((data) => {
            console.dir(data)
            const addedNodes : string[] = [];
            let graphSize = graph.size;
            data.nodes.forEach((node) => {
                let nodeClassName = RemoveNsPrefix(node.node_class);
                const nodeLabel = node.node_name+" ("+nodeClassName+")";
                if (!addedNodes.includes(node.node_id)) {
                    addedNodes.push(node.node_id);
                    graph.mergeNode(node.node_id,{label:nodeLabel,x:1,y:1,color:getColor(nodeClassName), size:getSize(nodeClassName,graphSize)});
                    
                }
            });
            data.edges.forEach((edge) => {
              if (props.mode== "update"){
                graph.mergeEdge(edge.src_object_ref,edge.dst_object_ref);
              }else {
                if (addedNodes.includes(edge.src_object_ref) && addedNodes.includes(edge.dst_object_ref)) {
                  graph.mergeEdge(edge.src_object_ref,edge.dst_object_ref);
                }
              }

            });
            // loadGraph(graph);
            setBigGraph(graph);
            loadGraph(graph);
            assign();
            console.log("graph loaded");
          }).catch((error) => {
            console.log('Error:', error);
          }).finally(() => {  });
    }

    return null;
  };


export default function GraphExplorer(props:{filters:Array<string>,nodeNameProperty:string,sparqlQuery:string}) {
    const [nodeNameProperty, setNodeNameProperty] = useState(localStorage.getItem('nodeNameProperty'));
    const [reloader, setReloader] = useState(0);
    const loaderCompRef = useRef()
    const [openNodeViewer, setOpenNodeViewer] = useState(false);
    const [selectedNodeId, setSelectedNodeId] = useState("");
    const [sparqlQuery, setSparqlQuery] = useState(props.sparqlQuery);
    const [loaderMode, setLoaderMode] = useState("create");
    const handleNodeNameProperty = (event: React.ChangeEvent<HTMLInputElement>) => {
        setNodeNameProperty(event.target.value);
        localStorage.setItem('nodeNameProperty',event.target.value);
    };
   
    const reload = () => {
          setReloader(reloader+1);
    }
    
    const onViewerClose = () => {
      setOpenNodeViewer(false);
    }

    const GraphEvents: React.FC = () => {
      const registerEvents = useRegisterEvents();
      const sigma = useSigma();
      const [draggedNode, setDraggedNode] = useState<string | null>(null);
      useEffect(() => {
        // Register the events
        registerEvents({
          // node events
          rightClickNode: (event) => { 
            console.log("clickNode", event.event, event.node, event.preventSigmaDefault ) 
            console.log("node id: "+event.node);
            setSelectedNodeId(event.node);
            setLoaderMode("update");
            let query = `SELECT (?childName AS ?node_name) (?childType AS ?node_class) (?childInst AS ?node_id) ?src_object_ref (?childInst AS ?dst_object_ref) ?relPropery WHERE { 
              ?childInst ?relProperty <`+event.node+`> . 
              ?childInst `+nodeNameProperty+` ?childName .
              ?childInst rdf:type ?childType . 
              BIND( <`+event.node+`> AS ?src_object_ref)
              } `
            setSparqlQuery(query);
            // setOpenNodeViewer(true);
            setReloader(reloader+1);
            
          },
          doubleClickNode: (event) => { 
            console.log("doubleClickNode", event.event, event.node, event.preventSigmaDefault) 
            setSelectedNodeId(event.node);
            setOpenNodeViewer(true);
          },
          mouseup: (e) => {
            if (draggedNode) {
              setDraggedNode(null);
              sigma.getGraph().removeNodeAttribute(draggedNode, "highlighted");
            }
          },
          mousedown: (e) => {
            // Disable the autoscale at the first down interaction
            if (!sigma.getCustomBBox()) sigma.setCustomBBox(sigma.getBBox());
          },
          mousemove: (e) => {
            if (draggedNode) {
              // Get new position of node
              console.log("draggedNode",draggedNode);
              const pos = sigma.viewportToGraph(e);
              sigma.getGraph().setNodeAttribute(draggedNode, "x", pos.x);
              sigma.getGraph().setNodeAttribute(draggedNode, "y", pos.y);
  
              // Prevent sigma to move camera:
              e.preventSigmaDefault();
              e.original.preventDefault();
              e.original.stopPropagation();
            }
          },
          downNode: (e) => {
            setDraggedNode(e.node);
            sigma.getGraph().setNodeAttribute(e.node, "highlighted", true);
          },
          // rightClickNode: (event) => console.log("rightClickNode", event.event, event.node, event.preventSigmaDefault),
          // wheelNode: (event) => console.log("wheelNode", event.event, event.node, event.preventSigmaDefault),
          // downNode: (event) => console.log("downNode", event.event, event.node, event.preventSigmaDefault),
          // enterNode: (event) => console.log("enterNode", event.node),
          // leaveNode: (event) => console.log("leaveNode", event.node),
          // // edge events
          // clickEdge: (event) => console.log("clickEdge", event.event, event.edge, event.preventSigmaDefault),
          // doubleClickEdge: (event) => console.log("doubleClickEdge", event.event, event.edge, event.preventSigmaDefault),
          // rightClickEdge: (event) => console.log("rightClickEdge", event.event, event.edge, event.preventSigmaDefault),
          // wheelEdge: (event) => console.log("wheelEdge", event.event, event.edge, event.preventSigmaDefault),
          // downEdge: (event) => console.log("downEdge", event.event, event.edge, event.preventSigmaDefault),
          // enterEdge: (event) => console.log("enterEdge", event.edge),
          // leaveEdge: (event) => console.log("leaveEdge", event.edge),
          // // stage events
          // clickStage: (event) => console.log("clickStage", event.event, event.preventSigmaDefault),
          // doubleClickStage: (event) => console.log("doubleClickStage", event.event, event.preventSigmaDefault),
          // rightClickStage: (event) => console.log("rightClickStage", event.event, event.preventSigmaDefault),
          // wheelStage: (event) => console.log("wheelStage", event.event, event.preventSigmaDefault),
          // downStage: (event) => console.log("downStage", event.event, event.preventSigmaDefault),
          // // default mouse events
          // click: (event) => console.log("click", event.x, event.y),
          // doubleClick: (event) => console.log("doubleClick", event.x, event.y),
          // wheel: (event) => console.log("wheel", event.x, event.y, event.delta),
          // rightClick: (event) => console.log("rightClick", event.x, event.y),
          // mouseup: (event) => console.log("mouseup", event.x, event.y),
          // mousedown: (event) => console.log("mousedown", event.x, event.y),
          // mousemove: (event) => console.log("mousemove", event.x, event.y),
          // // default touch events
          // touchup: (event) => console.log("touchup", event.touches),
          // touchdown: (event) => console.log("touchdown", event.touches),
          // touchmove: (event) => console.log("touchmove", event.touches),
          // // sigma kill
          // kill: () => console.log("kill"),
          // resize: () => console.log("resize"),
          // beforeRender: () => console.log("beforeRender"),
          // afterRender: () => console.log("afterRender"),
          // // sigma camera update
          // updated: (event) => console.log("updated", event.x, event.y, event.angle, event.ratio),
        });
      }, [registerEvents, sigma, draggedNode]);
  
      return null;
    };
    return (
        <Box>
            <TextField id="search" label="Property to use as node name" value={nodeNameProperty} size='small' sx={{width:500}} variant="outlined" onChange={handleNodeNameProperty}  />
            <Button sx={{ marginLeft: 2 }} onClick={() => reload()  } variant="contained"> Reload </Button>
            <SigmaContainer style={{ height: "70vh", width: "100%" }}>
                <LoadGraph filters={props.filters} nodeNameProperty={nodeNameProperty} reloader={reloader} sparqlQuery={sparqlQuery} mode={loaderMode}/>
                <ControlsContainer position={"top-right"}>
                    <LayoutForceAtlas2Control settings={{ settings: { slowDown: 10 } }} />
                </ControlsContainer>
                <GraphEvents />
            </SigmaContainer>
            <NodeViewer open={openNodeViewer} nodeId={selectedNodeId} onClose={onViewerClose} />
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

    function getSize(nodeClass:string,graphSize:number) {
      if (nodeClass in sizeMap) {
        return sizeMap[nodeClass];
      } else
        // calculate size based on graph size (from 1 to 15). max size for small graphs
        
        if (graphSize < 15) 
          return 15;
        if (graphSize >= 15 && graphSize < 100) 
          return 10;
        else 
          return 3;
    }

    function getColor(nodeClass:string) {
      if (nodeClass in colorMap) {
        return colorMap[nodeClass];
      } else
        return "#c0c4c4";
    }
