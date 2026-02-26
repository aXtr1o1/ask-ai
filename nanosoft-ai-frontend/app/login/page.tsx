"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

const VALID_USERS = ["101", "102"];
const VALID_PASSWORD = "password";

export default function LoginPage() {
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedUser = userId.trim();

    if (!VALID_USERS.includes(trimmedUser) || password !== VALID_PASSWORD) {
      setError("Invalid user ID or password.");
      return;
    }

    setIsSubmitting(true);

    // Very basic "auth": store the logged-in user in localStorage
    if (typeof window !== "undefined") {
      localStorage.setItem("loggedInUser", trimmedUser);
    }

    router.push(`/?userId=${encodeURIComponent(trimmedUser)}`);
  };

  return (
    <div className="login-page">
      <div className="login-greeting">
        <h1 className="login-greeting-title">Welcome back to NanoSoft Ask AI</h1>
        <p className="login-greeting-subtitle">
          Sign in to continue your conversation with your AI assistant.
        </p>
      </div>

      <div className="login-card">
        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label htmlFor="userId" className="login-label">
              Username
            </label>
            <input
              id="userId"
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter your admin username"
              autoComplete="off"
              className="login-input"
            />
          </div>

          <div className="login-field">
            <label htmlFor="password" className="login-label">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="off"
              className="login-input"
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="login-submit"
            style={{
              opacity: isSubmitting ? 0.7 : 1,
              background: isSubmitting ? "rgba(212, 175, 55, 0.5)" : undefined,
            }}
          >
            {isSubmitting ? "Signing in..." : "Continue to chat"}
          </button>
        </form>
      </div>

      <p className="login-footer">NanoSoft Ask AI</p>
    </div>
  );
}

