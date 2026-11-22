import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io
import base64
from PIL import Image

# --- CONFIGURACIÓN GENERAL DE PÁGINA ---
st.set_page_config(
    page_title="Mantenimiento - Hospital de Gorbea",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILOS CSS PARA BOTONES Y TARJETAS ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        min-height: 2.8em;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.7rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONSTANTES Y LISTAS DEL HOSPITAL ---
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

ESTADOS_CERRADOS = ["Terminado", "Requiere licitar", "Solicitud rechazada"]

COLUMNAS_BASE = [
    "N° Ticket", "Fecha y Hora", "Correo", "Nombre y Apellido",
    "Unidad de Servicio", "Categorización", "Tipo Solicitud",
    "Descripción", "Archivo Adjunto", "Estado", "Comentarios Mtto",
    "Última Actualización", "Encargado Mtto", "Imagen Base64"
]

COLUMNAS_USUARIOS = ["RUT", "Nombre", "Correo", "Clave"]

# Clave maestra del Administrador SIM
CLAVE_ADMIN_SIM = "sim2026"

# --- FUNCIONES DE UTILIDAD PARA RUT E IMÁGENES ---
def limpiar_rut(rut_str):
    return str(rut_str).replace(".", "").replace("-", "").strip().upper()

def generar_clave_rut(rut_str):
    limpio = limpiar_rut(rut_str)
    return limpio[:4] if len(limpio) >= 4 else limpio

def procesar_imagen_base64(uploaded_file):
    if uploaded_file is None:
        return ""
    if uploaded_file.type not in ["image/png", "image/jpeg", "image/jpg"]:
        return ""
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        # Redimensionar para asegurar compatibilidad con el límite de celda de Google Sheets
        img.thumbnail((650, 650))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=60)
        b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        if len(b64_str) < 48000:
            return b64_str
        return ""
    except Exception:
        return ""

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
        
    client = gspread.authorize(creds)
    spreadsheet = client.open("BD_MANTENIMIENTO_GORBEA")
    sheet_solicitudes = spreadsheet.sheet1
    
    # Buscar o crear pestaña de usuarios de mantenimiento
    try:
        sheet_usuarios = spreadsheet.worksheet("USUARIOS_MTTO")
    except gspread.WorksheetNotFound:
        sheet_usuarios = spreadsheet.add_worksheet(title="USUARIOS_MTTO", rows=100, cols=5)
        sheet_usuarios.update(values=[COLUMNAS_USUARIOS], range_name="A1:D1")
        
    return sheet_solicitudes, sheet_usuarios

sheet, sheet_users = conectar_sheets()

def cargar_solicitudes():
    valores = sheet.get_all_values()
    if not valores:
        sheet.update(values=[COLUMNAS_BASE], range_name="A1:N1")
        return pd.DataFrame(columns=COLUMNAS_BASE)
    
    encabezados_actuales = valores[0]
    if len(encabezados_actuales) < len(COLUMNAS_BASE):
        sheet.update(values=[COLUMNAS_BASE], range_name="A1:N1")
        encabezados_actuales = COLUMNAS_BASE

    filas = []
    for row in valores[1:]:
        row_padded = row + [""] * (len(COLUMNAS_BASE) - len(row))
        filas.append(row_padded[:len(COLUMNAS_BASE)])
        
    return pd.DataFrame(filas, columns=COLUMNAS_BASE)

def cargar_usuarios():
    valores = sheet_users.get_all_values()
    if not valores or len(valores) == 1:
        if not valores:
            sheet_users.update(values=[COLUMNAS_USUARIOS], range_name="A1:D1")
        return pd.DataFrame(columns=COLUMNAS_USUARIOS)
    return pd.DataFrame(valores[1:], columns=COLUMNAS_USUARIOS)

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
    # Exportar todas las columnas excepto la cadena técnica Base64
    df_export = df.drop(columns=["Imagen Base64"], errors="ignore")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Solicitudes_Mtto")
    return output.getvalue()

