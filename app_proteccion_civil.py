
import os
import re
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage

st.set_page_config(
    page_title="Digitalización Protección Civil DIF",
    page_icon="🚒",
    layout="wide"
)

BASE_DIR = Path("proteccion_civil_digital")
ARCHIVOS_DIR = BASE_DIR / "archivos"
DB_PATH = BASE_DIR / "proteccion_civil.db"
COLECCION_FIRESTORE = "proteccion_civil_digital"

BASE_DIR.mkdir(exist_ok=True)
ARCHIVOS_DIR.mkdir(exist_ok=True)

CARPETAS_PRINCIPALES = [
    "LICENCIA DE USO DE SUELO",
    "IMPACTO AMBIENTAL",
    "FUNCIONAMIENTO",
    "DICTAMEN DE SEGURIDAD",
    "COESPRISSON",
]

CENTROS = [
    "CASA DE ABUELOS APACHE",
    "CASA DE ABUELOS CHOYAL",
    "CASA DE ABUELOS LOS OLIVOS",
    "CASA DE ABUELOS MARIACHI",
    "CASA DE ABUELOS OLIVARES",
    "CASA DE ABUELOS RANCHITO",
    "CASA DE ABUELOS POBLADO MIGUEL ALEMÁN",
    "COMEDOR COMUNITARIO P.M.A.",
    "CASA GALILEA",
    "DESAYUNOS ESCOLARES P.M.A. (CONTRATO ARRENDAMIENTO)",
    "DESAYUNOS ESCOLARES ZONA SUR",
    "DESAYUNOS ESCOLARES ZONA NORTE (CONTRATO ARRENDAMIENTO)",
    "CENTRO ASISTENCIAL DE DESARROLLO INFANTIL (CADI)",
    "ESTANCIA INFANTIL MANUEL GÓMEZ MORÍN",
    "ESTANCIA INFANTIL MIGUEL HIDALGO",
    "DIRECCIÓN DISCAPACIDAD MUNICIPAL",
    "UBR HERMOSILLO",
    "UBR POBLADO MIGUEL ALEMÁN",
    "UBR KINO",
    "PROCURADURÍA HERMOSILLO",
    "SUBPROCURADURÍA PMA",
    "SUBPROCURADURÍA BAHÍA DE KINO",
    "CIF NORTE",
    "CIF SUR",
    "CIF MINITAS",
    "OFICINAS GENERALES DIF HERMOSILLO",
]

USUARIOS = {
    "admin": {"password": "1234", "rol": "Administrador"},
    "captura": {"password": "1234", "rol": "Capturista"},
    "consulta": {"password": "1234", "rol": "Consulta"},
}

