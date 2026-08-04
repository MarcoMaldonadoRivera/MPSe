import io
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
from fpdf import FPDF
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tempfile

app = FastAPI(title="Sonoff POW - Dashboard Eléctrico")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "database.csv"

def cargar_datos() -> pd.DataFrame:
    """Carga y normaliza los datos del CSV del Sonoff POW."""
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    
    df = pd.read_csv(DATA_FILE)
    
    # Renombrar columnas a español
    df = df.rename(columns={
        "data": "fecha",
        "time": "hora_rango",
        "consumption/KWh": "kwh"
    })
    
    # Extraer hora de inicio del rango (ej: "20:00-21:00" -> 20)
    df["hora"] = df["hora_rango"].str.extract(r"(\d{2}):\d{2}").astype(int)
    
    # Convertir fecha
    df["fecha"] = pd.to_datetime(df["fecha"])
    
    # Crear datetime completo
    df["datetime"] = df.apply(
        lambda r: r["fecha"] + pd.Timedelta(hours=r["hora"]), axis=1
    )
    
    return df.sort_values("datetime").reset_index(drop=True)


def filtrar_por_rango(df: pd.DataFrame, inicio: str = None, fin: str = None) -> pd.DataFrame:
    """Filtra el DataFrame por rango de fechas si se proporcionan."""
    if inicio and fin:
        mask = (df["fecha"] >= inicio) & (df["fecha"] <= fin)
        return df[mask].copy()
    return df


def calcular_resumen(df: pd.DataFrame):
    """Calcula KPIs a partir de un DataFrame filtrado."""
    if df.empty:
        return {"total_kwh": 0, "promedio_diario_kwh": 0, "hora_pico": "N/A", "hora_pico_kwh": 0}
    
    total = df["kwh"].sum()
    dias = df["fecha"].nunique()
    promedio_diario = total / dias if dias > 0 else 0
    
    # Hora pico: promedio por hora del día
    hora_pico_df = df.groupby("hora")["kwh"].mean().reset_index()
    hora_pico_row = hora_pico_df.loc[hora_pico_df["kwh"].idxmax()]
    
    return {
        "total_kwh": round(total, 2),
        "promedio_diario_kwh": round(promedio_diario, 2),
        "hora_pico": f"{int(hora_pico_row['hora']):02d}:00",
        "hora_pico_kwh": round(hora_pico_row["kwh"], 3)
    }


@app.get("/api/resumen")
def obtener_resumen(
    inicio: str = Query(None, description="Fecha inicio YYYY-MM-DD (opcional)"),
    fin: str = Query(None, description="Fecha fin YYYY-MM-DD (opcional)")
):
    """Métricas clave: consumo total, promedio diario, hora pico.
    Acepta inicio y fin opcionales para filtrar por rango de fechas."""
    df = cargar_datos()
    df = filtrar_por_rango(df, inicio, fin)
    return calcular_resumen(df)


@app.get("/api/consumo/horas")
def consumo_por_horas(
    inicio: str = Query(None, description="Fecha inicio YYYY-MM-DD (opcional)"),
    fin: str = Query(None, description="Fecha fin YYYY-MM-DD (opcional)")
):
    """Consumo promedio agrupado por hora del día.
    Acepta inicio y fin opcionales para filtrar por rango de fechas."""
    df = cargar_datos()
    df = filtrar_por_rango(df, inicio, fin)
    if df.empty:
        return []
    
    horas = df.groupby("hora")["kwh"].mean().reset_index()
    horas["hora"] = horas["hora"].apply(lambda h: f"{int(h):02d}:00")
    return horas.to_dict(orient="records")


@app.get("/api/consumo/dias")
def consumo_por_dias(
    inicio: str = Query(None, description="Fecha inicio YYYY-MM-DD (opcional)"),
    fin: str = Query(None, description="Fecha fin YYYY-MM-DD (opcional)")
):
    """Consumo total diario.
    Acepta inicio y fin opcionales para filtrar por rango de fechas."""
    df = cargar_datos()
    df = filtrar_por_rango(df, inicio, fin)
    if df.empty:
        return []
    
    dias = df.groupby("fecha")["kwh"].sum().reset_index()
    dias["fecha"] = dias["fecha"].dt.strftime("%Y-%m-%d")
    return dias.to_dict(orient="records")


