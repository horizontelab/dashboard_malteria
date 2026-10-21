// Todos los dias a las 6:00 de Argentina (9:00 UTC) dispara un deploy nuevo,
// que vuelve a leer las planillas. BUILD_HOOK_URL sale de Netlify > Build hooks.
export default async () => {
  const hook = Netlify.env.get("BUILD_HOOK_URL");
  if (!hook) {
    console.log("Falta BUILD_HOOK_URL");
    return;
  }
  const r = await fetch(hook, { method: "POST" });
  console.log("Build hook:", r.status);
};

export const config = { schedule: "0 9 * * *" };