st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(8,123,117,0.18), transparent 30%),
        radial-gradient(circle at bottom right, rgba(233,78,27,0.22), transparent 34%),
        linear-gradient(135deg, #EEF8F5 0%, #FFF7E7 50%, #F8C2A5 100%);
}
.block-container { padding-top: 25px; }
.header-card {
    background: linear-gradient(135deg, rgba(219,246,241,0.98), rgba(255,242,216,0.98));
    padding: 28px;
    border-radius: 24px;
    box-shadow: 0px 8px 24px rgba(0,0,0,0.12);
    text-align: center;
    margin-bottom: 22px;
}
.header-card h1 {
    color: #087B75;
    font-weight: 900;
    margin-bottom: 5px;
}
.card {
    background: rgba(255,255,255,0.88);
    padding: 22px;
    border-radius: 18px;
    box-shadow: 0px 5px 15px rgba(0,0,0,0.09);
    border-left: 7px solid #087B75;
    margin-bottom: 18px;
}
.stButton > button {
    background: linear-gradient(90deg, #E94E1B, #F2B233);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 12px;
    font-weight: 900;
    width: 100%;
}
.stDownloadButton > button {
    background: linear-gradient(90deg, #087B75, #14A39A);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 12px;
    font-weight: 900;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)


def conectar_firebase():
    try:
        if not firebase_admin._apps:
            if "firebase" in st.secrets:
                fb = dict(st.secrets["firebase"])
                project_id = fb.get("project_id", "dif-hermosillo")
                bucket_name = fb.get("storage_bucket", f"{project_id}.appspot.com")
                firebase_admin.initialize_app(
                    credentials.Certificate(fb),
                    {"storageBucket": bucket_name}
                )
            else:
                archivos_json = list(Path(".").glob("*firebase-adminsdk*.json"))
                if not archivos_json:
                    return None, None, "No se encontró [firebase] en Secrets ni archivo JSON local."
                firebase_admin.initialize_app(
                    credentials.Certificate(str(archivos_json[0])),
                    {"storageBucket": "dif-hermosillo.appspot.com"}
                )

        return firestore.client(), storage.bucket(), None
    except Exception as e:
        return None, None, str(e)


db_firebase, bucket_firebase, error_firebase = conectar_firebase()


def firebase_disponible():
    return db_firebase is not None


def storage_disponible():
    return bucket_firebase is not None


def conectar_local():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def inicializar_db():
    con = conectar_local()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firebase_id TEXT,
            fecha_captura TEXT,
            carpeta_principal TEXT,
            centro TEXT,
            nombre_hoja TEXT,
            folio TEXT,
            fecha_documento TEXT,
            observaciones TEXT,
            palabras_clave TEXT,
            archivo_path TEXT,
            archivo_url TEXT,
            archivo_storage_path TEXT,
            usuario TEXT
        )
    """)
    con.commit()
    con.close()


inicializar_db()


def login():
    if "logueado_pc" not in st.session_state:
        st.session_state.logueado_pc = False
        st.session_state.usuario_pc = ""
        st.session_state.rol_pc = ""

    if st.session_state.logueado_pc:
        return True

    st.markdown("""
    <div class="header-card">
        <h1>🚒 Sistema de Digitalización Protección Civil</h1>
        <p>DIF Hermosillo · Acceso de usuarios</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    usuario = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("🔐 Entrar"):
        if usuario in USUARIOS and password == USUARIOS[usuario]["password"]:
            st.session_state.logueado_pc = True
            st.session_state.usuario_pc = usuario
            st.session_state.rol_pc = USUARIOS[usuario]["rol"]
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    st.info("Usuarios iniciales: admin / captura / consulta. Contraseña: 1234")
    st.markdown("</div>", unsafe_allow_html=True)
    return False


if not login():
    st.stop()


def limpiar_nombre_archivo(texto):
    texto = str(texto).upper().strip()
    reemplazos = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
        "á": "A", "é": "E", "í": "I", "ó": "O", "ú": "U", "ñ": "N"
    }
    for a, b in reemplazos.items():
        texto = texto.replace(a, b)
    texto = re.sub(r"[^A-Z0-9_\- ]", "", texto)
    texto = texto.replace(" ", "_")
    return texto[:80] if texto else "DOCUMENTO"


def generar_nombre_archivo(original_name, carpeta, centro, folio, nombre_hoja):
    extension = Path(original_name).suffix.lower()
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta_limpia = limpiar_nombre_archivo(carpeta)
    centro_limpio = limpiar_nombre_archivo(centro)
    folio_limpio = limpiar_nombre_archivo(folio) if folio else "SIN_FOLIO"
    hoja_limpia = limpiar_nombre_archivo(nombre_hoja)
    nombre_final = f"{fecha}_{folio_limpio}_{hoja_limpia}{extension}"
    ruta_relativa = f"{carpeta_limpia}/{centro_limpio}/{nombre_final}"
    return ruta_relativa


def guardar_archivo_local(uploaded_file, ruta_relativa):
    destino = ARCHIVOS_DIR / ruta_relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    uploaded_file.seek(0)
    with open(destino, "wb") as f:
        f.write(uploaded_file.read())
    return str(destino)


def subir_archivo_storage(uploaded_file, ruta_relativa):
    if not storage_disponible():
        return "", ""

    try:
        storage_path = f"proteccion_civil_digital/{ruta_relativa}"
        blob = bucket_firebase.blob(storage_path)
        uploaded_file.seek(0)
        contenido = uploaded_file.read()
        content_type = uploaded_file.type or "application/octet-stream"
        blob.upload_from_string(contenido, content_type=content_type)

        # Nota: public_url solo abre directo si tus reglas de Storage permiten lectura.
        # Aun así, el archivo queda guardado en Firebase Storage.
        archivo_url = blob.public_url
        return archivo_url, storage_path

    except Exception as e:
        st.warning(f"No se pudo subir el archivo a Firebase Storage: {e}")
        return "", ""


