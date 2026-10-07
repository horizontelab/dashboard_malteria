"""Conexion con Google Sheets. Todos los bloques usan estas dos funciones."""
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def conectar():
    """Devuelve un cliente de la API de Sheets autenticado con la cuenta de servicio."""
    creds = service_account.Credentials.from_service_account_file(
        "credenciales.json", scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def leer_hoja(sheets, sheet_id, hoja):
    """Devuelve todas las filas de una pestaña como lista de listas, con numeros crudos."""
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{hoja}'",          # solo el nombre = la hoja completa
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    return resp.get("values", [])


def pestanias(sheets, sheet_id):
    """Nombres de todas las pestanias de una planilla."""
    meta = sheets.spreadsheets().get(
        spreadsheetId=sheet_id, fields="sheets.properties.title").execute()
    return [s["properties"]["title"] for s in meta["sheets"]]


def leer_varias(sheets, sheet_id, hojas):
    """Lee varias pestanias en UNA sola consulta (cuida el limite de la API)."""
    if not hojas:
        return {}
    resp = sheets.spreadsheets().values().batchGet(
        spreadsheetId=sheet_id,
        ranges=["'" + h.replace("'", "''") + "'" for h in hojas],
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    return {h: vr.get("values", []) for h, vr in zip(hojas, resp.get("valueRanges", []))}
