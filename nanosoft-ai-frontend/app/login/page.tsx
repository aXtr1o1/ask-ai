"use client";

import { useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_SMARTFM_API_BASE_URL ||
  "https://v4demo.smartfm.cloud";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const p1 = searchParams.get("p1") ?? "";

  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedUser = userId.trim();

    if (!trimmedUser || !password) {
      setError("Please enter username and password.");
      return;
    }

    setIsSubmitting(true);

    try {
      // const apiUrl = `${apiBaseUrl}/askmeapi/login${
      //   p1 ? `?p1=${encodeURIComponent(p1)}` : ""
      // }`;
      const apiUrl = "/api/login";

      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: trimmedUser,
          password: password,
        }),
        cache: "no-store",
      });

      if (!response.ok) {
        setError("Invalid user ID or password.");
        return;
      }

      
      const data = await response.json() as { token?: string; userId?: number };
      const token = data?.token;
      const userIdFromApi = data?.userId;

      if (!token || userIdFromApi == null) {
        setError("Invalid login response.");
        return;
      }

      // Pass token, userId, and p1 to autologin; it will redirect to main chat
      const autologinParams = new URLSearchParams({
        token,
        userId: String(userIdFromApi),
        ...(p1 ? { p1 } : {}),
      });
      router.push(`/autologin?${autologinParams.toString()}`);
    } catch (err) {
      console.error("Login error:", err);
      setError("Unable to contact login service. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
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