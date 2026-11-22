import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io

# Configuración optimizada para celular y web
st.set_page_config(
    page_title="Mantenimiento - Hospital de Gorbea",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS para mejorar botones y visualización en pantallas de celular
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- LISTAS EXACTAS DEL FORMULARIO ---
UNIDADES_SERVICIO = [
    "URGENCIA", "MATERNO INFANTIL (URGENCIA)", "SALA PROCEDIMIENTOS (CURACIONES)",
    "POLICLÍNICO", "BODEGA GENERAL", "BODEGA FÁRMACOS / IM", "FARMACIA", "SOME",
    "CONTABILIDAD", "OFICINA DE PERSONAL", "DIRECCIÓN", "SUBDIRECCIÓN ADMINISTRATIVA",
    "ABASTECIMIENTO", "HOSPITALIZACIÓN", "SUBDIRECCION MÉDICA", "MOVILIZACIÓN",
    "DENTAL", "MATRONAS POLICLÍNICO", "LABORATORIO", "RAYOS", "UCA", "KINESIOLOGÍA",
    "TERAPEUTA OCUPACIONAL", "RESIDENCIA MÉDICOS", "LAVANDERÍA", "SALA MULTIUSO",
    "OFICINA DE CALIDAD", "NUTRICIONISTA", "VACUNATORIO", "PREVENCION DE RIESGOS",
    "SALA DISTRIBUCION PNAC", "ESTERILIZACIÓN", "BODEGA PNAC", "AMULDUNGUN",
    "EMPRESA DE ASEO", "EMPRESA DE SEGURIDAD"
]

CATEGORIZACIONES = [
    "URGENTE (Plazo: 1 día)",
    "IMPRESCINDIBLE (Plazo: 5 días)",
    "PRIORIDAD MEDIA (Plazo: 15 días)",
    "PRIORIDAD BAJA (Plazo: 30 días)"
]

TIPOS_SOLICITUD = [
    "ELECTRICIDAD", "GASFITERIA", "REPARACIONES ESTRUCTURALES", "INFORMATICA",
    "FILTRACIONES", "MANTECION DE EQUIPOS", "EQUIPAMIENTO MEDICO", "OTROS"
]

ESTADOS_MTTO = [
    "Enviado",
    "Revisado",
    "En ejecución",
    "Requiere licitar",
    "Solicitud rechazada",
    "Terminado"
]

COLUMNAS_BASE = [
    "N° Ticket", "Fecha y Hora", "Correo", "Nombre y Apellido",
    "Unidad de Servicio", "Categorización", "Tipo Solicitud",
    "Descripción", "Archivo Adjunto", "Estado", "Comentarios Mtto",
    "Última Actualización"
]

# Clave de acceso para el personal de mantenimiento
CLAVE_MANTENIMIENTO = "gorbea2026"

# --- CONEXIÓN A LA PLANILLA DE GOOGLE SHEETS (LOCAL Y NUBE) ---
@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    # Si está en la nube usa Secrets; si está en tu PC usa credenciales.json
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        
    client = gspread.authorize(creds)
    sheet = client.open("BD_MANTENIMIENTO_GORBEA").sheet1
    return sheet

sheet = conectar_sheets()

def inicializar_y_cargar():
    valores = sheet.get_all_values()
    if not valores or len(valores[0]) < len(COLUMNAS_BASE):
        sheet.update(values=[COLUMNAS_BASE], range_name="A1:L1")
        return pd.DataFrame(columns=COLUMNAS_BASE)
    
    df = pd.DataFrame(valores[1:], columns=valores[0][:len(COLUMNAS_BASE)])
    return df

def generar_nuevo_ticket(df):
    if df.empty:
        return "MTTO-0001"
    numeros = []
    for t in df["N° Ticket"]:
        if "-" in str(t):
            try:
                numeros.append(int(str(t).split("-")[1]))
            except ValueError:
                pass
    siguiente = max(numeros) + 1 if numeros else len(df) + 1
    return f"MTTO-{siguiente:04d}"

def convertir_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Solicitudes_Mtto")
    return output.getvalue()

# --- INTERFAZ PRINCIPAL ---
st.title("🏥 Sistema de Mantenimiento")
st.caption("Hospital de Gorbea • Gestión de Solicitudes")

df = inicializar_y_cargar()

# Navegación superior clara para móvil y web
perfil = st.radio(
    "Seleccione su perfil:",
    ["📝 Solicitar Mantenimiento", "🔍 Historial Jefe de Servicio", "🔧 Panel Personal de Mantenimiento"],
    horizontal=True
)

st.divider()

# ==============================================================================
# 1. FORMULARIO DE NUEVA SOLICITUD (JEFE DE SERVICIO / FUNCIONARIO)
# ==============================================================================
if perfil == "📝 Solicitar Mantenimiento":
    st.subheader("Nueva Solicitud de Mantenimiento")
    
    with st.form("form_solicitud", clear_on_submit=True):
        correo = st.text_input("Correo Electrónico Institucional o Personal *")
        nombre = st.text_input("Nombre y Apellido *")
        unidad = st.selectbox("Unidad de Servicio *", UNIDADES_SERVICIO)
        categorizacion = st.selectbox("Categorización de Solicitud *", CATEGORIZACIONES)
        tipo = st.selectbox("Tipo de Solicitud *", TIPOS_SOLICITUD)
        descripcion = st.text_area("Describa la Solicitud *", height=120, placeholder="Detalle el problema, ubicación exacta o equipo afectado...")
        archivo = st.file_uploader("Adjuntar Archivo o Foto (Opcional)", type=["png", "jpg", "jpeg", "pdf"])
        
        enviado = st.form_submit_button("🚀 ENVIAR SOLICITUD", type="primary")
        
        if enviado:
            if not correo.strip() or not nombre.strip() or not descripcion.strip():
                st.error("⚠️ Por favor complete los campos obligatorios marcados con (*): Correo, Nombre y Descripción.")
            else:
                df_actual = inicializar_y_cargar()
                nuevo_ticket = generar_nuevo_ticket(df_actual)
                fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
                nombre_archivo = archivo.name if archivo is not None else "Sin archivo"
                
                nueva_fila = [
                    nuevo_ticket,
                    fecha_actual,
                    correo.strip(),
                    nombre.strip(),
                    unidad,
                    categorizacion,
                    tipo,
                    descripcion.strip(),
                    nombre_archivo,
                    "Enviado",
                    "Pendiente de revisión por Mantenimiento.",
                    fecha_actual
                ]
                
                sheet.append_row(nueva_fila)
                st.success("✅ ¡Solicitud registrada con éxito!")
                st.info(f"🎫 **Su N° de Ticket es: `{nuevo_ticket}`**\n\nGuarde este número para consultar el avance en la pestaña *Historial Jefe de Servicio*.")

# ==============================================================================
# 2. HISTORIAL Y CONSULTA PARA JEFE DE SERVICIO
# ==============================================================================
elif perfil == "🔍 Historial Jefe de Servicio":
    st.subheader("Historial y Estado de Solicitudes")
    
    if st.button("🔄 Actualizar Estados"):
        st.rerun()
        
    if df.empty:
        st.info("Aún no hay solicitudes registradas en el sistema.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            filtro_unidad = st.selectbox("Filtrar por Unidad de Servicio:", ["Todas las Unidades"] + UNIDADES_SERVICIO)
        with col2:
            buscar_ticket = st.text_input("Buscar por N° Ticket o Nombre:", placeholder="Ej: MTTO-0001")
            
        df_vista = df.copy()
        if filtro_unidad != "Todas las Unidades":
            df_vista = df_vista[df_vista["Unidad de Servicio"] == filtro_unidad]
        if buscar_ticket.strip():
            mask = df_vista.apply(lambda r: r.astype(str).str.contains(buscar_ticket.strip(), case=False).any(), axis=1)
            df_vista = df_vista[mask]
            
        st.write(f"Mostrando **{len(df_vista)}** solicitud(es):")
        
        for _, row in df_vista.iloc[::-1].iterrows():
            with st.expander(f"🎫 {row['N° Ticket']} | {row['Unidad de Servicio']} — Estado: **{row['Estado']}**"):
                st.write(f"**Fecha:** {row['Fecha y Hora']} | **Solicitante:** {row['Nombre y Apellido']}")
                st.write(f"**Categoría:** {row['Categorización']} | **Tipo:** {row['Tipo Solicitud']}")
                st.write(f"**Descripción:** {row['Descripción']}")
                st.info(f"💬 **Respuesta Mantenimiento:** {row['Comentarios Mtto']} *(Act: {row['Última Actualización']})*")

# ==============================================================================
# 3. PANEL DE GESTIÓN PARA PERSONAL DE MANTENIMIENTO
# ==============================================================================
elif perfil == "🔧 Panel Personal de Mantenimiento":
    st.subheader("Panel de Control - Equipo de Mantenimiento")
    
    clave_ingresada = st.text_input("Ingrese clave de acceso de Mantenimiento:", type="password")
    
    if clave_ingresada != CLAVE_MANTENIMIENTO:
        if clave_ingresada != "":
            st.error("❌ Clave incorrecta.")
        st.info("🔒 Este módulo es exclusivo para el personal de Mantenimiento del Hospital de Gorbea.")
    else:
        if st.button("🔄 Sincronizar Base de Datos"):
            st.rerun()
            
        if df.empty:
            st.warning("No existen solicitudes en la base de datos.")
        else:
            # --- NOTIFICACIÓN DE NUEVAS SOLICITUDES ---
            nuevas = df[df["Estado"] == "Enviado"]
            if not nuevas.empty:
                st.warning(f"🔔 **¡ATENCIÓN! Tienes {len(nuevas)} solicitud(es) nueva(s) en estado 'Enviado' esperando revisión.**")
            else:
                st.success("✅ No hay solicitudes nuevas pendientes de revisión inicial.")

            # --- RESUMEN ESTADÍSTICO Y GRÁFICO ---
            st.markdown("### 📊 Resumen Estadístico")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Solicitudes", len(df))
            c2.metric("Nuevas (Enviado)", len(df[df["Estado"] == "Enviado"]))
            c3.metric("En Ejecución / Revisión", len(df[df["Estado"].isin(["Revisado", "En ejecución", "Requiere licitar"])]))
            c4.metric("Terminadas", len(df[df["Estado"] == "Terminado"]))
            
            conteo_estados = df["Estado"].value_counts().reindex(ESTADOS_MTTO, fill_value=0)
            st.bar_chart(conteo_estados)

            # --- DESCARGA EN EXCEL ---
            excel_bytes = convertir_a_excel(df)
            st.download_button(
                label="📥 Descargar Base de Datos Completa en Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"BD_Mantenimiento_Gorbea_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.divider()

            # --- GESTIÓN Y ACTUALIZACIÓN DE TICKETS ---
            st.markdown("### ✏️ Gestionar Solicitud")
            
            filtro_gestion = st.selectbox("Filtrar lista de gestión por estado:", ["Todos"] + ESTADOS_MTTO)
            df_gestion = df