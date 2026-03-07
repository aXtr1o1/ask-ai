export async function POST(req: Request) {
    const body = await req.json();
  
    const response = await fetch(
      "https://v4demo.smartfm.cloud/askmeapi/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    );
  
    const data = await response.json();
  
    return Response.json(data);
  }