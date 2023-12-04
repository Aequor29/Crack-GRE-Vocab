"use client";
import React, { useState } from "react";
import NewWords from "@/components/learning/NewWords";
import CreateProgress from "@/components/learning/CreateProgress";

const LearningSessionPage = () => {
  const [wordId, setWordId] = useState(null);
  const [response, setResponse] = useState(null);
  const [sessionID, setSessionID] = useState(null);

  const handleUserResponse = (id, userResponse, sessionID) => {
    console.log(
      "LearningSessionPage handleUserResponse:",
      id,
      userResponse,
      sessionID
    );
    setWordId(id);
    setResponse(userResponse);
    setSessionID(sessionID);
  };

  const resetProgress = () => {
    setWordId(null);
    setResponse(null);
  };

  return (
    <main className="container mx-auto px-4">
      <NewWords onUserResponse={handleUserResponse} />
      <CreateProgress
        wordId={wordId}
        response={response}
        session_id={sessionID}
        onProgressUpdated={resetProgress}
      />
    </main>
  );
};

export default LearningSessionPage;