@app.get("/api/consumo/rango")
def consumo_en_rango(
    inicio: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    fin: str = Query(..., description="Fecha fin YYYY-MM-DD")
):
    """Consumo dentro de un intervalo de fechas personalizado."""
    df = cargar_datos()
    if df.empty:
        return []
    
    mask = (df["fecha"] >= inicio) & (df["fecha"] <= fin)
    df_filtrado = df[mask].copy()
    
    resultado = df_filtrado.groupby("fecha")["kwh"].sum().reset_index()
    resultado["fecha"] = resultado["fecha"].dt.strftime("%Y-%m-%d")
    return resultado.to_dict(orient="records")


@app.get("/api/comparativa")
def comparativa_periodos(
    inicio1: str = Query(..., description="Inicio período 1 YYYY-MM-DD"),
    fin1: str = Query(..., description="Fin período 1 YYYY-MM-DD"),
    inicio2: str = Query(..., description="Inicio período 2 YYYY-MM-DD"),
    fin2: str = Query(..., description="Fin período 2 YYYY-MM-DD"),
    tipo: str = Query("horas", description="Tipo: 'horas' o 'dias'")
):
    """Compara el consumo entre dos períodos de tiempo."""
    df = cargar_datos()
    if df.empty:
        return {"error": "Sin datos"}
    
    p1 = filtrar_por_rango(df, inicio1, fin1)
    p2 = filtrar_por_rango(df, inicio2, fin2)
    
    def stats(periodo):
        total = periodo["kwh"].sum()
        dias = periodo["fecha"].nunique()
        return {
            "total_kwh": round(total, 2),
            "promedio_diario_kwh": round(total / dias, 2) if dias > 0 else 0,
            "dias": dias
        }
    
    res1 = stats(p1) if not p1.empty else {"total_kwh": 0, "promedio_diario_kwh": 0, "dias": 0}
    res2 = stats(p2) if not p2.empty else {"total_kwh": 0, "promedio_diario_kwh": 0, "dias": 0}
    
    diff_total = round(res2["total_kwh"] - res1["total_kwh"], 2)
    pct = round((diff_total / res1["total_kwh"]) * 100, 1) if res1["total_kwh"] > 0 else 0
    
    # Datos para gráfico comparativo
    if tipo == "dias":
        # Alinear por día relativo (día 1, día 2...)
        g1 = p1.groupby("fecha")["kwh"].sum().reset_index() if not p1.empty else pd.DataFrame()
        g2 = p2.groupby("fecha")["kwh"].sum().reset_index() if not p2.empty else pd.DataFrame()
        
        # Normalizar a índices numéricos
        datos = []
        max_len = max(len(g1), len(g2))
        for i in range(max_len):
            d = {"indice": f"Día {i+1}"}
            d["periodo1"] = round(g1.iloc[i]["kwh"], 3) if i < len(g1) else 0
            d["periodo2"] = round(g2.iloc[i]["kwh"], 3) if i < len(g2) else 0
            datos.append(d)
    else:
        # Comparar hora por hora
        g1 = p1.groupby("hora")["kwh"].mean().reset_index() if not p1.empty else pd.DataFrame()
        g2 = p2.groupby("hora")["kwh"].mean().reset_index() if not p2.empty else pd.DataFrame()
        
        datos = []
        for h in range(24):
            v1 = g1.loc[g1["hora"] == h, "kwh"].values
            v2 = g2.loc[g2["hora"] == h, "kwh"].values
            datos.append({
                "hora": f"{h:02d}:00",
                "periodo1": round(float(v1[0]), 3) if len(v1) > 0 else 0,
                "periodo2": round(float(v2[0]), 3) if len(v2) > 0 else 0
            })
    
    return {
        "periodo1": {
            "label": f"{inicio1} a {fin1}",
            **res1
        },
        "periodo2": {
            "label": f"{inicio2} a {fin2}",
            **res2
        },
        "diferencia": {
            "total_kwh": diff_total,
            "porcentaje": pct,
            "tendencia": "sube" if diff_total > 0 else ("baja" if diff_total < 0 else "igual")
        },
        "datos": datos
    }


@app.get("/api/datos/disponibles")
def fechas_disponibles():
    """Devuelve las fechas mínima y máxima disponibles."""
    df = cargar_datos()
    if df.empty:
        return {"min": None, "max": None}
    return {
        "min": df["fecha"].min().strftime("%Y-%m-%d"),
        "max": df["fecha"].max().strftime("%Y-%m-%d")
    }



