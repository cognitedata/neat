import React, { useState, useEffect } from 'react';
import {
  Container,
  Button,
  Typography,
  Card,
  CardContent,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  FormLabel,
  Stepper,
  Step,
  StepLabel,
  TextField,
} from '@mui/material';
import { getNeatApiRootUrl } from './Utils';


interface Option {
  name: string;
  label: string;
  value: string;
  nextStep: string;
  workflowSteps: string[];
}

interface Answer {
  values: any;
  label?: string;
  nextSteps: string;
  previousStep: string;
}

interface Step {
  id: string;
  question: string; 
  workflowTemplate: string;
  img: string;
  description: string;
  options: Option[];
  default_next_step: string;
  type: string;
  answer: Answer;
  previousStep: string;
  action: string;

}

interface WizardData {
  steps: Step[];
}

function NeatWizard() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [activeStepId, setActiveStepId] = useState("0");
  const [wizardData, setWizardData] = useState<WizardData>();
  const [nextStepId, setNextStepId] = useState("0");
  const [currentStep, setCurrentStep] = useState<Step>();

  useEffect(() => {
    // Fetch the steps from an API endpoint
    let fullPath = neatApiRootUrl + '/templates/default_wizard.json?nocache=' + Date.now();
    fetch(fullPath)
      .then((response) => response.json())
      .then((data) => {
        setWizardData(data);
        setActiveStepId(data.steps[0].id);
        setCurrentStep(data.steps[0]);
      })
      .catch((error) => {
        console.error('Error fetching steps:', error);
      });
  }, []);

  const createWorkflow = () => {
    console.log('Creating workflow');
    console.log(wizardData);
    fetch(neatApiRootUrl + '/api/wizard', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(wizardData),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log('Success:', data);
      })
      .catch((error) => {
        console.error('Error creating workflow:', error);
      });
  }

  const sendResults = () => {
    console.log('Sending results to API');
    console.log(wizardData);
   
    fetch(neatApiRootUrl + '/api/wizard', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(wizardData),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log('Success:', data);
      })
      .catch((error) => {
        console.error('Error sending results:', error);
      });
  }

  const handleNext = () => {
    console.log('Next step id: ' + nextStepId);
    getStepById(nextStepId).answer = currentStep.answer;
  
    setActiveStepId(nextStepId);
    const nextStep = getStepById(nextStepId);
    nextStep.answer = {values: {},label:"", nextSteps: "", previousStep: activeStepId}
    setCurrentStep(nextStep);
    console.dir(wizardData);
    // setAnsweredSteps([...answeredSteps, { question: currentStep.question, step_id: currentStep.id}]);

  };

  const handleBack = () => {
    // setActiveStepId(previousStepId);
    console.dir(currentStep)
    const previousStepId = currentStep.answer.previousStep;
    currentStep.answer = {values: {},label:"", nextSteps: "", previousStep: ""}
    setActiveStepId(previousStepId);
    setCurrentStep(getStepById(previousStepId));
  };

  const getStepById = (id):Step =>  {
    return wizardData.steps.find((step) => step.id === id);
  }


  const getPreviousStepId = (currentStepId) => {
    const currentStep = getStepById(currentStepId);
    if (currentStep && currentStep.previousStep) {
      return getStepById(currentStep.previousStep);
    }
    return null;
  }

  const handleAnswerChange = (event) => {
    const { name, value } = event.target;
    console.log('name: ' + name + ' value: ' + value);
    const nextSteps = currentStep.options.find((option) => option.value === value).nextStep;
    if (currentStep.answer.values == null) {
      currentStep.answer.values = {};
    }
    currentStep.answer.values["selected"] = value;
    if (nextSteps) {
      setNextStepId(nextSteps);
      currentStep.answer.nextSteps = nextSteps;
    }else {
      console.log('No next step found, using default '+ currentStep.default_next_step);
      setNextStepId(currentStep.default_next_step);
      currentStep.answer.nextSteps = currentStep.default_next_step;
    }
    setCurrentStep({...currentStep})
    
  };

  const handleTextFieldChange = (name, value) => {
    currentStep.answer.values[name] = value;
    setNextStepId(currentStep.default_next_step);
    currentStep.answer.nextSteps = currentStep.default_next_step;
    setCurrentStep({...currentStep})
  }

  return (
    <Container>
    {currentStep && (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h5">{currentStep.question}</Typography>
        <Typography variant="subtitle1">{currentStep.description}</Typography>
        { currentStep.img && (
          <img src={neatApiRootUrl + currentStep.img} alt={currentStep.question} style={{width: '100%'}} />
        )}
        { currentStep.type === "single_choice" &&  (
        <FormControl component="fieldset">
          <FormLabel component="legend">Select an option:</FormLabel>
          <RadioGroup
            name="answer"
            value={currentStep?.answer?.values?.selected || ''}
            onChange={handleAnswerChange}
          >
            {currentStep?.options?.map((option, index) => (
              <FormControlLabel
                key={index}
                value={option.value}
                control={<Radio />}
                label={option.label}
              />
            ))}
          </RadioGroup>
        </FormControl>
        ) }
        { currentStep.type === "text_fields" &&  (
          <FormControl fullWidth>
            {currentStep?.options?.map((option, index) => (
             <Container key={index} >
              <Typography sx={{marginRight:7}}>{option?.label} :  </Typography>
              <TextField sx={{ marginTop: 1 }} id="text-field" key={index} fullWidth label="" size='small' variant="outlined" value={currentStep?.answer?.values[option?.name]} onChange={(event) => { handleTextFieldChange(option?.name, event.target.value) }} />
            </Container>
            ))}  
          </FormControl>
        )}

        <div style={{marginTop:15}}>
        {(currentStep?.action != "save_workflow") && (
          <Button
            variant="contained"
            color="primary"
            onClick={handleNext}
            // disabled={(activeStepId=="1")}
          > Next
          </Button>
        )}
          {(currentStep?.action == "save_workflow") && (
            <Button variant="contained" color="primary" onClick={sendResults} sx={{marginLeft:2}} >
              Create workflow
            </Button>
          )}
          {(activeStepId!="1") && (
            <Button variant="contained" color="secondary" onClick={handleBack} sx={{marginLeft:2}} >
              Back
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
    )}
     {(currentStep?.action == "debug") && (
            <pre>{JSON.stringify(wizardData, null, 2)}</pre>
    )}
  </Container>
  );
}

export default NeatWizard;
