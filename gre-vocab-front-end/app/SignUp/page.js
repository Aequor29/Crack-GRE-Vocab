"use client";
import SignUp from "@/components/login/signUp";
import { useRouter } from "next/navigation";
import { useAuth } from "@/app/AuthContext";

export default function SignUpPage() {
  const { setIsLoggedIn } = useAuth();
  const router = useRouter();
  const handleSignupSuccess = () => {
    setIsLoggedIn(true);
    router.push("/dashboard");
  };

  return (
    <div className="flex flex-col justify-center items-center my-4">
      <h1 className="text-primary">Sign Up</h1>
      <SignUp onLoginSuccess={handleSignupSuccess} />
    </div>
  );
}
