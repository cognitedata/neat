import * as React from 'react';
import {useState,useEffect, useRef, useImperativeHandle,FC} from 'react';
import Box from '@mui/material/Box';
import Graph from "graphology";
import { SearchControl, SigmaContainer, useCamera, useLoadGraph,useRegisterEvents, useSetSettings } from "@react-sigma/core";

import "@react-sigma/core/lib/react-sigma.min.css";
import { ControlsContainer, useSigma } from "@react-sigma/core";
import Sigma from "sigma";
import { ExplorerContext } from 'components/Context';
import RemoveNsPrefix, { getNeatApiRootUrl, getSelectedWorkflowName } from 'components/Utils';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import NodeViewer from 'components/NodeViewer';
import LinearProgress from '@mui/material/LinearProgress';
import { useWorkerLayoutForceAtlas2,useLayoutForceAtlas2, LayoutForceAtlas2Control } from "@react-sigma/layout-forceatlas2";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import Autocomplete from '@mui/material/Autocomplete';
import { Attributes } from "graphology-types";

import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import { Editor } from '@monaco-editor/react';

export function GraphStyleDialog(props: any) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [data, setData] = useState<any>(props.data);
    const editorRef = useRef(null);

    function handleEditorDidMount(editor, monaco) {
      editorRef.current = editor;
    }

    const handleDialogClickOpen = () => {

        setDialogOpen(true);
    };

    const handleDialogClose = () => {
        setDialogOpen(false);
    };

    const handleDialogSave = () => {
      console.log("saving node style");
      const value = editorRef.current.getValue();
      setData(JSON.parse(value));
      localStorage.setItem('nodeTypeConfigMap_'+getSelectedWorkflowName(),value);
      setDialogOpen(false);
      props.onSave();
    };

    useEffect(() => {
      if (props?.data) {
        setData(props.data);
      }else {
        let configMap = localStorage.getItem('nodeTypeConfigMap_'+getSelectedWorkflowName());
        if (configMap) {
          setData(JSON.parse(configMap));
        }else {
          setData({"object_type_name":{"color":"#42f557","size":20}});
        }
      }},[props.data]);
    return (
        <React.Fragment>
          <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
            <DialogTitle>Node style editor</DialogTitle>
            <DialogContent sx={{height:'90vh'}}>
            <Editor defaultLanguage="json" value={JSON.stringify(data)} onMount={handleEditorDidMount} />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Close</Button>
                <Button onClick={handleDialogSave}>Save</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen} > Node style editor </Button>
        </React.Fragment>
    )
}


