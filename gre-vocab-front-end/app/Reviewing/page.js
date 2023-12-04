"use client";
import React, { useState } from "react";
import ReviewWords from "@/components/reviewing/ReviewWords";
import UpdateProgress from "@/components/reviewing/UpdateProgress";

export default function reviewSessionPage() {
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
      <ReviewWords onUserResponse={handleUserResponse} />
      <UpdateProgress
        wordId={wordId}
        response={response}
        session_id={sessionID}
        onProgressUpdated={resetProgress}
      />
    </main>
  );
}
