"use client";
import React, { useState } from "react";
import NewWords from "@/components/learning/NewWords";
import CreateProgress from "@/components/learning/CreateProgress";
import { useAuth } from "@/app/AuthContext";

const LearningSessionPage = () => {
  const { isLoggedIn } = useAuth();
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
  if (!isLoggedIn) {
    return (
      <main className="flex flex-col justify-center items-center my-4">
        <h3 className="text-primary">Please login to continue</h3>
      </main>
    );
  }

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
