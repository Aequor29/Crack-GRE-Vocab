"use client";

import React from "react";
import Login from "@/components/login/login";
import { useAuth } from "@/app/AuthContext";
import { useRouter } from "next/navigation";

const LoginPage = () => {
  const router = useRouter();
  const { setIsLoggedIn } = useAuth();

  const handleLoginSuccess = async () => {
    await setIsLoggedIn(true);

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
