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
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(circle at top, #ECFAE5 0, #DDF6D2 35%, #CAE8BD 75%)",
        padding: "16px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "380px",
          background:
            "linear-gradient(135deg, #FFFFFF, #ECFAE5)",
          borderRadius: "18px",
          border: "1px solid rgba(148, 163, 184, 0.4)",
          boxShadow:
            "0 18px 40px rgba(15,23,42,0.7), 0 0 0 1px rgba(15,23,42,0.9)",
          padding: "26px 24px 24px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 10,
              background:
                "linear-gradient(135deg, #B0DB9C, #6fb24f, #CAE8BD)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 10px 25px rgba(34,197,94,0.45)",
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: 0.4,
                color: "#1f2933",
              }}
            >
              NANOSOFT ASK AI
            </span>
            <span
              style={{
                fontSize: 11,
                color: "#4b5f45",
              }}
            >
              Sign in to continue
            </span>
          </div>
        </div>

        <h1
          style={{
            fontSize: 20,
            fontWeight: 600,
            color: "#1f2933",
            marginBottom: 18,
          }}
        >
          Welcome back
        </h1>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label
              htmlFor="userId"
              style={{ fontSize: 12, color: "#4b5f45", fontWeight: 500 }}
            >
              User ID
            </label>
            <input
              id="userId"
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter 101 or 102"
              autoComplete="off"
              style={{
                height: 40,
                borderRadius: 10,
                border: "1px solid rgba(176, 219, 156, 0.9)",
                background: "#FFFFFF",
                color: "#1f2933",
                padding: "0 12px",
                fontSize: 13,
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label
              htmlFor="password"
              style={{ fontSize: 12, color: "#4b5f45", fontWeight: 500 }}
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder='Use "password"'
              autoComplete="off"
              style={{
                height: 40,
                borderRadius: 10,
                border: "1px solid rgba(176, 219, 156, 0.9)",
                background: "#FFFFFF",
                color: "#1f2933",
                padding: "0 12px",
                fontSize: 13,
                outline: "none",
              }}
            />
          </div>

          {error && (
            <div
              style={{
                fontSize: 12,
                color: "#b91c1c",
                background: "rgba(254, 202, 202, 0.7)",
                borderRadius: 8,
                padding: "6px 10px",
                border: "1px solid rgba(248, 113, 113, 0.7)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              marginTop: 6,
              height: 42,
              borderRadius: 999,
            border: "1px solid #B0DB9C",
            background: isSubmitting ? "#DDF6D2" : "#B0DB9C",
            color: "#1f2933",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            boxShadow: "none",
            transition: "background 0.1s ease-out, opacity 0.1s",
              opacity: isSubmitting ? 0.7 : 1,
            }}
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>

          <p
            style={{
              marginTop: 10,
              fontSize: 11,
              color: "#4b5f45",
              textAlign: "center",
            }}
          >
            Demo users: <span style={{ color: "#e5e7eb" }}>101</span> or{" "}
            <span style={{ color: "#e5e7eb" }}>102</span> with password{" "}
            <span style={{ color: "#e5e7eb" }}>password</span>.
          </p>
        </form>
      </div>
    </div>
  );
}

