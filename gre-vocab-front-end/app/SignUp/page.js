import SignUp from "@/components/login/signUp";

export default function SignUpPage() {
  return (
    <div className="flex flex-col justify-center items-center my-4">
      <h1 className="text-primary">Sign Up</h1>
      <SignUp onLoginSuccess={handleLoginSuccess} />
    </div>
  );
}
