"use client";

import React from "react";
import Login from "@/components/login/Login";
import { useRouter } from "next/navigation";

const LoginPage = () => {
  const router = useRouter();

  const handleLoginSuccess = () => {
    router.push("/dashboard");
  };

  return (
    <div className="flex flex-col justify-center items-center my-4">
      <h1 className="text-primary">Login</h1>
      <Login onLoginSuccess={handleLoginSuccess} />
    </div>
  );
};

export default LoginPage;
