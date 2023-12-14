"use client";
import React, { useState } from "react";
import ReviewWords from "@/components/reviewing/ReviewWords";
import UpdateProgress from "@/components/reviewing/UpdateProgress";
import { useAuth } from "@/app/AuthContext";

export default function reviewSessionPage() {
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
        <h1 className="text-primary">Please login to continue</h1>
      </main>
    );
  }

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
