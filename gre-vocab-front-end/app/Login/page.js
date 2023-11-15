// Use client directive at the top of the file
'use client';

import React from 'react';
import Login from '@/components/login/Login';
import { useRouter } from 'next/navigation';

const LoginPage = () => {
  const router = useRouter();

  const handleLoginSuccess = () => {
    router.push('/dashboard'); // Replace '/dashboard' with your post-login route
  };

  return (
    <div>
      <h1>Login</h1>
      <Login onLoginSuccess={handleLoginSuccess} />
    </div>
  );
};

export default LoginPage;


