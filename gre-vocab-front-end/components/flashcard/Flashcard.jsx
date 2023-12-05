import React, { useState } from "react";
import { Button } from "@nextui-org/react";
import "./cardStyles.css";

const Flashcard = ({
  wordId,
  sessionID,
  word,
  pronunciation,
  definitions,
  onUserResponse,
}) => {
  const [isFlipped, setIsFlipped] = useState(false);
  const [currentDefinitionIndex, setCurrentDefinitionIndex] = useState(0);

  const nextDefinition = () => {
    setCurrentDefinitionIndex((prevIndex) =>
      prevIndex === definitions.length - 1 ? 0 : prevIndex + 1
    );
  };

  const handleClick = () => {
    setIsFlipped(!isFlipped);
    console.log(isFlipped);
  };

  const handleResponse = (userResponse) => {
    console.log("User response:", userResponse);
    onUserResponse(wordId, userResponse, sessionID);
    console.log(isFlipped);
  };

  if (!definitions || definitions.length === 0) {
    return <div>Loading definitions...</div>;
  }

  return (
    <div className="flex flex-col justify-center items-center my-5">
      <div
        className={`flashcard ${isFlipped ? "is-flipped" : ""}`}
        onClick={handleClick}
      >
        <div className="card-front">
          <h2>
            {word} {pronunciation && `(${pronunciation})`}
          </h2>
        </div>
        <div className="card-back relative h-full">
          <div className="p-5">
            <h3 className="text-primary mb-2">
              {definitions[currentDefinitionIndex].part_of_speech}
            </h3>
            <p>{definitions[currentDefinitionIndex].definition}</p>
          </div>
          <Button
            variant="flat"
            className="absolute bottom-2 left-1/2 transform -translate-x-1/2"
            onClick={nextDefinition}
          >
            Next Definition
          </Button>
        </div>
      </div>
      <div className="flex justify-center mt-4 gap-5">
        <Button
          color="success"
          variant="flat"
          onClick={() => handleResponse("remember")}
        >
          Remember
        </Button>
        <Button
          color="danger"
          variant="flat"
          onClick={() => handleResponse("forget")}
        >
          Forgot
        </Button>
      </div>
    </div>
  );
};

export default Flashcard;
