"use client"
import React, { useState, useEffect } from 'react';
import Flashcard from '@/components/flashcard/Flashcard';

const NewWords = ({ onUserResponse }) => {
  const [words, setWords] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    fetchNewWords();
  }, []);

  async function refreshToken() {
    // Assuming you store your refresh token in local storage
    const refreshToken = localStorage.getItem('refreshToken');
  
    // Call your API endpoint to get a new access token
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}vocab/token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh: refreshToken })
    });
  
    if (response.ok) {
      const data = await response.json();
      localStorage.setItem('token', data.access); // Update the access token
      return data.access;
    } else {
      // Handle error, refresh token might be invalid or expired
      console.error('Error refreshing token');
      return null;
    }
  }

  const fetchNewWords = async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/vocab/words/new`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    if (response.ok) {
      const data = await response.json();
      setWords(data);
    } else {
      // Handle errors
      
      console.error('Failed to fetch new words');
    }
  };

  const nextWord = () => {
    setCurrentIndex((prevIndex) => 
      prevIndex === words.length - 1 ? 0 : prevIndex + 1
    );
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
          onUserResponse={(response) => {
            onUserResponse(words[currentIndex].id, response);
            nextWord();
          }}
        />
      )}
    </div>
  );
};

export default NewWords;
