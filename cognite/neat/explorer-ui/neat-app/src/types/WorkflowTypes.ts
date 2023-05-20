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
    group_id?: string;
    trigger?: boolean = false;
    transition_to?: string[];
    params?:any = {}
    ui_config?: UIConfig = new UIConfig();
}


export class WorkflowStepsGroup {
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
    groups: WorkflowStepsGroup[];
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
            groups: this.groups
        };
    }

    getStepById(id: string): WorkflowStepDefinition {
        let step = this.steps.find(step => step.id == id);
        return step;
    }

    getGroupById(id: string): WorkflowStepsGroup {
        let group = this.groups.find(group => group.id == id);
        return group;
    }

    updateStep(id:string,step: WorkflowStepDefinition) {
        let index = this.steps.findIndex(s => s.id == id);
        if (index >= 0) {
            this.steps[index] = step;
        }
    }

    updateGroup(id:string,group: WorkflowStepsGroup) {
        let index = this.groups.findIndex(g => g.id == id);
        if (index >= 0) {
            this.groups[index] = group;
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

    convertGroupsToNodes():any {
        let nodes = [];
        this.groups.forEach(step => {
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
        this.steps.forEach(step => {
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

    convertGroupsToEdges():any {
        let edges = [];
        this.groups.forEach(step => {
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
                let group = this.groups.find(group => group.id == node.id);
                if (group) {
                    group.ui_config.pos_x = node.position.x;
                    group.ui_config.pos_y = node.position.y;
                }
            }
        });
    }

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

    updateGroupTransitions(edges:any) {
        this.groups.forEach(group => {
            group.transition_to = [];
        });
        edges.forEach(edge => {
            let source = this.groups.find(group => group.id == edge.source);
            if (source) {
                source.transition_to.push(edge.target);
            }
        });
    }


}
