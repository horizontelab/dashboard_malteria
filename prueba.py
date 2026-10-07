from google.oauth2 import service_account
from googleapiclient.discovery import build

# ID de la planilla: es la parte larga de la URL, entre /d/ y /edit
SHEET_ID = "1V7r0Vs_6FNtKQdbRBtKlsIQ-fmEyU3e3h-QD2t69cgo"

# 1) Nos autenticamos con la cuenta de servicio
creds = service_account.Credentials.from_service_account_file(
    "credenciales.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
sheets = build("sheets", "v4", credentials=creds)

# 2) Leemos la hoja RESULTADOS con los numeros "crudos"
resp = sheets.spreadsheets().values().get(
    spreadsheetId=SHEET_ID,
    range="RESULTADOS!A1:N40",
    valueRenderOption="UNFORMATTED_VALUE",
).execute()
filas = resp.get("values", [])

# 3) Buscamos la fila cuya columna A dice "INGRESOS"
for fila in filas:
    if fila and str(fila[0]).strip().upper() == "INGRESOS":
        meses = fila[1:13]  # columnas B a M = enero a diciembre
        cargados = [v for v in meses if isinstance(v, (int, float)) and v > 0]
        print("Ingresos por mes:", cargados)
        print("Acumulado del anio: $", round(sum(cargados)))