export function LoadGraph(props:{filters:Array<string>,nodeNameProperty:string,sparqlQuery:string,reloader:number,mode:string,limit:number}) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [graphName, setGraphName] = graphNameCtx;
    const [hiddenNsPrefixMode, setHiddenNsPrefixMode ] = hiddenNsPrefixModeCtx;
    const loadGraph = useLoadGraph();
    // const { positions, assign } = useLayoutForceAtlas2({settings:{strongGravityMode:true},iterations:10});
    const { positions, assign } = useLayoutCircular();
    const { start, stop,kill } = useWorkerLayoutForceAtlas2({ settings: { slowDown: 5 } });
    const [ bigGraph, setBigGraph] = useState<Graph>();
    const [ loading, setLoading] = useState(false);
    const {zoomIn, zoomOut, reset, goto, gotoNode } = useCamera();
    const sigma = useSigma();
    const setSettings = useSetSettings();
    const [hoveredNode, setHoveredNode] = useState<string | null>(null);
    const registerEvents = useRegisterEvents();
    let nodeTypeConfigMap = {};

    useEffect(() => {

      loadDataset();
      // Register the events
       registerEvents({
        enterNode: (event) => setHoveredNode(event.node),
        leaveNode: () => setHoveredNode(null),
      });
      return () => {
        // Kill FA2 on unmount
        kill();
      };

    }, [loadGraph,start,kill]);

    useEffect(() => {
      if (props.reloader || props.sparqlQuery) {
        loadDataset();
      }
    }, [props.reloader,props.sparqlQuery]);

    useEffect(() => {
      setSettings({
        nodeReducer: (node, data) => {
          const graph = sigma.getGraph();
          const newData: Attributes = { ...data, highlighted: data.highlighted || false };

          if (hoveredNode) {
            if (node === hoveredNode || graph.neighbors(hoveredNode).includes(node)) {
              newData.highlighted = true;
            } else {
              newData.color = "#E2E2E2";
              newData.highlighted = false;
            }
          }
          return newData;
        },
        edgeReducer: (edge, data) => {
          const graph = sigma.getGraph();
          const newData = { ...data, hidden: false };

          if (hoveredNode && !graph.extremities(edge).includes(hoveredNode)) {
            newData.hidden = true;
          }
          return newData;
        },
      });
    }, [hoveredNode, setSettings, sigma]);

    function getSize(nodeClass:string,graphSize:number) {
      if (nodeClass in nodeTypeConfigMap) {
        return nodeTypeConfigMap[nodeClass]["size"];
      } else
        // calculate size based on graph size (from 1 to 15). max size for small graphs
        if (graphSize < 15)
          return 20;
        if (graphSize >= 15 && graphSize < 100)
          return 15;
        else
          return 5;
    }

    function getColor(nodeClass:string) {
      if (nodeClass in nodeTypeConfigMap) {
        return nodeTypeConfigMap[nodeClass]["color"];
      } else
        return "#c0c4c4";
    }

    const loadNodeTypeStyles = () => {
    }

    const loadDataset = () => {
        setLoading(true);
        reset();
        setHoveredNode(null);
        if (localStorage.getItem('nodeTypeConfigMap_'+getSelectedWorkflowName())) {
          nodeTypeConfigMap = JSON.parse(localStorage.getItem('nodeTypeConfigMap_'+getSelectedWorkflowName()));
        }
        console.log("loading dataset");
        let nodeNameProperty = ""

        try {
          const nodeNameProp =  JSON.parse(localStorage.getItem('nodeNameProperty_'+getSelectedWorkflowName()))
          if (nodeNameProp && nodeNameProp["id"])
              nodeNameProperty= "<"+nodeNameProp["id"]+">";
        }catch (e) {
          console.log("error parsing node name property");
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
            "limit": props.limit
        }
        fetch(url,{ method:"post",body:JSON.stringify(requestFilter),headers: {
            'Content-Type': 'application/json;charset=utf-8'
          }}).then((response) => response.json()).then((data) => {
            const addedNodes : string[] = [];
            let graphSize = graph.size+data.nodes.length;
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
            setBigGraph(graph);
            loadGraph(graph,true);
            assign();

            stop();
            start();
            // stop after 5 seconds
            setTimeout(() => {
              stop();
            }, 1000);
            console.log("graph loaded");
          }).catch((error) => {
            console.log('Error:', error);
          }).finally(() => {
            setLoading(false);
           });
    }

    return (loading &&( <LinearProgress />) );
  };

  class DatatypePropertyRequest {
    graph_name: string = "source";
    workflow_name: string = "";
    cache: boolean = false;
    limit: number = 10;
  }


