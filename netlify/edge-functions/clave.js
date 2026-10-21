// Pide usuario y clave antes de mostrar el dashboard (los datos van adentro del HTML).
export default async (request, context) => {
  const usuario = Netlify.env.get("DASHBOARD_USUARIO") || "socias";
  const clave = Netlify.env.get("DASHBOARD_CLAVE");
  if (!clave) {                                   // sin clave configurada no se muestra nada
    return new Response("Falta configurar DASHBOARD_CLAVE en Netlify.", { status: 503 });
  }
  const cabecera = request.headers.get("authorization") || "";
  if (cabecera.startsWith("Basic ")) {
    try {
      const texto = atob(cabecera.slice(6));
      const i = texto.indexOf(":");
      if (texto.slice(0, i) === usuario && texto.slice(i + 1) === clave) {
        return context.next();
      }
    } catch {}
  }
  return new Response("Clave requerida", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Dashboard Ovunque + Amola"' },
  });
};
