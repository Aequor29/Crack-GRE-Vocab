`use client`;
import React, { useState } from "react";
import { Input, Button } from "@nextui-org/react";

const SignUp = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/vocab/signup/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, email }),
      }
    );

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem("token", data.access); // Save the token
      onLoginSuccess(); // Callback for successful login
    } else {
      console.error("Signup failed");
      // Handle errors
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <br />
      <Input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
      />
      <br />
      <Input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <br />

      <Button variant="flat" color="default" type="submit">
        Sign Up
      </Button>
    </form>
  );
};

export default SignUp;
