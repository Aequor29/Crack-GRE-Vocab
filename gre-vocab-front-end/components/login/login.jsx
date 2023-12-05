"use client";

import React, { useState } from "react";
import { Input, Button } from "@nextui-org/react";

const Login = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    const response = await loginUser({
      username,
      password,
    });

    if (response.access) {
      localStorage.setItem("token", response.access);
      localStorage.setItem("refreshToken", response.refresh);
      onLoginSuccess();
    } else {
      alert("Invalid credentials");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Input
        type="text"
        label="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />

      <br />

      <Input
        type="password"
        label="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <br />
      <Button variant="flat" color="default" type="submit">
        Login
      </Button>
    </form>
  );
};

async function loginUser(credentials) {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/vocab/token/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(credentials),
      }
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Login failed");
    }
    return data;
  } catch (error) {
    console.error("Login error:", error.message);
    return { error: error.message };
  }
}

export default Login;
