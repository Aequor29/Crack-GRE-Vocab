// pages/learn.js or similar
"use client"
// pages/learn.js

import React, { useState, useEffect } from 'react';
import Flashcard from '@/components/flashcard/Flashcard';

const LearningSessionPage = () => {
  const [words, setWords] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    // Fetch words from the API
    // ...
  }, []);

  const LearningSessionPage = () => {
    const [words, setWords] = useState([]);

    useEffect(() => {
        const fetchNewWords = async () => {
            const response = await fetch('http://localhost:8000/vocab/words/new', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    // Include authentication headers if necessary
                }
            });
            if (response.ok) {
                const data = await response.json();
                setWords(data);
            } else {
                // Handle errors
            }
        };

        fetchNewWords();
    }, []);

  const nextWord = () => {
    setCurrentIndex((prevIndex) => 
      prevIndex === words.length - 1 ? 0 : prevIndex + 1
    );
  };

  const handleUserResponse = async (wordId, response) => {
    // Send the response to the backend
    await fetch('/vocab/word-response', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Include authentication headers if necessary
      },
      body: JSON.stringify({ wordId, response })
    });
    
    nextWord();
  };

  

  return (
    <div>
      {words.length > 0 && (
        <Flashcard
          key={words[currentIndex].word}
          wordId={words[currentIndex].id}
          word={words[currentIndex].word}
          pronunciation={words[currentIndex].pronunciation}
          definitions={words[currentIndex].definitions}
          onUserResponse={handleUserResponse}
        />
      )}
    </div>
  );
};

export default LearningSessionPage;
