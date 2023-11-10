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
} from '@mui/material';
import { getNeatApiRootUrl } from './Utils';


interface Option {
  label: string;
  value: string;
  nextStep: string[];
}

interface Answer {
  value: string;
  label?: string;
  nextSteps: string[];
  previousStep: string;
}

interface Step {
  id: string;
  question: string;
  description: string;
  options: Option[];
  default_next_step: string;
  type: string;
  answer: Answer;
  previousStep: string;

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
    let fullPath = neatApiRootUrl + '/data/staging/wizard_steps.json?nocache=' + Date.now();
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

  const handleNext = () => {
    console.log('Next step id: ' + nextStepId);
    getStepById(nextStepId).answer = currentStep.answer;
    console.dir(wizardData);
    setActiveStepId(nextStepId);
    const nextStep = getStepById(nextStepId);
    nextStep.answer = {value: "",label:"", nextSteps: [""], previousStep: activeStepId}
    setCurrentStep(nextStep);
    // setAnsweredSteps([...answeredSteps, { question: currentStep.question, step_id: currentStep.id}]);

  };

  const handleBack = () => {
    // setActiveStepId(previousStepId);
    console.dir(currentStep)
    const previousStepId = currentStep.answer.previousStep;
    currentStep.answer = {value: "",label:"", nextSteps: [""], previousStep: ""}
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
    currentStep.answer.value = value;
    if (nextSteps) {
      setNextStepId(nextSteps[0]);
      currentStep.answer.nextSteps = nextSteps;
    }else {
      setNextStepId(currentStep.default_next_step);
      currentStep.answer.nextSteps = [currentStep.default_next_step];
    }

  };


  return (
    <Container>
    {currentStep && (

    <Card variant="outlined">
      <CardContent>
        <Typography variant="h5">{currentStep.question}</Typography>
        <Typography variant="subtitle1">{currentStep.description}</Typography>
        <FormControl component="fieldset">
          <FormLabel component="legend">Select an option:</FormLabel>
          <RadioGroup
            name="answer"
            value={currentStep?.answer.value || ''}
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
        <div style={{marginTop:15}}>
          <Button
            variant="contained"
            color="primary"
            onClick={handleNext}
            // disabled={(activeStepId=="1")}
          >
            Next
          </Button>
          {(activeStepId!="1") && (
            <Button variant="contained" color="secondary" onClick={handleBack} sx={{marginLeft:2}} >
              Back
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
    )}
  </Container>
  );
}

export default NeatWizard;
