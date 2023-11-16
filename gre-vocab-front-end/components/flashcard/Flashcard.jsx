// components/Flashcard.jsx
"use client"
import React, { useState } from 'react';

const Flashcard = ({ wordId, word, pronunciation, definitions, onUserResponse }) => {
  const [currentDefinitionIndex, setCurrentDefinitionIndex] = useState(0);

  const nextDefinition = () => {
    setCurrentDefinitionIndex((prevIndex) => 
      prevIndex === definitions.length - 1 ? 0 : prevIndex + 1
    );
  };

  const handleResponse = (response) => {
    onUserResponse(wordId, response);
  };

  return (
    <div className="flashcard">
      <h2>{word} {pronunciation && `(${pronunciation})`}</h2>
      <p>{definitions[currentDefinitionIndex].definition}</p>
      <button onClick={() => handleResponse('remember')}>Remember</button>
      <button onClick={() => handleResponse('forget')}>Forget</button>
      <button onClick={nextDefinition}>Next Definition</button>
    </div> 
  );
};

export default Flashcard;

