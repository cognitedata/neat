import React, { useState, useEffect } from 'react';
import { Typography, List, ListItem, ListItemText } from '@mui/material';
import { getNeatApiRootUrl } from 'components/Utils';


const AboutView = () => {
  const [structure, setStructure] = useState(null);
  const [neatApiRootUrl, setNeatApiRootUrl] = useState(getNeatApiRootUrl());
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(neatApiRootUrl+'/api/about');
        const data = await response.json();
        setStructure(data);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };

    fetchData();
  }, []);

  if (!structure) {
    return <div>Loading...</div>;
  }

  return (
    <div >
      <Typography variant="h5" >
        NEAT Version: {structure.version}
      </Typography>
      <Typography variant="h6" >
        Docs URL: <a href='https://thisisneat.io'>https://thisisneat.io</a>
      </Typography>
      <Typography variant="h6" >
        Docs URL: <a href='https://cognite-neat.readthedocs-hosted.com/en/latest/'>https://cognite-neat.readthedocs-hosted.com/en/latest/</a>
      </Typography>
      <Typography variant="h6" >
        Github: <a href='https://github.com/cognitedata/neat'>https://github.com/cognitedata/neat</a>
      </Typography>
      <Typography variant="h6" >
        Issues tracker (Github): <a href='https://github.com/cognitedata/neat/issues'> https://github.com/cognitedata/neat/issues </a>
      </Typography>
      <Typography variant="h6" >
        License (Apache 2.0): <a href='https://github.com/cognitedata/neat/blob/main/LICENSE'> https://github.com/cognitedata/neat/blob/main/LICENSE </a>
      </Typography>
      <Typography variant="h5">
        3rd party packages :
      </Typography>
      <List dense={true}>
        {structure.packages.map((spackage, index) => (
          <ListItem key={index}>
            <ListItemText primary={spackage} />
          </ListItem>
        ))}
      </List>
    </div>
  );
};

export default AboutView;
