import { NextRequest, NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export async function POST(req: NextRequest) {
  try {
    const { token } = await req.json();

    if (!token) {
      console.warn("[verify-token] reject: missing token body");
      return NextResponse.json(
        { error: "Token missing" },
        { status: 400 }
      );
    }

    const secretFromEnv = process.env.JWT_SECRET;
    const secretUsed = secretFromEnv ?? "nano_encryption_key";
    const tokenStr = typeof token === "string" ? token : String(token);
    console.log("[verify-token] verify start", {
      tokenLength: tokenStr.length,
      tokenPreview: `${tokenStr.slice(0, 24)}…${tokenStr.slice(-12)}`,
      jwtSecretFromEnv: Boolean(secretFromEnv),
      usingFallbackSecret: !secretFromEnv,
    });

    const payload = jwt.verify(tokenStr, secretUsed) as {
      userName: string;
      clientName: string;
      userId: string;
      cl?: string;
      fl?: string;
    };

    console.log("[verify-token] verify OK (decoded claims)", {
      userName: payload.userName,
      clientName: payload.clientName,
      userId: payload.userId,
      hasCl: Boolean(payload.cl),
      hasFl: Boolean(payload.fl),
    });

    return NextResponse.json({
      userName:   payload.userName,
      clientName: payload.clientName,
      userId:     payload.userId,
      cl:         payload.cl ?? "",
      fl:         payload.fl ?? "",
    });

  } catch (err) {
    const e = err as Error;
    console.error("[verify-token] verify failed", {
      name: e?.name,
      message: e?.message,
    });
    return NextResponse.json(
      { error: "Invalid or expired token" },
      { status: 401 }
    );
  }
}