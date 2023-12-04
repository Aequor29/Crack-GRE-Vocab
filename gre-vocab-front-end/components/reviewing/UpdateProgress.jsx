"use client";
import React, { useState, useEffect } from "react";

export default function UpdateProgress({
  wordId,
  response,
  session_id,
  onProgressUpdated,
}) {
  const updateProgressRecord = async () => {
    const token = localStorage.getItem("token");
    try {
      const apiResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/vocab/update-progress`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            word_id: wordId,
            response: response,
            session_id: session_id,
          }),
        }
      );

      if (!apiResponse.ok) {
        throw new Error(`HTTP error! status: ${apiResponse.status}`);
      }

      // Additional successful response handling can be added here
    } catch (error) {
      console.error("Error creating progress record", error);
    }
  };

  React.useEffect(() => {
    console.log("useEffect triggered", { wordId, response, session_id });
    if (wordId && response && session_id) {
      updateProgressRecord().then(() => {
        if (onProgressUpdated) {
          onProgressUpdated();
        }
      });
    }
  }, [wordId, response]);
  return null;
}