def insertar_documento(carpeta, centro, nombre_hoja, folio, fecha_documento, observaciones, palabras_clave, archivo_path, archivo_url, archivo_storage_path):
    fecha_captura = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    datos = {
        "fecha_captura": fecha_captura,
        "carpeta_principal": carpeta,
        "centro": centro,
        "nombre_hoja": nombre_hoja.upper(),
        "folio": folio.upper(),
        "fecha_documento": str(fecha_documento),
        "observaciones": observaciones.upper(),
        "palabras_clave": palabras_clave.upper(),
        "archivo_path": archivo_path,
        "archivo_url": archivo_url,
        "archivo_storage_path": archivo_storage_path,
        "usuario": st.session_state.usuario_pc,
    }

    firebase_id = ""

    if firebase_disponible():
        try:
            ref = db_firebase.collection(COLECCION_FIRESTORE).document()
            datos["firebase_id"] = ref.id
            ref.set(datos)
            firebase_id = ref.id
        except Exception as e:
            st.warning(f"No se pudo guardar en Firestore: {e}")

    con = conectar_local()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO documentos (
            firebase_id, fecha_captura, carpeta_principal, centro, nombre_hoja, folio,
            fecha_documento, observaciones, palabras_clave, archivo_path,
            archivo_url, archivo_storage_path, usuario
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        firebase_id,
        fecha_captura,
        carpeta,
        centro,
        nombre_hoja.upper(),
        folio.upper(),
        str(fecha_documento),
        observaciones.upper(),
        palabras_clave.upper(),
        archivo_path,
        archivo_url,
        archivo_storage_path,
        st.session_state.usuario_pc
    ))
    con.commit()
    con.close()

    return firebase_id


def leer_documentos_local():
    con = conectar_local()
    df = pd.read_sql_query("SELECT * FROM documentos ORDER BY id DESC", con)
    con.close()
    return df


def leer_documentos_firebase():
    if not firebase_disponible():
        return pd.DataFrame()

    try:
        docs = db_firebase.collection(COLECCION_FIRESTORE).stream()
        registros = []
        for doc in docs:
            d = doc.to_dict()
            d["firebase_id"] = doc.id
            registros.append(d)

        df = pd.DataFrame(registros)
        if df.empty:
            return df

        for col in [
            "firebase_id", "fecha_captura", "carpeta_principal", "centro",
            "nombre_hoja", "folio", "fecha_documento", "observaciones",
            "palabras_clave", "archivo_path", "archivo_url",
            "archivo_storage_path", "usuario"
        ]:
            if col not in df.columns:
                df[col] = ""

        df = df.sort_values("fecha_captura", ascending=False)
        df["id"] = range(1, len(df) + 1)
        return df

    except Exception as e:
        st.warning(f"No se pudo leer Firestore: {e}")
        return pd.DataFrame()


def leer_documentos():
    df_fb = leer_documentos_firebase()
    if not df_fb.empty:
        return df_fb
    return leer_documentos_local()


def filtrar_documentos(df, texto="", carpeta="Todas", centro="Todos"):
    if df.empty:
        return df

    resultado = df.copy()

    if carpeta != "Todas":
        resultado = resultado[resultado["carpeta_principal"] == carpeta]

    if centro != "Todos":
        resultado = resultado[resultado["centro"] == centro]

    if texto:
        t = texto.upper()
        campos = ["carpeta_principal", "centro", "nombre_hoja", "folio", "observaciones", "palabras_clave"]
        filtro = False
        for campo in campos:
            filtro = filtro | resultado[campo].astype(str).str.upper().str.contains(t, na=False)
        resultado = resultado[filtro]

    return resultado


def crear_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output


def leer_archivo_local(ruta):
    if ruta and os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return f.read()
    return None


def eliminar_documento(id_doc, firebase_id="", archivo_path="", archivo_storage_path=""):
    if firebase_disponible() and firebase_id:
        try:
            db_firebase.collection(COLECCION_FIRESTORE).document(firebase_id).delete()
        except Exception:
            pass

    if storage_disponible() and archivo_storage_path:
        try:
            bucket_firebase.blob(archivo_storage_path).delete()
        except Exception:
            pass

    if archivo_path and os.path.exists(archivo_path):
        try:
            os.remove(archivo_path)
        except Exception:
            pass

    con = conectar_local()
    cur = con.cursor()
    cur.execute("DELETE FROM documentos WHERE id = ?", (int(id_doc),))
    con.commit()
    con.close()