def obtener_estilo_estado(estado):
    estilos = {
        "Enviado": {"bg": "#FFF3CD", "border": "#FFC107", "badge": "🟡 ENVIADO (Nueva)"},
        "Revisado": {"bg": "#D1ECF1", "border": "#17A2B8", "badge": "🔵 REVISADO"},
        "En ejecución": {"bg": "#FFE5D0", "border": "#FD7E14", "badge": "🟠 EN EJECUCIÓN"},
        "Requiere licitar": {"bg": "#E2E3E5", "border": "#6C757D", "badge": "⚪ REQUIERE LICITAR"},
        "Solicitud rechazada": {"bg": "#F8D7DA", "border": "#DC3545", "badge": "🔴 RECHAZADA"},
        "Terminado": {"bg": "#D4EDDA", "border": "#28A745", "badge": "🟢 TERMINADO"}
    }
    return estilos.get(estado, {"bg": "#F8F9FA", "border": "#CED4DA", "badge": estado})

# --- GESTIÓN DE ESTADOS DE NAVEGACIÓN ---
if "vista_principal" not in st.session_state:
    st.session_state.vista_principal = "solicitudes"
if "subvista_solicitud" not in st.session_state:
    st.session_state.subvista_solicitud = "ingresar"
if "usuario_mtto" not in st.session_state:
    st.session_state.usuario_mtto = None
if "ticket_abierto" not in st.session_state:
    st.session_state.ticket_abierto = None
if "admin_sim_autenticado" not in st.session_state:
    st.session_state.admin_sim_autenticado = False

# --- ENCABEZADO PRINCIPAL ---
st.title("🏥 Sistema de Mantenimiento")
st.caption("Hospital de Gorbea • Gestión Integral de Solicitudes")

# ==============================================================================
# MENÚ PRINCIPAL: SOLO 2 BOTONES PRINCIPALES + ACCESO ADMINISTRADOR SIM
# ==============================================================================
col_nav1, col_nav2, col_nav3 = st.columns([4, 4, 2])
with col_nav1:
    tipo_btn1 = "primary" if st.session_state.vista_principal == "solicitudes" else "secondary"
    if st.button("📝 Solicitudes de Mantenimiento", type=tipo_btn1):
        st.session_state.vista_principal = "solicitudes"
        st.session_state.ticket_abierto = None
        st.rerun()

with col_nav2:
    tipo_btn2 = "primary" if st.session_state.vista_principal == "panel_mtto" else "secondary"
    if st.button("🔧 Panel Personal de Mtto", type=tipo_btn2):
        st.session_state.vista_principal = "panel_mtto"
        st.rerun()

with col_nav3:
    tipo_btn3 = "primary" if st.session_state.vista_principal == "admin_sim" else "secondary"
    if st.button("⚙️ Admin SIM", type=tipo_btn3):
        st.session_state.vista_principal = "admin_sim"
        st.session_state.ticket_abierto = None
        st.rerun()

st.divider()

df = cargar_solicitudes()

