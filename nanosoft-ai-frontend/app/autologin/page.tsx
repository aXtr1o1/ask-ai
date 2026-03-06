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

export default async function AutoLoginPage({ searchParams }: AutoLoginPageProps) {
  const hdrs = await headers();
  const params = await searchParams;

  // Support token/userId from URL (e.g. from login page redirect) or from headers
  const tokenFromUrl = getParam(params, "token");
  const userIdFromUrl = getParam(params, "userId");
  const xAuth = tokenFromUrl
    ? `Bearer ${tokenFromUrl}`
    : (hdrs.get("x-auth") ?? "");
  const userId = userIdFromUrl ?? hdrs.get("userid") ?? "";
  const rawToken = xAuth?.startsWith("Bearer ") ? xAuth.slice(7) : xAuth ?? "";
  const authHeader = xAuth?.startsWith("Bearer ") ? xAuth : `Bearer ${rawToken}`;

  const rawP1 = params?.p1;
  const p1 =
    typeof rawP1 === "string"
      ? rawP1
      : Array.isArray(rawP1)
      ? rawP1[0]
      : undefined;

  let userNameFromApi: string | undefined;

  if ((tokenFromUrl && userIdFromUrl) || (xAuth && userId)) {
    const apiBaseUrl =
      process.env.NEXT_PUBLIC_SMARTFM_API_BASE_URL ||
      "https://v4demo.smartfm.cloud";
    const apiUrl = `${apiBaseUrl}/askmeapi/autoLogin?p1=${encodeURIComponent(
      p1 || ""
    )}`;

    try {
      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          accept: "*/*",
          "x-auth": authHeader,
          userid: userId,
        },
        cache: "no-store",
      });

      const apiResult = await response.json();
      const service = apiResult?.Output?.service;
      const userName = apiResult?.Output?.userName as string | undefined;
      const userIdFromApi = apiResult?.Output?.userID as number | undefined;
      console.log("API status:", response.status);
      console.log("API response:", apiResult);
      console.log("service", service);

      if (response.ok && userName) {
        console.log("AutoLogin API success");
        userNameFromApi = userName;

        // Call backend to check/store client data (best-effort)
        try {
          const backendBaseUrl =
            process.env.NEXT_PUBLIC_API_BASE_URL || "";
          const clientInsertionUrl = `${backendBaseUrl}/api/client_insertion`;

          const clientResponse = await fetch(clientInsertionUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              userId: String(userIdFromApi),
              userName: userNameFromApi,
              service,
              token: rawToken,
            }),
            cache: "no-store",
          });

          
          const clientResult = await clientResponse.json();
          console.log("client_insertion result:", clientResult);
        } catch (err) {
          console.error("client_insertion error:", err);
        }
      } else {
        console.log("AutoLogin API failed");
      }
    } catch (err) {
      console.error("AutoLogin API error:", err);
    }
  }

  if (userNameFromApi) {
    redirect(`/?userName=${encodeURIComponent(userNameFromApi)}`);
  }

  redirect(`/login?p1=${encodeURIComponent(p1 || "")}`);
  console.log("redirecting to login page");
}
