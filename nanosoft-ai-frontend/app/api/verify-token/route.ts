import { NextRequest, NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export async function POST(req: NextRequest) {
  try {
    const { token } = await req.json();

    if (!token) {
      return NextResponse.json(
        { error: "Token missing" },
        { status: 400 }
      );
    }

    const payload = jwt.verify(
      token,
      process.env.JWT_SECRET ?? "nano_encryption_key"
    ) as {
      userName: string;
      clientName: string;
      userId: string;
      cl?: string;
      fl?: string;
    };

    return NextResponse.json({
      userName:   payload.userName,
      clientName: payload.clientName,
      userId:     payload.userId,
      cl:         payload.cl ?? "",
      fl:         payload.fl ?? "",
    });

  } catch (err) {
    console.error("[verify-token] failed", err);
    return NextResponse.json(
      { error: "Invalid or expired token" },
      { status: 401 }
    );
  }
}