# ==============================================================================
# SECCIÓN 1: SOLICITUDES DE MANTENIMIENTO (2 SUB-BOTONES)
# ==============================================================================
if st.session_state.vista_principal == "solicitudes":
    sub1, sub2 = st.columns(2)
    with sub1:
        t_sub1 = "primary" if st.session_state.subvista_solicitud == "ingresar" else "secondary"
        if st.button("➕ Ingresar Solicitud de Mtto", type=t_sub1):
            st.session_state.subvista_solicitud = "ingresar"
            st.rerun()
    with sub2:
        t_sub2 = "primary" if st.session_state.subvista_solicitud == "consultar" else "secondary"
        if st.button("🔍 Consultar Estado de Solicitud", type=t_sub2):
            st.session_state.subvista_solicitud = "consultar"
            st.rerun()

    st.write("")

    # --- SUBVISTA 1A: INGRESAR SOLICITUD ---
    if st.session_state.subvista_solicitud == "ingresar":
        st.subheader("Nueva Solicitud de Mantenimiento")
        with st.form("form_solicitud", clear_on_submit=True):
            correo = st.text_input("Correo Electrónico Institucional o Personal *")
            nombre = st.text_input("Nombre y Apellido *")
            unidad = st.selectbox("Unidad de Servicio *", UNIDADES_SERVICIO)
            categorizacion = st.selectbox("Categorización de Solicitud *", CATEGORIZACIONES)
            tipo = st.selectbox("Tipo de Solicitud *", TIPOS_SOLICITUD)
            descripcion = st.text_area("Describa la Solicitud *", height=120, placeholder="Detalle el problema, ubicación exacta o equipo afectado...")
            archivo = st.file_uploader("Adjuntar Foto o Archivo (Opcional - JPG/PNG se visualizan en panel)", type=["png", "jpg", "jpeg", "pdf"])
            
            enviado = st.form_submit_button("🚀 ENVIAR SOLICITUD", type="primary")
            
            if enviado:
                if not correo.strip() or not nombre.strip() or not descripcion.strip():
                    st.error("⚠️ Complete los campos obligatorios (*): Correo, Nombre y Descripción.")
                else:
                    df_actual = cargar_solicitudes()
                    nuevo_ticket = generar_nuevo_ticket(df_actual)
                    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
                    nombre_archivo = archivo.name if archivo is not None else "Sin archivo"
                    img_b64 = procesar_imagen_base64(archivo)
                    
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
                        fecha_actual,
                        "Sin asignar",
                        img_b64
                    ]
                    sheet.append_row(nueva_fila)
                    st.success("✅ ¡Solicitud registrada con éxito!")
                    st.info(f"🎫 **Su N° de Ticket es: `{nuevo_ticket}`**\n\nGuarde este código para revisar el estado en *Consultar Estado de Solicitud*.")

    # --- SUBVISTA 1B: CONSULTAR ESTADO ---
    elif st.session_state.subvista_solicitud == "consultar":
        st.subheader("Consultar Estado de Solicitudes")
        if st.button("🔄 Actualizar Estados"):
            st.rerun()

        if df.empty:
            st.info("Aún no existen solicitudes registradas.")
        else:
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                filtro_unidad = st.selectbox("Filtrar por Unidad de Servicio:", ["Todas las Unidades"] + UNIDADES_SERVICIO)
            with c_f2:
                buscar_txt = st.text_input("Buscar por N° Ticket o Nombre:", placeholder="Ej: MTTO-0001")

            df_vista = df.copy()
            if filtro_unidad != "Todas las Unidades":
                df_vista = df_vista[df_vista["Unidad de Servicio"] == filtro_unidad]
            if buscar_txt.strip():
                mask = df_vista.apply(lambda r: r.astype(str).str.contains(buscar_txt.strip(), case=False).any(), axis=1)
                df_vista = df_vista[mask]

            st.write(f"Mostrando **{len(df_vista)}** solicitud(es) (más recientes primero):")
            for _, row in df_vista.iloc[::-1].iterrows():
                est_info = obtener_estilo_estado(row["Estado"])
                encargado = row["Encargado Mtto"] if row["Encargado Mtto"] else "Sin asignar"
                with st.expander(f"🎫 {row['N° Ticket']} | {row['Unidad de Servicio']} — {est_info['badge']}"):
                    st.write(f"**Fecha:** {row['Fecha y Hora']} | **Solicitante:** {row['Nombre y Apellido']}")
                    st.write(f"**Prioridad:** {row['Categorización']} | **Tipo:** {row['Tipo Solicitud']}")
                    st.write(f"**Técnico Asignado:** {encargado}")
                    st.write(f"**Descripción:** {row['Descripción']}")
                    st.info(f"💬 **Observaciones Mtto:** {row['Comentarios Mtto']} *(Act: {row['Última Actualización']})*")