@app.get("/api/informe/pdf")
def generar_informe_pdf(
    inicio: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    fin: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    titulo: str = Query("Informe de Consumo Eléctrico", description="Título del informe")
):
    """Genera un informe PDF con el detalle de consumo entre dos fechas."""
    df = cargar_datos()
    df_filtrado = filtrar_por_rango(df, inicio, fin)
    
    if df_filtrado.empty:
        return JSONResponse({"error": "No hay datos en el rango seleccionado"}, status_code=404)
    
    resumen = calcular_resumen(df_filtrado)
    consumo_diario = df_filtrado.groupby("fecha")["kwh"].sum().reset_index()
    consumo_horas = df_filtrado.groupby("hora")["kwh"].mean().reset_index()
    
    # Top 10 días de mayor consumo
    top_dias = consumo_diario.sort_values("kwh", ascending=False).head(10)
    
    # ---- GENERAR GRÁFICO CON MATPLOTLIB ----
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['figure.facecolor'] = 'white'
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), facecolor='white')
    
    # Gráfico 1: Consumo diario
    dias_chart = consumo_diario.copy()
    dias_chart['fecha_str'] = dias_chart['fecha'].dt.strftime('%d/%m')
    bars1 = ax1.bar(dias_chart['fecha_str'], dias_chart['kwh'], color='#3b82f6', edgecolor='#2563eb', linewidth=0.5)
    ax1.bar_label(bars1, fmt='%.2f', fontsize=6, padding=2, color='#1e293b')
    ax1.set_title('Consumo Diario (kWh)', fontsize=10, fontweight='bold', color='#1e293b')
    ax1.set_ylabel('kWh', fontsize=8, color='#64748b')
    ax1.tick_params(axis='x', rotation=45, labelsize=6)
    ax1.tick_params(axis='y', labelsize=7)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.set_facecolor('#f8fafc')
    # Mostrar menos etiquetas si hay muchos días
    step = max(1, len(dias_chart) // 20)
    for i, label in enumerate(ax1.get_xticklabels()):
        if i % step != 0:
            label.set_visible(False)
    
    # Gráfico 2: Consumo por hora
    horas_chart = consumo_horas.copy()
    horas_chart['hora_label'] = horas_chart['hora'].apply(lambda h: f"{int(h):02d}:00")
    bars2 = ax2.bar(horas_chart['hora_label'], horas_chart['kwh'], color='#eab308', edgecolor='#ca8a04', linewidth=0.5)
    ax2.bar_label(bars2, fmt='%.2f', fontsize=6, padding=2, color='#1e293b')
    ax2.set_title('Consumo Promedio por Hora (kWh)', fontsize=10, fontweight='bold', color='#1e293b')
    ax2.set_ylabel('kWh', fontsize=8, color='#64748b')
    ax2.set_xlabel('Hora', fontsize=8, color='#64748b')
    ax2.tick_params(axis='x', rotation=45, labelsize=6)
    ax2.tick_params(axis='y', labelsize=7)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.set_facecolor('#f8fafc')
    # Mostrar cada 3 horas
    for i, label in enumerate(ax2.get_xticklabels()):
        if i % 3 != 0:
            label.set_visible(False)
    
    plt.tight_layout(pad=1.5)
    
    # Guardar gráfico en un archivo temporal
    chart_path = os.path.join(tempfile.gettempdir(), f"chart_{inicio}_{fin}.png")
    fig.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    
    # ---- GENERAR PDF ----
    pdf = FPDF()
    pdf.add_page()
    
    # ---- PÁGINA 1 ----
    # Encabezado
    pdf.set_fill_color(59, 130, 246)
    pdf.rect(10, 10, 190, 25, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 13)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(190, 7, "Informe de Consumo Electrico", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_xy(10, 21)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(190, 5, f"Dispositivo: Sonoff POW  |  Periodo: {inicio} al {fin}  |  Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_y(40)
    
    # Resumen
    pdf.set_fill_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, "  RESUMEN DEL PERIODO", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)
    
    pdf.set_text_color(30, 41, 59)
    for label, value in [
        ("Consumo Total:", f"{resumen['total_kwh']:.2f} kWh"),
        ("Promedio Diario:", f"{resumen['promedio_diario_kwh']:.2f} kWh/dia"),
        ("Hora de Mayor Consumo:", f"{resumen['hora_pico']} ({resumen['hora_pico_kwh']:.3f} kWh)"),
        ("Dias en el periodo:", f"{df_filtrado['fecha'].nunique()} dias"),
        ("Total de registros:", f"{len(df_filtrado)} lecturas"),
    ]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(59, 130, 246)
        pdf.cell(55, 5, f"  {label}")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 5, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    
    # Insertar gráfico
    pdf.image(chart_path, x=15, y=pdf.get_y(), w=180)
    
    # ---- PÁGINA 2 (si es necesario) ----
    pdf.add_page()
    
    # Encabezado página 2
    pdf.set_fill_color(59, 130, 246)
    pdf.rect(10, 10, 190, 15, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 12)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(190, 6, f"Detalle - {inicio} al {fin}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_y(30)
    
    # Consumo por hora (tabla)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, "  CONSUMO PROMEDIO POR HORA", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(59, 130, 246)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(20, 6, "Hora", border=1, align="C", fill=True)
    pdf.cell(25, 6, "kWh", border=1, align="C", fill=True)
    pdf.cell(0, 6, "", border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 7)
    max_kwh = consumo_horas["kwh"].max()
    bar_max = 120
    
    for i, (_, row) in enumerate(consumo_horas.iterrows()):
        h = f"{int(row['hora']):02d}:00"
        val = row["kwh"]
        bar_w = int((val / max_kwh) * bar_max) if max_kwh > 0 else 0
        
        if i % 2 == 0:
            pdf.set_fill_color(240, 244, 248)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        pdf.set_text_color(30, 41, 59)
        pdf.cell(20, 4.5, h, border=1, align="C", fill=True)
        pdf.cell(25, 4.5, f"{val:.3f}", border=1, align="C", fill=True)
        
        x0 = pdf.get_x()
        
        # Color dinámico según el consumo
        ratio = val / max_kwh if max_kwh > 0 else 0
        if ratio > 0.5:
            f = (ratio - 0.5) * 2
            r, g_col, b = int(234 + 5 * f), int(179 - 111 * f), int(8 + 60 * f)
        else:
            f = ratio * 2
            r, g_col, b = int(34 + 200 * f), int(197 - 18 * f), int(94 - 86 * f)
            
        pdf.set_fill_color(r, g_col, b)
        pdf.cell(bar_w, 4.5, "", border=0, fill=True)
        pdf.set_xy(x0 + bar_max, pdf.get_y())
        pdf.cell(0, 4.5, "", border=1)
        pdf.ln()
    pdf.ln(4)
    
    # Top 10 días
    pdf.set_fill_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, "  TOP 10 DIAS DE MAYOR CONSUMO", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(234, 179, 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(30, 6, "Fecha", border=1, align="C", fill=True)
    pdf.cell(25, 6, "kWh", border=1, align="C", fill=True)
    pdf.cell(0, 6, "", border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 7)
    top_max = top_dias["kwh"].max()
    
    for i, (_, row) in enumerate(top_dias.iterrows()):
        fecha_str = row["fecha"].strftime("%Y-%m-%d")
        val = row["kwh"]
        bar_w = int((val / top_max) * bar_max) if top_max > 0 else 0
        
        if i % 2 == 0:
            pdf.set_fill_color(255, 248, 230)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        pdf.set_text_color(30, 41, 59)
        pdf.cell(30, 4.5, fecha_str, border=1, align="C", fill=True)
        pdf.cell(25, 4.5, f"{val:.2f}", border=1, align="C", fill=True)
        
        x0 = pdf.get_x()
        
        # Color dinámico según el consumo
        ratio = val / top_max if top_max > 0 else 0
        if ratio > 0.5:
            f = (ratio - 0.5) * 2
            r, g_col, b = int(234 + 5 * f), int(179 - 111 * f), int(8 + 60 * f)
        else:
            f = ratio * 2
            r, g_col, b = int(34 + 200 * f), int(197 - 18 * f), int(94 - 86 * f)
            
        pdf.set_fill_color(r, g_col, b)
        pdf.cell(bar_w, 4.5, "", border=0, fill=True)
        pdf.set_xy(x0 + bar_max, pdf.get_y())
        pdf.cell(0, 4.5, "", border=1)
        pdf.ln()
    pdf.ln(4)
    
    # Pie
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    txt_aviso = "Aviso de Automatizacion: Informamos que el presente reporte es fruto de la integracion entre la telemetria del medidor Sonoff POW y modelos de Inteligencia Artificial Generativa para el procesamiento de datos. Si detecta alguna discrepancia inusual, le recomendamos verificar los registros brutos del dispositivo."
    pdf.multi_cell(0, 4, txt_aviso, align="C")
    
    # Limpiar archivo temporal
    try:
        os.remove(chart_path)
    except:
        pass
    
    # Generar PDF en memoria
    pdf_bytes = io.BytesIO()
    pdf.output(pdf_bytes)
    pdf_bytes.seek(0)
    
    filename = f"informe_consumo_{inicio}_{fin}.pdf"
    
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
