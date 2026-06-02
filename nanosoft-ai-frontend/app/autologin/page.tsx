import { headers } from "next/headers";
import { redirect } from "next/navigation";

interface AutoLoginPageProps {
  searchParams: Promise<{
    [key: string]: string | string[] | undefined;
  }>;
}

function getParam(
  params: { [key: string]: string | string[] | undefined },
  key: string
): string | undefined {
  const raw = params?.[key];
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw) && raw[0]) return raw[0];
  return undefined;
}

export const dynamic = "force-dynamic";
// get headers and params

export default async function AutoLoginPage({ searchParams }: AutoLoginPageProps) {
  const reqHeaders = await headers();
  const params = await searchParams;
  const p1 = getParam(params, "p1");
  const xAuth = reqHeaders.get("x-auth") ?? undefined;
  const userId = reqHeaders.get("userid") ?? undefined;

  console.log("[autologin] entry", {
    hasP1: !!p1,
    p1Length: p1?.length,
    hasXAuth: !!xAuth,
    hasUserId: !!userId,
  });

  if (!p1) {
    console.log("[autologin] missing p1, redirecting to /?autologin_error=missing_p1");
    redirect("/?autologin_error=missing_p1");
  }

  let email: string;
  let service: string;

  // decode p1 and parse payload
  try {
    const decoded = Buffer.from(p1, "base64").toString("utf-8");
    console.log("[autologin] decoded p1 (raw)", decoded);

    const payload = JSON.parse(decoded) as {
      email?: string;
      service?: string;
      domain?: string;
    };
    console.log("[autologin] parsed payload", payload);

    if (!payload.email) {
      console.log("[autologin] missing email in payload");
      redirect("/?autologin_error=missing_email");
    }
    email = payload.email;

    if (payload.service) { service = payload.service.replace(/\/$/, ""); }
    else if (payload.domain) { service = `https://${payload.domain}.smartfm.cloud`; }
    else {
      console.log("[autologin] missing service or domain in payload");
      redirect("/?autologin_error=missing_service");
    }
    console.log("[autologin] using", { email, service });
  } catch (err) {
    console.error("[autologin] decode/parse error", err);
    redirect("/?autologin_error=decode_error");
  }
  // encoding :
  const encodedEmail = Buffer.from(email, "utf-8").toString("base64");   ////////////////////////////////
  const autoLoginUrl = `${service}/askmeapi/autoLogin?p1=${encodeURIComponent(encodedEmail)}`;
  //const autoLoginUrl = `${service}/askmeapi/autoLogin?p1=eyJlbWFpbCI6ImFobWVkLmZAYmNnLXVhZS5jb20iLCJkb21haW4iOiJ2NGRlbW8ifQ`;     ////////////////// REMAINDER REMOVE THIS !!!!!
  console.log("[encoding] calling endpoint", { encodedEmail, autoLoginUrl });

  let autoLoginOutput: {
    userID?: number;
    userName?: string;
    service?: string;
  } | null = null;

  // call autoLogin FRONTEND API
  try {
    const response = await fetch(autoLoginUrl, { cache: "no-store" });
    const result = (await response.json().catch(() => ({}))) as {
      Output?: { userID?: number; userName?: string; service?: string };
    };
    console.log("[autologin] autoLogin result", {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      result,
    });
    if (response.ok && result?.Output) {
      autoLoginOutput = {
        userID: result.Output.userID,
        userName: result.Output.userName,
        service: result.Output.service,
      };
    }
  } catch (err) {
    console.error("[autologin] autoLogin request failed", err);
  }


  // check if userID, userName, and service are present


  if (autoLoginOutput?.userID != null && autoLoginOutput?.userName && autoLoginOutput?.service) {
    const backendBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
    const clientInsertionUrl = `${backendBaseUrl}/api/client_insertion`;
    const authToken = xAuth?.startsWith("Bearer ") ? xAuth : xAuth ? `Bearer ${xAuth}` : "";
    const clientName =
      (() => {
        try {
          const hostname = new URL(autoLoginOutput!.service!).hostname;
          return hostname.split(".")[0] || autoLoginOutput!.userName!;
        } catch {
          return autoLoginOutput!.userName!;
        }
      })();
    console.log("[autologin] calling client_insertion", {
      userId: String(autoLoginOutput.userID),
      userName: autoLoginOutput.userName,
      service: autoLoginOutput.service,
      clientName,
      hasToken: !!authToken,
    });




    // call client_insertion BACKEND API

    try {
      const clientRes = await fetch(clientInsertionUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: String(autoLoginOutput.userID),
          userName: autoLoginOutput.userName,
          service: autoLoginOutput.service,
          clientName,
          token: authToken,
        }),
        cache: "no-store",
      });
      const clientResult = await clientRes.json().catch(() => ({}));
      console.log("[autologin] client_insertion result", {
        status: clientRes.status,
        ok: clientRes.ok,
        result: clientResult,
      });
    } catch (err) {
      console.error("[autologin] client_insertion error", err);
    }


    // getBranding: POST with x-auth, userid, body { data: { service } }
    const getBrandingUrl = `${autoLoginOutput.service}/getBranding`;
    const serviceName = new URL(autoLoginOutput.service).hostname.split(".")[0] ?? "";
    //const serviceName = "v4demo";
    const authHeader = xAuth?.startsWith("Bearer ") ? xAuth : xAuth ? `Bearer ${xAuth}` : "";

    let LoginPageClientLogoPath: string | undefined;
    let LoginFooterLogoPath: string | undefined;
    console.log("[branding] getBrandingUrl", getBrandingUrl);
    console.log("[branding] authHeader", authHeader);
    console.log("[branding] serviceName", serviceName);
    console.log("[branding] userId", userId);
    if (authHeader && serviceName) {
      try {
        const brandingResponse = await fetch(getBrandingUrl, {
          method: "POST",
          headers: {
            accept: "*/*",
            "Content-Type": "application/json",
            "x-auth": authHeader,
            userid: String(autoLoginOutput.userID),
          },
          body: JSON.stringify({ data: { service: serviceName } }),
          cache: "no-store",
        });
        const brandingResult = await brandingResponse.json().catch(() => ({}));
        console.log("[autologin] getBranding result", {
          status: brandingResponse.status,
          statusmessage: brandingResult?.Output?.status?.message,
          ok: brandingResponse.ok,
          result: brandingResult,
        });

        LoginPageClientLogoPath = brandingResult?.Output?.data?.[0]?.LoginPageClientLogoPath;
        LoginFooterLogoPath = brandingResult?.Output?.data?.[0]?.LoginFooterLogoPath;
        console.log("[autologin] LoginPageClientLogoPath", LoginPageClientLogoPath);
        console.log("[autologin] LoginFooterLogoPath", LoginFooterLogoPath);

      } catch (err) {
        console.error("[autologin] getBranding error", err);
      }
    }

    const jwt = require("jsonwebtoken");
    // Must match app/verify-token/route.ts so ?data= tokens verify after redirect
    const jwtSecret = process.env.JWT_SECRET ?? "nano_encryption_key";
    console.log("[autologin] signing session JWT", {
      hasJwtSecretFromEnv: Boolean(process.env.JWT_SECRET),
      usingFallbackSecret: !process.env.JWT_SECRET,
    });

    // Bundle everything into one single token (userName, clientName, userId + logos)
    const token = jwt.sign(
      {
        userName: autoLoginOutput.userName,
        clientName: clientName,
        userId: "1",
        email: email,
        cl: LoginPageClientLogoPath ?? "",
        fl: LoginFooterLogoPath ?? "",
      },
      jwtSecret
    );

    console.log("[autologin] signing JWT payload", {
      userName: autoLoginOutput.userName,
      clientName: clientName,
      userId: "1",
      cl: LoginPageClientLogoPath ?? "",
      fl: LoginFooterLogoPath ?? "",
    });

    // Single encoded param — no plain logo URLs in the address bar
    const target = `/?data=${encodeURIComponent(token)}`;
    console.log("[autologin] redirecting to main chat (single encoded token)", { target });
    redirect(target);
  }


  console.log("[autologin] autoLogin output incomplete, redirecting to /?autologin_error=auto_login_failed", {
    autoLoginOutput,
  });
  redirect("/?autologin_error=auto_login_failed");
}