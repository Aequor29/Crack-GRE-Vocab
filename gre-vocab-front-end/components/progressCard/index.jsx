"use client";
import { Card, CardHeader, CardBody } from "@nextui-org/card";
import { React, useState, useEffect } from "react";
import Chart from "@/components/chart/ProgressChart";

export default function ProgressCard() {
  const [username, setUsername] = useState("");
  const [progress, setProgress] = useState([]);

  const getUserName = async () => {
    const token = localStorage.getItem("token");
    try {
      const apiResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/vocab/profile/`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!apiResponse.ok) {
        throw new Error(`HTTP error! status: ${apiResponse.status}`);
      }

      const data = await apiResponse.json();
      return data.username;
    } catch (error) {
      console.error("Error fetching user name", error);
    }
  };

  const getProgress = async () => {
    const token = localStorage.getItem("token");
    try {
      const apiResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/vocab/user/progress`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!apiResponse.ok) {
        throw new Error(`HTTP error! status: ${apiResponse.status}`);
      }

      const data = await apiResponse.json();
      console.log(data);
      return data;
    } catch (error) {
      console.error("Error fetching user name", error);
    }
  };

  useEffect(() => {
    getUserName().then((name) => {
      setUsername(name);
    });
    getProgress().then((progress) => {
      setProgress(progress);
    });
  }, []);

  return (
    <div>
      <Card>
        <CardHeader>
          <h3 className="text-cyan-600">Hi {username}!</h3>
        </CardHeader>
        <CardBody>
          <p>
            You have learned
            <strong>
              {" "}
              {progress.learned_words_count}/ {progress.total_words_count}
            </strong>{" "}
            words.
          </p>
          <p>
            you have remembered{" "}
            <strong> {progress.well_remembered_words_count} </strong> words
            well.
          </p>
          <p>
            That means you need to review{" "}
            <strong>
              {progress.learned_words_count -
                progress.well_remembered_words_count}{" "}
            </strong>
            words.
          </p>
          <Chart progress={progress} />
        </CardBody>
      </Card>
    </div>
  );
}
