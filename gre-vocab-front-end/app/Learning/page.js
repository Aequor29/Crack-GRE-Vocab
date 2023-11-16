"use client";
import React, { useState } from 'react';
import NewWords from '@/components/learning/NewWords';
import CreateProgress from '@/components/learning/CreateProgress';

const LearningSessionPage = () => {
  const [wordId, setWordId] = useState(null);
  const [response, setResponse] = useState(null);

  const handleUserResponse = (id, userResponse) => {
    setWordId(id);
    setResponse(userResponse);
  };

  return (
    <div>
      <NewWords onUserResponse={handleUserResponse} />
      {wordId && response && (
        <CreateProgress wordId={wordId} response={response} />
      )}
    </div>
  );
};

export default LearningSessionPage;
