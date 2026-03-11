import LoginClient from "./LoginClient";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = (await searchParams) ?? {};
  const rawP1 = resolved["p1"];
  const p1 = typeof rawP1 === "string" ? rawP1 : "";

  return <LoginClient p1={p1} />;
}