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

function NeatWizard() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const [activeStepId, setActiveStepId] = useState("0");
  const [steps, setSteps] = useState([]);
  const [nextStepId, setNextStepId] = useState("0");
  const [currentStep, setCurrentStep] = useState(null);
  
  /*  {
    "id": "1",
    "question": "What is your favorite color?",
    "description": "This is a description of the question",
    "options": [
      { "value": "Red", "nextStep": "2" },
      { "value": "Blue", "nextStep": "3" },
      { "value": "Green", "nextStep": "4" }
    ],
    "default_next_step": "2",
    "type": "single choice", // single choice, multiple choice, text
    "answer": { "value": "Red", "nextStep": "2", "previousStep": "1" }
  }, */


  useEffect(() => {
    // Fetch the steps from an API endpoint
    let fullPath = neatApiRootUrl + '/data/staging/wizard_steps.json?nocache=' + Date.now();
    fetch(fullPath)
      .then((response) => response.json())
      .then((data) => {
        setSteps(data.steps);
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
    console.dir(steps);
    setActiveStepId(nextStepId);
    const nextStep = getStepById(nextStepId);
    nextStep.answer = {value: "", nextStep: "", previousStep: activeStepId}
    setCurrentStep(nextStep);
    // setAnsweredSteps([...answeredSteps, { question: currentStep.question, step_id: currentStep.id}]);

  };

  const handleBack = () => {
    // setActiveStepId(previousStepId);
    console.dir(currentStep)
    const previousStepId = currentStep.answer.previousStep;
    currentStep.answer = {value: "", nextStep: "", previousStep: ""}
    setActiveStepId(previousStepId);
    setCurrentStep(getStepById(previousStepId));
  };

  const getStepById = (id) => {
    return steps.find((step) => step.id === id);
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
    currentStep.answer.value = value;  //= { value: value, nextStep: value, previousStep: previousStepId };
    currentStep.answer.nextStep = value;
    setNextStepId(value);
    // const nextStepId = currentStep.options.find((option) => option.text === value).nextStep;
    

    // setAnswers({ ...answers, [currentStep.id]: value });
    
    // Update the current step based on the selected answer
    // const currentStep = steps[activeStep];
    // currentStep.value = value;
    // const selectedOption = currentStep.options.find((option) => option.text === value);
    // if (selectedOption && selectedOption.nextStep) {
    //   setActiveStep(selectedOption.nextStep);
    // }
  };

//   const currentStep = steps.filter((step) => step.id == activeStepId)[0];

//   if (activeStepId >= steps!.length) {
//     return (
//       <Container>
//         <Typography variant="h5" gutterBottom>
//           Wizard Completed
//         </Typography>
//         <pre>{JSON.stringify(steps, null, 2)}</pre>
//       </Container>
//     );
//   }

  return (
    <Container>
    <Stepper activeStep={Number(activeStepId)} alternativeLabel>
        {steps?.map((step, index) => (
           step.answer?.value && ( 
          <Step key={step.id}>
            <StepLabel>{step.question}</StepLabel>
          </Step>
            )
        ))}
    </Stepper> 
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
                value={option.nextStep}
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
