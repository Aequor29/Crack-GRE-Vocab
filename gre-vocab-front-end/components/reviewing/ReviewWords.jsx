"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Flashcard from "@/components/flashcard/Flashcard";
import axios from "axios";

export default function ReviewWords({ onUserResponse }) {
  const [words, setWords] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [finished, setFinished] = useState(false);

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
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/vocab/session-progress/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            word_ids: wordIds,
            session_id: sessionId,
          }),
        }
      );
      const data = await response.json();

      return data; // The progress data
    } catch (error) {
      console.error("Error fetching session progress:", error);
      return null;
    }
  };

  const nextWord = () => {
    setCurrentIndex((prevIndex) =>
      prevIndex === words.length - 1 ? 0 : prevIndex + 1
    );
  };

  const handleUserResponse = async (wordId, response, sessionID) => {
    console.log("Current word ID:", wordId, "Response:", response);
    await onUserResponse(wordId, response, sessionID);
    // Fetch updated proficiency levels
    let proficiencyData = await fetchSessionProgress(words.map((w) => w.id));
    console.log("Proficiency data:", proficiencyData);
    let allWordsProficient = false;
    const length = Object.keys(proficiencyData).length;
    if (length > 0) {
      allWordsProficient = true;
      for (let key in proficiencyData) {
        let proficiency = proficiencyData[key].proficiency_level;
        if (proficiency < 4) {
          allWordsProficient = false;
          break;
        }
      }
    }

    console.log("All words proficient:", allWordsProficient);

    if (allWordsProficient) {
      setFinished(true);

      alert(
        "Congratulations! You have learned all the words for this session!"
      );
      router.push("/dashboard");
      // End session logic here (e.g., navigate to a different page or show a message)
    } else {
      nextWord();
    }
  };

  if (words.length === 0) {
    return (
      <div className="flex flex-col justify-center items-center my-4">
        <h3 className="text-primary">
          No words to be reivewed for Today. Yeah!!!!!
        </h3>
      </div>
    );
  }

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
