"use client";
import SignUp from "@/components/login/signUp";
import { useRouter } from "next/navigation";

export default function SignUpPage() {
  const router = useRouter();
  const handleSignupSuccess = () => {
    router.push("/dashboard");
  };

  return (
    <div className="flex flex-col justify-center items-center my-4">
      <h1 className="text-primary">Sign Up</h1>
      <SignUp onLoginSuccess={handleSignupSuccess} />
    </div>
  );
}
