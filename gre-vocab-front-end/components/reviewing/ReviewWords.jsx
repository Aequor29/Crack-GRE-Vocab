"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Flashcard from "@/components/flashcard/Flashcard";
import axios from "axios";

export default function ReviewWords({ onUserResponse }) {
  const [words, setWords] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [sessionId, setSessionId] = useState(null);

  const router = useRouter();

  useEffect(() => {
    const startNewSession = async () => {
      let id = await initializeSession();
      console.log("Session ID:", id);
      if (id) {
        fetchWords();
      }
    };
    startNewSession();
  }, []);

  const initializeSession = async (sessionType = "reviewing") => {
    const token = localStorage.getItem("token");
    try {
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/vocab/session/create`,
        {
          session_type: sessionType,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setSessionId(response.data.session_id);
      return response.data.session_id;
    } catch (error) {
      console.error("Error initializing session:", error);
      // Handle error appropriately
    }
  };

  const fetchWords = async () => {
    const token = localStorage.getItem("token");
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/vocab/review-words`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      }
    );
    if (response.ok) {
      const data = await response.json();
      console.log("words for reivew:", data);
      setWords(data);
    } else {
      // Handle errors

      console.error("Failed to fetch new words");
    }
  };

  const fetchSessionProgress = async (wordIds) => {
    const token = localStorage.getItem("token");
    try {
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/vocab/session-progress/`,
        { word_ids: wordIds },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      return response.data; // The progress data
    } catch (error) {
      console.error("Error fetching session progress:", error);
      return null;
    }
  };
  const handleUserResponse = async (wordId, response, sessionID) => {
    console.log("Current word ID:", wordId, "Response:", response);
    await onUserResponse(wordId, response, sessionID); // Assuming this updates the proficiency level

    // Fetch updated proficiency levels
    const proficiencyData = await fetchSessionProgress(words.map((w) => w.id));
    const allWordsProficient = proficiencyData.every(
      (item) => item.proficiencyLevel > 4
    );

    if (allWordsProficient) {
      alert("Congratulations! You have review all the words for this session!");
      router.push("/dashboard");
      // End session logic here (e.g., navigate to a different page or show a message)
    } else {
      nextWord();
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
          sessionID={sessionId}
          onUserResponse={handleUserResponse}
        />
      )}
    </div>
  );
}
