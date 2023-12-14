"use client";

import React from "react";
import Login from "@/components/login/Login";
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
      <h3 className="text-primary">Login</h3>
      <Login onLoginSuccess={handleLoginSuccess} />
    </div>
  );
};

export default LoginPage;