export default function GraphExplorer(props:{filters:Array<string>,sparqlQuery:string}) {
    const [reloader, setReloader] = useState(0);
    const loaderCompRef = useRef()
    const [limitRecordsInResponse, setLimitRecordsInResponse] = useState(5000);
    const [openNodeViewer, setOpenNodeViewer] = useState(false);
    const [selectedNodeId, setSelectedNodeId] = useState("");
    const [sparqlQuery, setSparqlQuery] = useState("");
    const [loaderMode, setLoaderMode] = useState("create");
    const [dataTypeProps, setDataTypeProps] = useState(Array<any>);
    const [selectedDataTypeProp, setSelectedDataTypeProp] = useState({ "id": "", "name": "No label , use object id instead", "count": 0});
    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [graphName, setGraphName] = graphNameCtx;
    const [sigma, setSigma] = useState<Sigma | null>(null);


    const handleNodeNameProperty = (event: React.SyntheticEvent, value: any) => {
        if(value != null)
          setSelectedDataTypeProp(value);
        localStorage.setItem('nodeNameProperty_'+getSelectedWorkflowName(),JSON.stringify(value));
        reload();
    };

    const handleResponseLimitChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setLimitRecordsInResponse(parseInt(event.target.value));
    };
    const reload = () => {
          setReloader(reloader+1);
    }
    const loadFullGraph = () => {
      setLoaderMode("create");
      setSparqlQuery("");
      reload();
    }

    useEffect(() => {
      loadDataTypeProps();
      let nodeNameProp = {"id":"","name":"No label , use object id instead","count":0};
      try {
        const nodeNamePropObj =  JSON.parse(localStorage.getItem('nodeNameProperty_'+getSelectedWorkflowName()))
        if (nodeNamePropObj && nodeNamePropObj["id"])
            nodeNameProp= nodeNamePropObj;
      } catch (e) {
        console.log("error parsing node name property");
      }
      setSelectedDataTypeProp(nodeNameProp);
      setSparqlQuery(props.sparqlQuery);
    }, []);

    useEffect(() => {
      console.log("sparqlQuery changed");

    }, [props.sparqlQuery]);


    const onViewerClose = () => {
      setOpenNodeViewer(false);
    }

    const loadDataTypeProps = () => {
      console.log("--------loading data type props----------");
      const url = getNeatApiRootUrl()+"/api/get-datatype-properties";
      const workflowName = getSelectedWorkflowName();
      const request = new DatatypePropertyRequest();
      request.graph_name = graphName;
      request.workflow_name = workflowName;
      request.cache = false;
      request.limit = 2000;
      fetch(url,{ method:"post",body:JSON.stringify(request),headers: {
        'Content-Type': 'application/json;charset=utf-8'
      }}).then((response) => response.json()).then((data) => {
        console.dir(data)
        let dataTypeProps = data.datatype_properties
        dataTypeProps.push({"id":"","name":"No label , use object id instead","count":0});
        setDataTypeProps(data.datatype_properties);
      }).catch((error) => {
      })
    }

    const loadLinkedNodes = (nodeRef:string) => {
      let query = ""
      let nodeNamePropertyMod = ""
      if (selectedDataTypeProp["id"])
         nodeNamePropertyMod= "<"+selectedDataTypeProp["id"]+">";

      if (!nodeNamePropertyMod) {

        query = `SELECT (?dst_object_ref AS ?node_name) (?linked_obj_type  AS ?node_class) (?dst_object_ref AS ?node_id) ?src_object_ref ?dst_object_ref WHERE {
          BIND( <`+nodeRef+`> AS ?src_object_ref )
          {
           ?src_object_ref ?rel_propery ?dst_object_ref .
           ?dst_object_ref rdf:type ?linked_obj_type
          }
          UNION
          {
           ?dst_object_ref ?rel_propery ?src_object_ref .
           ?dst_object_ref rdf:type ?linked_obj_type .
          }
          }  `
      }else {
        query = `SELECT ?node_name (?linked_obj_type  AS ?node_class) (?dst_object_ref AS ?node_id) ?src_object_ref ?dst_object_ref WHERE {
          BIND( <`+nodeRef+`> AS ?src_object_ref )
          {
           ?src_object_ref ?rel_propery ?dst_object_ref .
           ?dst_object_ref rdf:type ?linked_obj_type .
           ?dst_object_ref `+nodeNamePropertyMod+` ?node_name .
          }
          UNION
          {
           ?dst_object_ref ?rel_propery ?src_object_ref .
           ?dst_object_ref rdf:type ?linked_obj_type .
           ?dst_object_ref `+nodeNamePropertyMod+` ?node_name .
          }
          } `
      }
      console.log("requesting linked nodes");

      setSparqlQuery(query);
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
            // event.preventSigmaDefault();
            console.log("clickNode", event.event, event.node )
            console.log("node id: "+event.node);
            setLoaderMode("update");
            setSelectedNodeId(event.node);
            loadLinkedNodes(event.node);
            sigma.getGraph().setNodeAttribute(event.node, "highlighted", true);

          },
          doubleClickNode: (event) => {
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
           <Box sx={{ display: 'flex', alignItems: 'flex-end', marginBottom:2 }}>
            <Autocomplete
              id="datatype-property-selector"
              options={dataTypeProps}
              getOptionLabel={(option) => option["name"]}
              sx={{ width: 500 }}
              value={selectedDataTypeProp}
              size='small' onChange={handleNodeNameProperty}
              renderInput={(params) => <TextField {...params} label="Property to be used as node name." />}
            />
            <TextField id="response_limit" label="Limit max nodes in response" value={limitRecordsInResponse} size='small' type='number' sx={{width:150 , marginLeft:2}} variant="outlined" onChange={handleResponseLimitChange}  />
            <Button sx={{ marginLeft: 2 , marginRight:2}} onClick={() => reload()  } variant="contained"> Reload </Button>

            <GraphStyleDialog onSave ={()=> reload()} />

            </Box>
            <SigmaContainer style={{ height: "70vh", width: "100%" }} ref={setSigma} >
                <LoadGraph filters={props.filters} nodeNameProperty={selectedDataTypeProp["id"]} reloader={reloader} sparqlQuery={sparqlQuery} mode={loaderMode} limit={limitRecordsInResponse}/>
                <ControlsContainer position={"top-right"}>
                    <LayoutForceAtlas2Control settings={{ settings: { slowDown: 10  } }} />
                </ControlsContainer>
                <ControlsContainer position={"top-left"}>
                  <SearchControl style={{ width: "300px" }} />
                </ControlsContainer>
                <GraphEvents />
            </SigmaContainer>
            <NodeViewer open={openNodeViewer} nodeId={selectedNodeId} onClose={onViewerClose} />
        </Box>
    );
    }

    const nodeTypeConfigMap = {
      "Substation": {"color":"#42f557","size":20},
      "Bay": {"color":"#4842f5","size":20},
      "Line": {"color":"#f59b42","size":20},
    }
