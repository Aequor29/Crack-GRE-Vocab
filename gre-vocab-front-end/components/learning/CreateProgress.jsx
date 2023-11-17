"use client"
import React from 'react';

const CreateProgress = ({ wordId, response }) => {
  const createProgressRecord = async () => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/vocab/words/response`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ wordId, response })
      });

      if (!response.ok) {
        // Handle non-2xx status codes
        console.error('Failed to create progress record', response.statusText);
      }
    } catch (error) {
      // Handle network errors and other exceptions
      console.error('Error creating progress record', error);
    }
  };

  React.useEffect(() => {
    if (wordId && response) {
      createProgressRecord();
    }
  }, [wordId, response]);

  return null;
};

export default CreateProgress;

