"use client"
import React from 'react';

const CreateProgress = ({ wordId, response, session_id,onProgressUpdated }) => {

  const createProgressRecord = async () => {
    const token = localStorage.getItem('token');
    try {
      const apiResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/vocab/words/response`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ word_id: wordId, response: response, session_id: session_id })
      });
  
      if (!apiResponse.ok) {
        throw new Error(`HTTP error! status: ${apiResponse.status}`);
      }
  
      // Additional successful response handling can be added here
    } catch (error) {
      console.error('Error creating progress record', error);
    }
  };
  
  
  React.useEffect(() => {
    console.log("useEffect triggered", { wordId, response, session_id });
    if (wordId && response && session_id) {
      createProgressRecord().then(() => {
        if (onProgressUpdated) {
          onProgressUpdated();
        }
      });
    }
  }, [wordId, response]);
  

  return null;
};

export default CreateProgress;