st.markdown("""
<div class="header-card">
    <h1>🚒 Sistema Integral de Digitalización Protección Civil</h1>
    <p>Licencias · Impacto Ambiental · Funcionamiento · Dictámenes · COESPRISSON</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.success(f"Usuario: {st.session_state.usuario_pc} | Rol: {st.session_state.rol_pc}")

if firebase_disponible():
    st.sidebar.success("Firebase conectado")
else:
    st.sidebar.warning("Firebase no conectado")
    with st.sidebar.expander("Ver error Firebase"):
        st.write(error_firebase)

if storage_disponible():
    st.sidebar.success("Storage configurado")
else:
    st.sidebar.warning("Storage no configurado")

if st.sidebar.button("Cerrar sesión"):
    st.session_state.logueado_pc = False
    st.session_state.usuario_pc = ""
    st.session_state.rol_pc = ""
    st.rerun()

menu = st.sidebar.radio(
    "Menú",
    [
        "🏠 Inicio",
        "📤 Digitalizar documento",
        "🔎 Buscador general",
        "📁 Carpetas principales",
        "🏢 Expediente por centro",
        "📊 Reportes",
        "⚙️ Administración"
    ]
)

df = leer_documentos()

if menu == "🏠 Inicio":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Resumen general")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documentos digitalizados", len(df))
    c2.metric("Carpetas usadas", df["carpeta_principal"].nunique() if not df.empty else 0)
    c3.metric("Centros con documentos", df["centro"].nunique() if not df.empty else 0)
    c4.metric("Usuarios", df["usuario"].nunique() if not df.empty else 0)

    st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Últimos documentos digitalizados")
    if df.empty:
        st.warning("Todavía no hay documentos digitalizados.")
    else:
        st.dataframe(
            df[["id", "carpeta_principal", "centro", "nombre_hoja", "folio", "fecha_documento", "usuario"]].head(20),
            use_container_width=True
        )

elif menu == "📤 Digitalizar documento":
    if st.session_state.rol_pc == "Consulta":
        st.warning("Tu usuario solo tiene permiso de consulta.")
        st.stop()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Subir documento escaneado")

    col1, col2 = st.columns(2)
    with col1:
        carpeta = st.selectbox("Carpeta principal", CARPETAS_PRINCIPALES)
        nombre_hoja = st.text_input("Nombre de la hoja digitalizada *", placeholder="Ejemplo: Licencia Funcionamiento 2026")
        fecha_documento = st.date_input("Fecha del documento")
    with col2:
        centro = st.selectbox("Centro / Área", CENTROS)
        folio = st.text_input("Folio", placeholder="Ejemplo: PC-2026-001")
        palabras_clave = st.text_input("Palabras clave para búsqueda", placeholder="Ejemplo: renovación anual, seguridad, licencia")

    observaciones = st.text_area("Observaciones")
    archivo = st.file_uploader("Subir PDF o imagen escaneada", type=["pdf", "jpg", "jpeg", "png"])

    if st.button("💾 Guardar digitalización"):
        if not nombre_hoja.strip():
            st.error("Debes escribir el nombre de la hoja digitalizada.")
        elif archivo is None:
            st.error("Debes subir un archivo PDF o imagen.")
        else:
            ruta_relativa = generar_nombre_archivo(archivo.name, carpeta, centro, folio, nombre_hoja)

            archivo_path = guardar_archivo_local(archivo, ruta_relativa)
            archivo_url, archivo_storage_path = subir_archivo_storage(archivo, ruta_relativa)

            firebase_id = insertar_documento(
                carpeta, centro, nombre_hoja, folio, fecha_documento,
                observaciones, palabras_clave, archivo_path, archivo_url, archivo_storage_path
            )

            st.success("Documento guardado correctamente.")
            if firebase_id:
                st.success("Registro guardado en Firestore.")
            else:
                st.warning("El registro se guardó localmente, pero no en Firestore.")

            if archivo_storage_path:
                st.success("Archivo subido a Firebase Storage.")
            else:
                st.warning("El archivo se guardó localmente, pero no se subió a Storage.")

            st.info(f"Ruta local: {archivo_path}")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "🔎 Buscador general":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Buscador documental")

    col1, col2, col3 = st.columns(3)
    with col1:
        texto = st.text_input("Buscar por nombre, folio, centro, carpeta o palabra clave")
    with col2:
        carpeta = st.selectbox("Filtrar por carpeta", ["Todas"] + CARPETAS_PRINCIPALES)
    with col3:
        centro = st.selectbox("Filtrar por centro", ["Todos"] + CENTROS)

    resultado = filtrar_documentos(df, texto=texto, carpeta=carpeta, centro=centro)

    st.write(f"Resultados encontrados: **{len(resultado)}**")

    if resultado.empty:
        st.warning("No se encontraron documentos.")
    else:
        st.dataframe(
            resultado[["id", "carpeta_principal", "centro", "nombre_hoja", "folio", "fecha_documento", "fecha_captura"]],
            use_container_width=True
        )

        id_sel = st.selectbox("Selecciona un documento", resultado["id"].tolist())
        doc = resultado[resultado["id"] == id_sel].iloc[0]

        st.markdown("### Detalle del documento")
        st.write(f"**Carpeta:** {doc['carpeta_principal']}")
        st.write(f"**Centro:** {doc['centro']}")
        st.write(f"**Nombre hoja:** {doc['nombre_hoja']}")
        st.write(f"**Folio:** {doc['folio']}")
        st.write(f"**Fecha documento:** {doc['fecha_documento']}")
        st.write(f"**Observaciones:** {doc['observaciones']}")

        archivo_url = str(doc.get("archivo_url", "") or "")
        archivo_path = str(doc.get("archivo_path", "") or "")

        if archivo_url:
            st.link_button("🌐 Abrir archivo en la nube", archivo_url)

        data = leer_archivo_local(archivo_path)
        if data:
            extension = Path(archivo_path).suffix.lower()
            mime = "application/pdf" if extension == ".pdf" else "image/png"
            st.download_button(
                "📄 Descargar archivo local",
                data=data,
                file_name=os.path.basename(archivo_path),
                mime=mime
            )
        elif not archivo_url:
            st.error("El archivo no se encontró localmente ni tiene URL de nube.")

    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "📁 Carpetas principales":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Carpetas principales")

    for carpeta in CARPETAS_PRINCIPALES:
        total = len(df[df["carpeta_principal"] == carpeta]) if not df.empty else 0
        st.write(f"📁 **{carpeta}** — {total} documentos")

    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "🏢 Expediente por centro":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Expediente digital por centro")

    centro = st.selectbox("Selecciona centro", CENTROS)
    centro_df = df[df["centro"] == centro] if not df.empty else df

    st.metric("Documentos del centro", len(centro_df))

    if centro_df.empty:
        st.warning("Este centro todavía no tiene documentos.")
    else:
        for carpeta in CARPETAS_PRINCIPALES:
            sub = centro_df[centro_df["carpeta_principal"] == carpeta]
            with st.expander(f"📁 {carpeta} ({len(sub)})", expanded=False):
                if sub.empty:
                    st.info("Sin documentos.")
                else:
                    st.dataframe(
                        sub[["id", "nombre_hoja", "folio", "fecha_documento", "fecha_captura"]],
                        use_container_width=True
                    )

    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "📊 Reportes":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Reportes")

    if df.empty:
        st.warning("Todavía no hay documentos.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            carpeta = st.selectbox("Carpeta", ["Todas"] + CARPETAS_PRINCIPALES)
        with col2:
            centro = st.selectbox("Centro", ["Todos"] + CENTROS)

        rep = filtrar_documentos(df, carpeta=carpeta, centro=centro)

        st.metric("Total filtrado", len(rep))
        st.dataframe(rep, use_container_width=True)

        st.markdown("### Documentos por carpeta")
        por_carpeta = rep["carpeta_principal"].value_counts().reset_index()
        por_carpeta.columns = ["Carpeta", "Total"]
        st.dataframe(por_carpeta, use_container_width=True)
        if not por_carpeta.empty:
            st.bar_chart(por_carpeta.set_index("Carpeta"))

        st.markdown("### Documentos por centro")
        por_centro = rep["centro"].value_counts().reset_index()
        por_centro.columns = ["Centro", "Total"]
        st.dataframe(por_centro, use_container_width=True)

        st.download_button(
            "📥 Descargar reporte Excel",
            data=crear_excel(rep),
            file_name="reporte_proteccion_civil.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "⚙️ Administración":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Administración")

    if st.session_state.rol_pc != "Administrador":
        st.warning("Solo el administrador puede eliminar documentos.")
    elif df.empty:
        st.warning("No hay documentos registrados.")
    else:
        st.dataframe(df, use_container_width=True)

        id_eliminar = st.selectbox("Selecciona ID para eliminar", df["id"].tolist())
        if st.button("🗑️ Eliminar documento"):
            fila = df[df["id"] == id_eliminar].iloc[0]
            eliminar_documento(
                id_eliminar,
                firebase_id=str(fila.get("firebase_id", "") or ""),
                archivo_path=str(fila.get("archivo_path", "") or ""),
                archivo_storage_path=str(fila.get("archivo_storage_path", "") or "")
            )
            st.success("Documento eliminado correctamente.")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
