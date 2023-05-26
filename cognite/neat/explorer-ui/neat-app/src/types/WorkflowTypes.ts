export enum WorkflowState {
    CREATED = "CREATED",
    RUNNING = "RUNNING",
    COMPLETED = "COMPLETED",
    FAILED = "FAILED"
}

export enum StepExecutionStatus {
    SUCCESS = "COMPLETED",
    FAILED = "FAILED",
    SKIPPED = "SKIPPED",
    STARTED = "STARTED",
    UNKNOWN = "UNKNOWN"
}

export class UIConfig {
    pos_x: number = 0;
    pos_y: number = 0;
}

export class WorkflowConfigItem {
    name: string;
    value: string;
    label?: string;
    type?: string;
    required: boolean = false;
    options?: string[];
    group?: string;
}

export class WorkflowStepDefinition {
    id: string;
    label?: string;
    stype?: string;
    description?: string;
    method?: string;
    enabled?: boolean = true;
    system_component_id?: string;
    trigger?: boolean = false;
    max_retries?: number = 0;
    retry_delay?: number = 3;
    transition_to?: string[];
    params?:any = {}
    ui_config?: UIConfig = new UIConfig();
}


export class WorkflowSystemComponent {
    id: string;
    label: string;
    transition_to?: string[];
    description?: string;
    ui_config?: UIConfig = new UIConfig();
}

export class WorkflowDefinition {
    name: string;
    description?: string;
    steps: WorkflowStepDefinition[];
    system_components: WorkflowSystemComponent[];
    configs?: WorkflowConfigItem[];
    static fromJSON(json: any): WorkflowDefinition {
        let workflow = new WorkflowDefinition();
        Object.assign(workflow, json);
        return workflow;
    }
    serializeToJson(): any {
        let json = JSON.stringify(this);
        return json;
    }

    toJSON() {
        return {
            name: this.name,
            description: this.description,
            configs: this.configs,
            steps: this.steps,
            system_components: this.system_components
        };
    }

    upsertConfigItem(config: WorkflowConfigItem) {
        let index = this.configs.findIndex(c => c.name == config.name);
        if (index >= 0) {
            this.configs[index] = config;
        }else {
            this.configs.push(config);
        }
    }

    addConfigItem(config: WorkflowConfigItem) {
        this.configs.push(config);
    }

    deleteConfigItem(name: string) {
        let index = this.configs.findIndex(c => c.name == name);
        if (index >= 0) {
            this.configs.splice(index, 1);

        }
    }

    getStepById(id: string): WorkflowStepDefinition {
        let step = this.steps.find(step => step.id == id);
        return step;
    }

    getSystemComponentById(id: string): WorkflowSystemComponent {
        let systemComponent = this.system_components.find(systemComponent => systemComponent.id == id);
        return systemComponent;
    }

    updateStep(id:string,step: WorkflowStepDefinition) {
        let index = this.steps.findIndex(s => s.id == id);
        if (index >= 0) {
            this.steps[index] = step;
        }
    }

    updateSystemComponent(id:string,systemComponent: WorkflowSystemComponent) {
        let index = this.system_components.findIndex(g => g.id == id);
        if (index >= 0) {
            this.system_components[index] = systemComponent;
        }
    }

    convertStepsToNodes():any {
        let nodes = [];
        this.steps.forEach(step => {
            let style = {};
            if (step.enabled == false) {
                style = { borderColor: 'red'};
            }
            let node = {
                id: step.id,
                position: {
                    x: step.ui_config.pos_x,
                    y: step.ui_config.pos_y
                },
                data: {
                    label: step.label
                },
                width: 150,
                height: 40,
                style : style,
                selected: false,
                positionAbsolute: {
                    x: step.ui_config.pos_x,
                    y: step.ui_config.pos_y
                },
                dragging: false
            }
            nodes.push(node);
        });
        return nodes;
    }


    convertSystemComponentsToNodes():any {
        let nodes = [];
        this.system_components?.forEach(step => {
            let style = {};
            let node = {
                id: step.id,
                position: {
                    x: step.ui_config.pos_x,
                    y: step.ui_config.pos_y
                },
                data: {
                    label: step.label
                },
                width: 150,
                height: 40,
                style : style,
                selected: false,
                positionAbsolute: {
                    x: step.ui_config.pos_x,
                    y: step.ui_config.pos_y
                },
                dragging: false
            }
            nodes.push(node);
        });
        return nodes;
    }

    convertStepsToEdges():any {
        let edges = [];
        this.steps?.forEach(step => {
            if (step.transition_to) {
                step.transition_to.forEach(transition => {
                    let edge = {
                        id: step.id + "_" + transition,
                        source: step.id,
                        target: transition,
                        animated: true,
                        label: "",
                        arrowHeadType: "arrowclosed"
                    }
                    edges.push(edge);
                });
            }
        });
        return edges;
    }

    convertSystemComponentsToEdges():any {
        let edges = [];
        this.system_components?.forEach(step => {
            if (step.transition_to) {
                step.transition_to.forEach(transition => {
                    let edge = {
                        id: step.id + "_" + transition,
                        source: step.id,
                        target: transition,
                        animated: true,
                        label: "",
                        arrowHeadType: "arrowclosed"
                    }
                    edges.push(edge);
                });
            }
        });
        console.log("Component edges: ");
        console.dir(edges)
        return edges;
    }

    updatePositions(nodes:any) {
        nodes.forEach(node => {
            let step = this.steps.find(step => step.id == node.id);
            if (step) {
                step.ui_config.pos_x = node.position.x;
                step.ui_config.pos_y = node.position.y;
            }else {
                let systemComponent = this.system_components.find(systemComponent => systemComponent.id == node.id);
                if (systemComponent) {
                    systemComponent.ui_config.pos_x = node.position.x;
                    systemComponent.ui_config.pos_y = node.position.y;
                }
            }
        });
    }
    // Update step transitions from edges
    updateStepTransitions(edges:any) {
        this.steps.forEach(step => {
            step.transition_to = [];
        });
        edges.forEach(edge => {
            let source = this.steps.find(step => step.id == edge.source);
            if (source) {
                source.transition_to.push(edge.target);
            }
        });
    }
    // Update systemComponent transitions from edges
    updateSystemComponentTransitions(edges:any) {
        this.system_components.forEach(systemComponent => {
            systemComponent.transition_to = [];
        });
        edges.forEach(edge => {
            let source = this.system_components.find(systemComponent => systemComponent.id == edge.source);
            if (source) {
                source.transition_to.push(edge.target);
            }
        });
    }

    deleteStep(id:string) {
        let index = this.steps.findIndex(s => s.id == id);
        if (index >= 0) {
            this.steps.splice(index,1);
        }
    }

    deleteSystemComponent(id:string) {
        let index = this.system_components.findIndex(g => g.id == id);
        if (index >= 0) {
            this.system_components.splice(index,1);
        }
    }


}