# ==============================================================================
# SECCIÓN 2: PANEL PERSONAL DE MANTENIMIENTO
# ==============================================================================
elif st.session_state.vista_principal == "panel_mtto":
    df_usuarios = cargar_usuarios()

    # --- PANTALLA DE LOGIN POR RUT Y CONTRASEÑA ---
    if st.session_state.usuario_mtto is None:
        st.subheader("🔐 Acceso Personal de Mantenimiento")
        if df_usuarios.empty:
            st.warning("⚠️ Aún no hay funcionarios registrados. Solicite al **Administrador SIM** crear los perfiles de mantenimiento.")
        else:
            with st.form("login_mtto"):
                rut_in = st.text_input("RUT (Ej: 12345678-9 o 12.345.678-9)")
                clave_in = st.text_input("Contraseña (Primeros 4 dígitos de su RUT)", type="password")
                btn_login = st.form_submit_button("Ingresar al Panel", type="primary")
                
                if btn_login:
                    rut_limpio = limpiar_rut(rut_in)
                    df_usuarios["RUT_LIMPIO"] = df_usuarios["RUT"].apply(limpiar_rut)
                    match = df_usuarios[(df_usuarios["RUT_LIMPIO"] == rut_limpio) & (df_usuarios["Clave"].astype(str).str.strip() == clave_in.strip())]
                    
                    if not match.empty:
                        st.session_state.usuario_mtto = {
                            "nombre": match.iloc[0]["Nombre"],
                            "rut": match.iloc[0]["RUT"],
                            "correo": match.iloc[0]["Correo"]
                        }
                        st.rerun()
                    else:
                        st.error("❌ RUT o contraseña incorrectos.")

    # --- PANEL INTERNO DEL FUNCIONARIO AUTENTICADO ---
    else:
        usuario_actual = st.session_state.usuario_mtto
        
        # Barra superior de sesión
        col_u1, col_u2, col_u3 = st.columns([5, 3, 2])
        with col_u1:
            st.success(f"👷‍♂️ Funcionario activo: **{usuario_actual['nombre']}** ({usuario_actual['rut']})")
        with col_u2:
            if st.button("🔄 Sincronizar Datos"):
                st.rerun()
        with col_u3:
            if st.button("🚪 Cerrar Sesión"):
                st.session_state.usuario_mtto = None
                st.session_state.ticket_abierto = None
                st.rerun()

        # ======================================================================
        # VISTA DETALLADA DE UNA SOLICITUD AL HACER CLIC EN "ABRIR SOLICITUD"
        # ======================================================================
        if st.session_state.ticket_abierto is not None:
            ticket_id = st.session_state.ticket_abierto
            if st.button("⬅️ Volver al Listado de Solicitudes"):
                st.session_state.ticket_abierto = None
                st.rerun()

            fila_df = df[df["N° Ticket"] == ticket_id]
            if fila_df.empty:
                st.error("No se encontró el ticket seleccionado.")
            else:
                idx_df = fila_df.index[0]
                fila_sheets = idx_df + 2
                datos = df.loc[idx_df]

                # Si la solicitud estaba en estado "Enviado", al abrirla pasa automáticamente a "En ejecución"
                # y queda registrado el nombre del técnico que la abrió.
                if datos["Estado"] == "Enviado":
                    fecha_ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    sheet.update_cell(fila_sheets, 10, "En ejecución")
                    sheet.update_cell(fila_sheets, 12, fecha_ahora)
                    sheet.update_cell(fila_sheets, 13, usuario_actual["nombre"])
                    st.toast(f"Solicitud {ticket_id} tomada por {usuario_actual['nombre']} (En ejecución)")
                    df = cargar_solicitudes()
                    datos = df.loc[idx_df]

                est_info = obtener_estilo_estado(datos["Estado"])
                st.markdown(f"## 🎫 Detalle de Solicitud: `{datos['N° Ticket']}`")
                
                with st.container(border=True):
                    c_d1, c_d2 = st.columns(2)
                    with c_d1:
                        st.write(f"**Estado Actual:** {est_info['badge']}")
                        st.write(f"**Fecha de Ingreso:** {datos['Fecha y Hora']}")
                        st.write(f"**Unidad de Servicio:** {datos['Unidad de Servicio']}")
                        st.write(f"**Categorización:** {datos['Categorización']}")
                    with c_d2:
                        st.write(f"**Tipo de Solicitud:** {datos['Tipo Solicitud']}")
                        st.write(f"**Solicitante:** {datos['Nombre y Apellido']}")
                        st.write(f"**Correo Solicitante:** {datos['Correo']}")
                        st.write(f"**Personal Asignado:** **{datos['Encargado Mtto']}**")

                    st.divider()
                    st.markdown("**📝 Descripción del Problema:**")
                    st.write(datos["Descripción"])

                    # Visualización de Imagen Adjunta
                    st.markdown(f"**📎 Archivo Adjunto:** `{datos['Archivo Adjunto']}`")
                    if datos["Imagen Base64"] and len(str(datos["Imagen Base64"])) > 20:
                        try:
                            img_bytes = base64.b64decode(datos["Imagen Base64"])
                            st.image(img_bytes, caption=datos["Archivo Adjunto"], width=480)
                        except Exception:
                            st.caption("No se pudo renderizar la vista previa de la imagen.")
                    elif datos["Archivo Adjunto"] != "Sin archivo":
                        st.info("El archivo adjunto no es una imagen compatible para vista previa directa (ej. PDF) o supera el tamaño de vista previa.")

                # Formulario de Gestión y Cambio de Estado
                st.markdown("### ✏️ Actualizar Estado y Observaciones")
                with st.form("form_gestion_detalle"):
                    idx_est = ESTADOS_MTTO.index(datos["Estado"]) if datos["Estado"] in ESTADOS_MTTO else 0
                    nuevo_estado = st.selectbox("Estado de la Solicitud:", ESTADOS_MTTO, index=idx_est)
                    observaciones = st.text_area(
                        "Observaciones de Mantenimiento / Motivo de rechazo:",
                        value=datos["Comentarios Mtto"],
                        height=110
                    )
                    asignar_a_mi = st.checkbox(f"Registrar a mi nombre ({usuario_actual['nombre']}) como responsable", value=True)
                    
                    guardar_btn = st.form_submit_button("💾 Guardar Cambios en la Solicitud", type="primary")
                    
                    if guardar_btn:
                        if nuevo_estado == "Solicitud rechazada" and (not observaciones.strip() or observaciones.strip() == "Pendiente de revisión por Mantenimiento."):
                            st.error("⚠️ Debe escribir obligatoriamente el motivo en Observaciones para rechazar una solicitud.")
                        else:
                            fecha_act = datetime.now().strftime("%d/%m/%Y %H:%M")
                            responsable_final = usuario_actual["nombre"] if asignar_a_mi or not datos["Encargado Mtto"] or datos["Encargado Mtto"] == "Sin asignar" else datos["Encargado Mtto"]
                            
                            sheet.update_cell(fila_sheets, 10, nuevo_estado)
                            sheet.update_cell(fila_sheets, 11, observaciones.strip())
                            sheet.update_cell(fila_sheets, 12, fecha_act)
                            sheet.update_cell(fila_sheets, 13, responsable_final)
                            
                            st.success(f"✅ Solicitud {ticket_id} actualizada correctamente.")
                            if nuevo_estado in ESTADOS_CERRADOS:
                                st.info("Esta solicitud pasó a estado cerrado y salió de la bandeja activa (permanece en el Excel).")
                                st.session_state.ticket_abierto = None
                            st.rerun()

        # ======================================================================
        # VISTA PRINCIPAL DEL PANEL: ENCABEZADO RESUMEN + BANDEJA ACTIVA
        # ======================================================================
        else:
            # --- 4. ENCABEZADO: CUADRO RESUMEN Y TERMINADAS POR FUNCIONARIO ---
            st.markdown("### 📊 Resumen General de Solicitudes")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Historial", len(df))
            m2.metric("🟡 Enviadas", len(df[df["Estado"] == "Enviado"]))
            m3.metric("🔵 Revisadas", len(df[df["Estado"] == "Revisado"]))
            m4.metric("🟠 En Ejecución", len(df[df["Estado"] == "En ejecución"]))
            m5.metric("🟢 Terminadas", len(df[df["Estado"] == "Terminado"]))

            col_res1, col_res2 = st.columns([3, 2])
            with col_res1:
                st.markdown("**🏆 Solicitudes Terminadas por Personal de Mantenimiento:**")
                df_term = df[df["Estado"] == "Terminado"]
                if df_term.empty:
                    st.caption("Aún no hay solicitudes terminadas registradas.")
                else:
                    conteo_tecnicos = df_term["Encargado Mtto"].replace("", "Sin asignar").value_counts().reset_index()
                    conteo_tecnicos.columns = ["Personal de Mantenimiento", "Solicitudes Terminadas"]
                    st.dataframe(conteo_tecnicos, use_container_width=True, hide_index=True)

            with col_res2:
                st.markdown("**📥 Exportación Base de Datos:**")
                st.write("Incluye historial completo, cerradas y técnico responsable.")
                if not df.empty:
                    excel_bytes = convertir_a_excel(df)
                    st.download_button(
                        label="📥 Descargar Registro Completo (.xlsx)",
                        data=excel_bytes,
                        file_name=f"BD_Mantenimiento_Gorbea_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            st.divider()

            # --- 6. BANDEJA DE SOLICITUDES ACTIVAS (EXCLUYE TERMINADO, LICITAR, RECHAZADO) ---
            st.markdown("### 📋 Bandeja de Solicitudes Activas (Más recientes primero)")
            st.caption("Las solicitudes en estado *Terminado*, *Requiere licitar* o *Solicitud rechazada* salen automáticamente de esta vista y quedan respaldadas en el Excel.")

            df_activas = df[~df["Estado"].isin(ESTADOS_CERRADOS)].copy()

            if df_activas.empty:
                st.success("🎉 ¡Excelente! No hay solicitudes pendientes en la bandeja activa.")
            else:
                # Ordenar de la más reciente a la más antigua
                for _, row in df_activas.iloc[::-1].iterrows():
                    est = obtener_estilo_estado(row["Estado"])
                    encargado = row["Encargado Mtto"] if row["Encargado Mtto"] and row["Encargado Mtto"] != "Sin asignar" else "Sin asignar"
                    
                    st.markdown(f"""
                        <div style="background-color:{est['bg']}; border-left: 6px solid {est['border']}; padding: 12px 16px; border-radius: 6px; margin-bottom: 6px; color: #111;">
                            <strong>🎫 {row['N° Ticket']}</strong> &nbsp;|&nbsp; <strong>{row['Unidad de Servicio']}</strong> &nbsp;|&nbsp; <span>{est['badge']}</span><br>
                            <small>📅 <b>Ingreso:</b> {row['Fecha y Hora']} &nbsp;|&nbsp; ⚡ <b>Prioridad:</b> {row['Categorización']} &nbsp;|&nbsp; 🔧 <b>Tipo:</b> {row['Tipo Solicitud']}</small><br>
                            <small>👷‍♂️ <b>Personal asignado:</b> {encargado} &nbsp;|&nbsp; 👤 <b>Solicita:</b> {row['Nombre y Apellido']}</small><br>
                            <div style="margin-top:4px; font-size:0.92em;">📝 {row['Descripción'][:140]}{'...' if len(row['Descripción']) > 140 else ''}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"📂 Abrir Solicitud {row['N° Ticket']} (Ver detalle, imagen y gestionar)", key=f"open_{row['N° Ticket']}"):
                        st.session_state.ticket_abierto = row["N° Ticket"]
                        st.rerun()
                    st.write("")

# ==============================================================================
# SECCIÓN 9: ADMINISTRADOR SIM (GESTIÓN DE PERFILES DE MANTENIMIENTO)
# ==============================================================================
elif st.session_state.vista_principal == "admin_sim":
    st.subheader("⚙️ Administrador SIM — Gestión de Personal de Mantenimiento")
    
    if not st.session_state.admin_sim_autenticado:
        with st.form("login_admin_sim"):
            clave_sim = st.text_input("Ingrese Clave de Administrador SIM:", type="password")
            if st.form_submit_button("Acceder", type="primary"):
                if clave_sim == CLAVE_ADMIN_SIM:
                    st.session_state.admin_sim_autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta.")
    else:
        if st.button("🔒 Salir de Administrador SIM"):
            st.session_state.admin_sim_autenticado = False
            st.rerun()

        df_usuarios = cargar_usuarios()

        c_sim1, c_sim2 = st.columns(2)
        with c_sim1:
            st.markdown("### ➕ Agregar Personal de Mantenimiento")
            with st.form("form_nuevo_tecnico", clear_on_submit=True):
                nombre_tec = st.text_input("Nombre Completo del Funcionario *")
                rut_tec = st.text_input("RUT (Ej: 15432198-K) *")
                correo_tec = st.text_input("Correo Electrónico *")
                
                if st.form_submit_button("💾 Crear Perfil", type="primary"):
                    if not nombre_tec.strip() or not rut_tec.strip() or not correo_tec.strip():
                        st.error("⚠️ Todos los campos son obligatorios.")
                    else:
                        rut_norm = limpiar_rut(rut_tec)
                        clave_auto = generar_clave_rut(rut_norm)
                        if not df_usuarios.empty and rut_norm in df_usuarios["RUT"].apply(limpiar_rut).values:
                            st.error("⚠️ Ya existe un funcionario registrado con ese RUT.")
                        else:
                            sheet_users.append_row([rut_norm, nombre_tec.strip(), correo_tec.strip(), clave_auto])
                            st.success(f"✅ Perfil creado para **{nombre_tec.strip()}**.")
                            st.info(f"🔑 **Credenciales asignadas:**\n- Usuario (RUT): `{rut_norm}`\n- Contraseña (4 primeros dígitos): `{clave_auto}`")
                            st.rerun()

        with c_sim2:
            st.markdown("### 🗑️ Eliminar Perfil Existente")
            if df_usuarios.empty:
                st.info("No hay funcionarios registrados para eliminar.")
            else:
                opciones_del = [f"{r['RUT']} | {r['Nombre']} ({r['Correo']})" for _, r in df_usuarios.iterrows()]
                seleccion_del = st.selectbox("Seleccione funcionario a eliminar:", opciones_del)
                if st.button("🗑️ Eliminar Perfil Seleccionado"):
                    rut_eliminar = seleccion_del.split(" | ")[0]
                    idx_user = df_usuarios[df_usuarios["RUT"] == rut_eliminar].index[0]
                    sheet_users.delete_rows(int(idx_user) + 2)
                    st.success("✅ Perfil eliminado correctamente.")
                    st.rerun()

        st.divider()
        st.markdown("### 👥 Nómina Actual de Personal de Mantenimiento")
        if df_usuarios.empty:
            st.warning("La nómina está vacía. Agregue al primer técnico en el formulario superior.")
        else:
            st.dataframe(df_usuarios, use_container_width=True, hide_index=True)